"""Agente de Integración: arma y revalida el plan; la publicación la dispara la aplicación.

El modelo prepara el plan con sus tools, pero el plan se garantiza en código: si el modelo no
llega a armarlo, se arma igual. Publicar exige un plan aprobado por una persona (`execute_approved_plan`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backlogguard.agents.context import load_limits
from backlogguard.skills import skill_instructions
from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.board import AgentRole
from backlogguard.integrations import ExecutionReport, PublishPlan, PublishService
from backlogguard.llm.providers import LLMProvider
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry
from backlogguard.tools.integracion import IntegrationToolkit

INSTRUCTIONS_PATH = Path(__file__).with_name("agent.md")
GOAL = "Preparé el plan de publicación del backlog: buscá posibles duplicados, armá el plan en dry-run y revalidalo."


@dataclass(frozen=True)
class IntegrationRun:
    plan: PublishPlan
    summary: str
    tokens: int
    stop_reason: str


def run_integracion(
    *,
    provider: LLMProvider,
    service: PublishService,
    run_id: str = "run-local",
    max_steps: int = 6,
    max_seconds: float = 180.0,
    max_tool_calls: int = 5,
    max_tokens: int = 30_000,
    on_event: Callable[[dict], None] | None = None,
) -> IntegrationRun:
    """Corre al agente en modo borrador (sin permiso de escritura externa) y devuelve el plan armado."""
    toolkit = IntegrationToolkit(service)
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(user_id="factory", role=AgentRole.INTEGRACION, run_id=run_id, allow_drafts=True)
    policy = ToolPolicy()
    decider = LLMDecider(
        provider,
        AgentRole.INTEGRACION.value,
        registry,
        context,
        policy,
        instructions=skill_instructions("integracion", INSTRUCTIONS_PATH),
        limits=load_limits("integracion"),
        max_observation_chars=8_000,
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
        on_event=on_event,
    )
    # El plan no depende del modelo: si no lo armó, se arma ahora con la misma lógica.
    plan = service.stored_plan(toolkit.last_plan_hash) if toolkit.last_plan_hash else None
    plan = plan or service.arm()
    summary = outcome["answer"] if outcome["stop_reason"] == "final_answer" else "Plan armado sin resumen del agente."
    return IntegrationRun(plan=plan, summary=summary, tokens=decider.tokens_used, stop_reason=outcome["stop_reason"])


def execute_approved_plan(
    plan_hash: str, *, service: PublishService, approved_by: str, run_id: str = "run-local"
) -> ExecutionReport:
    """Publica un plan que una persona ya aprobó. Lo llama la aplicación, nunca el modelo.

    Pasa por el `ToolRegistry`: rige la política (rol, permiso de escritura externa) y la guarda que
    exige que el hash a ejecutar sea el aprobado.
    """
    toolkit = IntegrationToolkit(service)
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(
        user_id=approved_by,
        role=AgentRole.INTEGRACION,
        run_id=run_id,
        allow_drafts=True,
        allow_external_writes=True,
        approved_plan_hash=plan_hash,
        approved_by=approved_by,
    )
    result = registry.run(
        ToolCall(tool_name="ejecutar_plan_aprobado", arguments={"plan_hash": plan_hash}), context=context, policy=ToolPolicy()
    )
    if result.metadata.get("error_type") in ("execution_failed", "plan_drift"):
        return ExecutionReport.model_validate_json(result.content)
    if not result.ok:
        return ExecutionReport(ok=False, error=result.content)
    return ExecutionReport.model_validate_json(result.content)
