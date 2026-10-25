"""Construcción del grafo de la corrida (clase 11: StateGraph, arcos condicionales, SqliteSaver).

Recorrido fijo: plan → producir → revisar (un ítem por vuelta) → auditar → [revisar los ítems
reabiertos, una sola vez] → escalar → resumir. El Supervisor no puede alterarlo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from backlogguard.board import Board
from backlogguard.graph.deps import RunDeps, index_library
from backlogguard.graph.nodes import make_nodes
from backlogguard.graph.state import RunState


def route_after_work(state: RunState) -> str:
    """Después de producir, revisar o auditar: ¿hay más ítems, falta auditar o se termina?"""
    if state.get("stop_reason"):
        return "escalate"
    if state.get("pending"):
        return "review"
    return "audit" if state.get("audit_passes", 0) == 0 else "escalate"


def sqlite_checkpointer(path: str | Path) -> SqliteSaver:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def build_graph(deps: RunDeps, checkpointer: Any):
    """Compila el grafo. Indexa las fuentes, porque el índice no viaja en el estado."""
    index_library(deps.library, deps.retriever)
    nodes = make_nodes(deps)
    builder = StateGraph(RunState)
    for name, node in nodes.items():
        builder.add_node(name, node)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "produce")
    for source in ("produce", "review", "audit"):
        builder.add_conditional_edges(
            source, route_after_work, {"review": "review", "audit": "audit", "escalate": "escalate"}
        )
    builder.add_edge("escalate", "summarize")
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
        "stop_reason": None,
        "status": "en_curso",
    }


def run_pipeline(graph, objective: str, thread_id: str) -> RunState:
    """Corre una corrida completa. El `thread_id` identifica la corrida en el checkpointer."""
    return graph.invoke(initial_state(objective, thread_id), config={"configurable": {"thread_id": thread_id}})


def load_state(graph, thread_id: str) -> RunState:
    """Último estado guardado de una corrida (sirve desde otra instancia del grafo)."""
    return graph.get_state({"configurable": {"thread_id": thread_id}}).values
