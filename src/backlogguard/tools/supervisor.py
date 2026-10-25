"""Tools del Supervisor: delegar tareas y escalar a una persona.

Ninguna ejecuta trabajo ni escribe en el tablero: solo registran. Quién decide una escalación
lo fija la política (`config/policy.yaml`), nunca el modelo.
"""
from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from backlogguard.rag.sources import SourceLibrary
from backlogguard.tools.models import ToolResult
from backlogguard.tools.policy_config import PolicyConfig

DocumentId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,60}$")]
TASK_BY_AGENT = {"requerimientos": "redactar", "critico": "revisar", "auditor": "auditar"}
MAX_DELEGATIONS = 4

# Las razones coinciden con las condiciones de pausa de config/policy.yaml.
EscalationReason = Literal["cambio_de_alcance", "contradiccion", "vendido_no_tratado", "desacuerdo_sin_consenso"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DelegateArgs(_Args):
    agent: Literal["requerimientos", "critico", "auditor"]
    task: Literal["redactar", "revisar", "auditar"]
    sources: list[DocumentId] = Field(default_factory=list, max_length=8)
    instruction: str = Field(default="", max_length=400)


class EscalateArgs(_Args):
    reason: EscalationReason
    ref: str = Field(min_length=1, max_length=80, description="id del ítem o del hallazgo")
    detail: str = Field(default="", max_length=400)


class Delegation(BaseModel):
    agent: str
    task: str
    sources: list[str] = Field(default_factory=list)
    instruction: str = ""


class Escalation(BaseModel):
    id: str
    reason: str
    decides: str
    ref: str
    detail: str = ""


def _fail(content: str, error_type: str) -> ToolResult:
    return ToolResult(ok=False, content=content, metadata={"error_type": error_type})


class SupervisorToolkit:
    def __init__(
        self,
        library: SourceLibrary,
        policy: PolicyConfig,
        escalations: list[Escalation] | None = None,
        max_delegations: int = MAX_DELEGATIONS,
    ):
        self.library = library
        self.policy = policy
        self.max_delegations = max_delegations
        self.delegations: list[Delegation] = []
        self.escalations: list[Escalation] = list(escalations or [])

    def delegar_tarea(self, args: dict) -> ToolResult:
        if TASK_BY_AGENT[args["agent"]] != args["task"]:
            return _fail(f"{args['agent']} hace la tarea '{TASK_BY_AGENT[args['agent']]}', no '{args['task']}'", "invalid_task")
        if args["agent"] == "requerimientos" and not args["sources"]:
            return _fail("Redactar requiere al menos una fuente.", "missing_sources")
        unknown = sorted(set(args["sources"]) - set(self.library.list_ids()))
        if unknown:
            return _fail(f"Fuentes inexistentes: {unknown}", "unknown_source")
        if any(d.agent == args["agent"] for d in self.delegations):
            return _fail(f"Ya se delegó una tarea a {args['agent']}.", "duplicate_delegation")
        if len(self.delegations) >= self.max_delegations:
            return _fail("Se alcanzó el máximo de delegaciones.", "too_many_delegations")
        self.delegations.append(Delegation(**args))
        return ToolResult(ok=True, content=f"Tarea '{args['task']}' delegada a {args['agent']}.")

    def escalar_a_persona(self, args: dict) -> ToolResult:
        decides = next((r.decides for r in self.policy.pauses if r.condition == args["reason"]), None)
        if decides is None:
            return _fail(f"La política no define quién decide '{args['reason']}'.", "no_decider")
        digest = hashlib.sha1(f"{args['reason']}|{args['ref']}".encode()).hexdigest()[:8]
        escalation_id = f"E-{digest}"
        if any(e.id == escalation_id for e in self.escalations):
            return ToolResult(ok=True, content=f"La escalación {escalation_id} ya estaba registrada.", metadata={"escalation_id": escalation_id})
        self.escalations.append(
            Escalation(id=escalation_id, reason=args["reason"], decides=decides, ref=args["ref"], detail=args["detail"])
        )
        return ToolResult(
            ok=True,
            content=f"Escalado a {decides} ({args['reason']}, {args['ref']}).",
            metadata={"escalation_id": escalation_id, "decides": decides},
        )

    def implementations(self) -> dict:
        return {
            "delegar_tarea": (self.delegar_tarea, DelegateArgs, True),
            "escalar_a_persona": (self.escalar_a_persona, EscalateArgs, True),
        }
