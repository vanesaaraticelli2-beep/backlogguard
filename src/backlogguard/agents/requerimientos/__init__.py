"""Agente de Requerimientos: arma el ciclo con sus tools y sus instrucciones."""
from __future__ import annotations

from pathlib import Path

from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.board import AgentRole, Board
from backlogguard.llm.providers import LLMProvider
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
    run_id: str = "run-local",
    max_steps: int = 14,
    max_seconds: float = 180.0,
    max_tool_calls: int = 20,
    max_tokens: int = 60_000,
) -> dict:
    """Corre al agente sobre un tablero y devuelve respuesta, traza, stop reason y tokens."""
    toolkit = RequirementsToolkit(library, retriever, board)
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(user_id="factory", role=AgentRole.REQUERIMIENTOS, run_id=run_id)
    policy = ToolPolicy()
    decider = LLMDecider(
        provider,
        AgentRole.REQUERIMIENTOS.value,
        registry,
        context,
        policy,
        instructions=INSTRUCTIONS_PATH.read_text(encoding="utf-8"),
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
    )
    return {**outcome, "tokens": decider.tokens_used}
