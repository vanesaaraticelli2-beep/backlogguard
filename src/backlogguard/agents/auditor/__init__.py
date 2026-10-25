"""Agente Auditor de Proyecto: audita con sus tools y devuelve un informe validado."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backlogguard.agents.auditor.informe import ApplyResult, AuditReport, apply_report, parse_report
from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.agents.structured import parse_with_repair
from backlogguard.board import AgentRole, Board
from backlogguard.llm.errors import InvalidProviderResponseError
from backlogguard.llm.providers import LLMProvider
from backlogguard.memory import ProjectMemory
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools import ExecutionContext, ToolPolicy, build_catalog_registry
from backlogguard.tools.auditor import AuditorToolkit

INSTRUCTIONS_PATH = Path(__file__).with_name("agent.md")
GOAL = "Auditá el proyecto: compará lo tratado con lo vendido y detectá cambios de alcance y contradicciones."
REPORT_FORMAT = (
    '{"findings": [{"kind": "...", "description": "...", "item_id": null, '
    '"citations": [{"chunk_id": "...", "quote": "..."}]}], "summary": "..."}'
)

__all__ = ["ApplyResult", "AuditReport", "AuditRun", "apply_report", "run_auditor"]


@dataclass(frozen=True)
class AuditRun:
    report: AuditReport
    stop_reason: str
    tokens: int


def run_auditor(
    *,
    provider: LLMProvider,
    retriever: InMemoryRetriever | QdrantRetriever,
    board: Board,
    memory: ProjectMemory,
    approved_by: str | None = None,
    run_id: str = "run-local",
    max_steps: int = 8,
    max_seconds: float = 300.0,
    max_tool_calls: int = 6,
    max_tokens: int = 60_000,
) -> AuditRun:
    """Corre al Auditor sobre todo el proyecto. No aplica el informe: eso lo hace `apply_report`."""
    context = ExecutionContext(user_id="factory", role=AgentRole.AUDITOR, run_id=run_id, approved_by=approved_by)
    toolkit = AuditorToolkit(retriever, board, memory, context)
    registry = build_catalog_registry(toolkit.implementations())
    policy = ToolPolicy()
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    decider = LLMDecider(
        provider,
        AgentRole.AUDITOR.value,
        registry,
        context,
        policy,
        instructions=instructions,
        max_observation_chars=12_000,
    )
    outcome = run_basic_agent(
        GOAL,
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
    if outcome["stop_reason"] != "final_answer":
        raise InvalidProviderResponseError(f"el Auditor no llegó a un informe ({outcome['stop_reason']})")
    report, repair_tokens = parse_with_repair(
        outcome["answer"],
        parse_report,
        provider=provider,
        system=instructions,
        expected_format=REPORT_FORMAT,
        subject="el Auditor",
    )
    return AuditRun(report=report, stop_reason=outcome["stop_reason"], tokens=decider.tokens_used + repair_tokens)
