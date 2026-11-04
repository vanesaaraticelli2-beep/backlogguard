"""Construcción del grafo de la corrida (clase 11: StateGraph, arcos condicionales, SqliteSaver).

Recorrido fijo: plan → producir → revisar (un ítem por vuelta, o por olas de N en paralelo) → auditar → [revisar los ítems
reabiertos, una sola vez] → escalar → decidir (pausas) → armar el plan → aprobar el plan (pausa) → resumir. El Supervisor no puede alterarlo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from backlogguard.board import Board
from backlogguard.graph.deps import RunDeps, index_library
from backlogguard.graph.nodes import make_nodes
from backlogguard.graph.state import RunState


def route_after_work(state: RunState, parallel: bool = False) -> str:
    """Después de producir, revisar o auditar: ¿hay más ítems, falta auditar o se termina?

    Con revisión en paralelo los ítems pasan primero por `triage`, que arma la ola; en fila se revisa de a uno.
    """
    if state.get("stop_reason"):
        return "escalate"
    if state.get("pending"):
        return "triage" if parallel else "review"
    return "audit" if state.get("audit_passes", 0) == 0 else "escalate"


def dispatch_wave(state: RunState) -> list[Send] | str:
    """Fan-out (clase 12): un `Send` por ítem de la ola, y cada uno corre `review_one` por su cuenta.

    Si el triage no dejó ítems para revisar (eran duplicados o se cortó por presupuesto), sigue como después de cualquier trabajo.
    """
    wave = state.get("wave") or []
    if not wave:
        return route_after_work(state, parallel=True)
    return [Send("review_one", {"item_id": item_id, "board": state["board"]}) for item_id in wave]


def route_to_decisions(state: RunState) -> str:
    """Mientras haya pedidos de decisión por resolver, se vuelve a pausar."""
    return "decide" if state.get("requests") else "integrate"


def route_to_plan_approval(state: RunState) -> str:
    return "approve_plan" if state.get("plan_request") else "summarize"


PARALLEL_NODES = ("triage", "review_one", "merge_reviews")


def sqlite_checkpointer(path: str | Path) -> SqliteSaver:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def build_graph(deps: RunDeps, checkpointer: Any):
    """Compila el grafo. Indexa las fuentes, porque el índice no viaja en el estado."""
    index_library(deps.library, deps.retriever)
    nodes = make_nodes(deps)
    parallel = deps.budget.max_parallel_reviews > 1
    builder = StateGraph(RunState)
    unused = {"review"} if parallel else set(PARALLEL_NODES)
    for name, node in nodes.items():
        if name not in unused:
            builder.add_node(name, node)

    def after_work(state: RunState) -> str:
        return route_after_work(state, parallel)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "produce")
    if parallel:  # revisión por olas: triage → Send a review_one (en paralelo) → merge_reviews → siguiente ola o auditoría
        destinations = {"triage": "triage", "audit": "audit", "escalate": "escalate"}
        for source in ("produce", "merge_reviews", "audit"):
            builder.add_conditional_edges(source, after_work, destinations)
        builder.add_conditional_edges("triage", dispatch_wave, ["review_one", "triage", "audit", "escalate"])
        builder.add_edge("review_one", "merge_reviews")
    else:
        for source in ("produce", "review", "audit"):
            builder.add_conditional_edges(
                source, after_work, {"review": "review", "audit": "audit", "escalate": "escalate"}
            )
    builder.add_conditional_edges("escalate", route_to_decisions, {"decide": "decide", "integrate": "integrate"})
    builder.add_conditional_edges("decide", route_to_decisions, {"decide": "decide", "integrate": "integrate"})
    builder.add_conditional_edges(
        "integrate", route_to_plan_approval, {"approve_plan": "approve_plan", "summarize": "summarize"}
    )
    builder.add_conditional_edges(
        "approve_plan", route_to_plan_approval, {"approve_plan": "approve_plan", "summarize": "summarize"}
    )
    builder.add_edge("summarize", END)
    return builder.compile(checkpointer=checkpointer)


def initial_state(objective: str, run_id: str) -> RunState:
    return {
        "run_id": run_id,
        "objective": objective,
        "board": Board().model_dump(mode="json"),
        "pending": [],
        "reviewed": {},
        "audit_passes": 0,
        "escalations": [],
        "errors": [],
        "tokens": 0,
        "trace": [],
        "tasks": [],
        "stop_reason": None,
        "status": "en_curso",
    }


def run_pipeline(graph, objective: str, thread_id: str) -> RunState:
    """Corre una corrida completa. El `thread_id` identifica la corrida en el checkpointer."""
    return graph.invoke(initial_state(objective, thread_id), config={"configurable": {"thread_id": thread_id}})


def pending_request(graph, thread_id: str) -> dict | None:
    """Pedido de decisión en el que está pausada la corrida (con el último error, si lo hubo), o `None`."""
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    for task in snapshot.tasks:
        for interruption in task.interrupts:
            return interruption.value
    return None


def resume_pipeline(graph, thread_id: str, decision: dict) -> RunState:
    """Retoma la corrida pausada con la decisión de una persona (`Command(resume=...)`, clase 11)."""
    return graph.invoke(Command(resume=decision), config={"configurable": {"thread_id": thread_id}})


def load_state(graph, thread_id: str) -> RunState:
    """Último estado guardado de una corrida (sirve desde otra instancia del grafo)."""
    return graph.get_state({"configurable": {"thread_id": thread_id}}).values
