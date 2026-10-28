"""Agente de Requerimientos: arma el ciclo con sus tools y sus instrucciones."""
from __future__ import annotations

from pathlib import Path

from backlogguard.agents.context import load_limits
from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.board import AgentRole, Board
from backlogguard.catalog import Catalog
from backlogguard.llm.providers import LLMProvider
from backlogguard.skills import skill_instructions
from backlogguard.rag import SourceLibrary
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools import ExecutionContext, ToolPolicy, build_catalog_registry
from backlogguard.tools.requerimientos import RequirementsToolkit

INSTRUCTIONS_PATH = Path(__file__).with_name("agent.md")


def run_requerimientos(
    goal: str,
    *,
    provider: LLMProvider,
    library: SourceLibrary,
    retriever: InMemoryRetriever | QdrantRetriever,
    board: Board,
    catalog: Catalog | None = None,
    run_id: str = "run-local",
    max_steps: int = 40,
    max_seconds: float = 900.0,
    max_tool_calls: int = 50,
    max_tokens: int = 150_000,
    on_event: Callable[[dict], None] | None = None,
) -> dict:
    """Corre al agente sobre un tablero y devuelve respuesta, traza, stop reason y tokens."""
    toolkit = RequirementsToolkit(library, retriever, board, catalog)
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(user_id="factory", role=AgentRole.REQUERIMIENTOS, run_id=run_id)
    policy = ToolPolicy()
    decider = LLMDecider(
        provider,
        AgentRole.REQUERIMIENTOS.value,
        registry,
        context,
        policy,
        instructions=skill_instructions("requerimientos", INSTRUCTIONS_PATH),
        limits=load_limits("requerimientos"),
    )
    outcome = run_basic_agent(
        goal,
        registry,
        decider,
        max_steps=max_steps,
        max_seconds=max_seconds,
        max_tool_calls=max_tool_calls,
        max_tokens=max_tokens,
        tokens_used=lambda: decider.tokens_used,
        context=context,
        policy=policy,
        on_event=on_event,
    )
    return {**outcome, "tokens": decider.tokens_used}


def revise_item(item_id: str, objections: list[str], **kwargs) -> dict:
    """Pide al productor que corrija un ítem objetado (usa `redactar_historia` con `revises`)."""
    listed = "\n".join(f"- {text}" for text in objections)
    goal = (
        f"El Crítico objetó el ítem {item_id}. Objeciones:\n{listed}\n"
        f'Corregilo con redactar_historia usando revises="{item_id}" (mismo tipo, con título, como/quiero/para, '
        "todos los criterios de aceptación —escenarios y reglas— y citas corregidos). Podés buscar en las fuentes antes. Si la objeción no tiene "
        "solución con las fuentes, explicalo en tu respuesta final sin inventar nada. Corregilo UNA sola vez y terminá."
    )
    # Corregir un ítem es una tarea corta: sin tope, el modelo puede reescribirlo una y otra vez.
    for name, limit in (("max_steps", 8), ("max_tool_calls", 8), ("max_tokens", 40_000), ("max_seconds", 240.0)):
        kwargs.setdefault(name, limit)
    return run_requerimientos(goal, **kwargs)
