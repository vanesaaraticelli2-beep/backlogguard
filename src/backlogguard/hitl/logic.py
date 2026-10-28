"""Armado de los pedidos de decisión, validación de las decisiones y sus efectos.

Reglas en código: quién puede decidir, que la decisión corresponda a la versión exacta que se vio,
qué se puede editar y qué efecto tiene cada acción. Los efectos son idempotentes (reanudar no duplica).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backlogguard.board import BacklogItem, Board, ItemState
from backlogguard.hitl.grouping import FindingGroup
from backlogguard.hitl.models import DecisionRequest, Evidence, HumanDecision
from backlogguard.hitl.people import PeopleConfig
from backlogguard.memory import ProjectMemory
from backlogguard.tools.policy_config import PolicyConfig
from backlogguard.tools.requerimientos import is_gherkin

REASON_TITLES = {
    "cambio_de_alcance": "Cambio de alcance",
    "vendido_no_tratado": "Vendido y no tratado",
    "contradiccion": "Contradicción entre reuniones",
    "desacuerdo_sin_consenso": "Desacuerdo sin consenso",
    "plan_de_publicacion": "Plan de publicación",
}
ITEM_FIELDS = ("title", "description", "acceptance_criteria")
MAX_EDITED_TEXT = 400


def decider_for(reason: str, policy: PolicyConfig) -> str:
    decides = next((rule.decides for rule in policy.pauses if rule.condition == reason), None)
    if decides is None:
        raise ValueError(f"La política no define quién decide '{reason}'.")
    return decides


# ---- armado de pedidos ----


def request_for_group(group: FindingGroup, policy: PolicyConfig) -> DecisionRequest:
    reason = group.reason
    first = group.findings[0].description
    return DecisionRequest(
        request_id=f"R-{group.group_id}",
        kind="alcance",
        reason=reason,
        decides=decider_for(reason, policy),
        ref=group.group_id,
        title=f"{REASON_TITLES[reason]}: {first[:80]}",
        summary=group.summary,
        evidence=group.evidence(),
        editable=["decision_text"],
        payload={"decision_text": first[:MAX_EDITED_TEXT], "topic_key": group.topic_key},
    ).sealed()


def request_for_item(item: BacklogItem, policy: PolicyConfig) -> DecisionRequest:
    objections = [o.text for o in item.objections if not o.resolved]
    evidence = [
        Evidence(
            fragment_id=c.fragment_id,
            quote=c.quote,
            source_name=c.source_name,
            source_date=c.source_date.isoformat(),
            speaker=c.speaker,
            page=c.page,
            source_type=c.source_type.value,
        )
        for c in item.citations
    ]
    return DecisionRequest(
        request_id=f"R-item-{item.id}",
        kind="item",
        reason="desacuerdo_sin_consenso",
        decides=decider_for("desacuerdo_sin_consenso", policy),
        ref=item.id,
        title=f"{REASON_TITLES['desacuerdo_sin_consenso']}: {item.title}",
        summary="El Crítico y el productor no llegaron a un acuerdo en 2 rondas.\nObjeciones vigentes:\n"
        + "\n".join(f"- {text}" for text in objections),
        evidence=evidence,
        editable=list(ITEM_FIELDS),
        payload={"title": item.title, "description": item.description, "acceptance_criteria": list(item.acceptance_criteria)},
    ).sealed()


def request_for_plan(plan_summary: dict, policy: PolicyConfig) -> DecisionRequest:
    actionable = [i for i in plan_summary["items"] if i["action"] != "omitir"]
    lines = [f"- {i['action'].upper()} {i['title']} ({i['reason']})" for i in plan_summary["items"]]
    return DecisionRequest(
        request_id="R-plan",
        kind="plan",
        reason="plan_de_publicacion",
        decides=decider_for("plan_de_publicacion", policy),
        ref=plan_summary["hash"],
        title=f"Plan de publicación {plan_summary['hash']}: {len(actionable)} cambio(s)",
        summary="\n".join(lines),
        editable=["exclude"],
        payload={"plan_hash": plan_summary["hash"], "items": plan_summary["items"], "exclude": []},
    ).sealed()


# ---- validación ----


def validate_decision(request: DecisionRequest, decision: HumanDecision, people: PeopleConfig | None = None) -> str | None:
    """Motivo por el que la decisión no es válida, o `None` si se puede aplicar."""
    if decision.request_id != request.request_id:
        return "La decisión es de otro pedido."
    if decision.request_version != request.version:
        return f"La decisión es de la versión {decision.request_version} y el pedido está en la {request.version}."
    if decision.args_hash != request.args_hash:
        return "El contenido cambió desde que lo viste: la decisión no corresponde a esta versión."
    if decision.actor_role != request.decides:
        return f"Este pedido lo decide el rol '{request.decides}', no '{decision.actor_role}'."
    if people is not None:
        person = people.get(decision.actor)
        if person is None:
            return f"No conozco a '{decision.actor}'."
        if person.role != decision.actor_role:
            return f"{person.name} tiene el rol '{person.role}', no '{decision.actor_role}'."
    if decision.decision != "edit":
        return "Solo la edición lleva datos." if decision.edited else None
    if not decision.edited:
        return "Una edición necesita los datos editados."
    if extra := set(decision.edited) - set(request.editable):
        return f"No se pueden editar estos campos: {sorted(extra)}."
    return _invalid_edit(request, decision.edited)


def _invalid_edit(request: DecisionRequest, edited: dict) -> str | None:
    if request.kind == "alcance":
        text = edited.get("decision_text")
        if not isinstance(text, str) or not 3 <= len(text.strip()) <= MAX_EDITED_TEXT:
            return f"El texto de la decisión debe tener entre 3 y {MAX_EDITED_TEXT} caracteres."
    elif request.kind == "item":
        if "title" in edited and (not isinstance(edited["title"], str) or not 3 <= len(edited["title"].strip()) <= 140):
            return "El título debe tener entre 3 y 140 caracteres."
        if "description" in edited and not isinstance(edited["description"], str):
            return "La descripción debe ser texto."
        criteria = edited.get("acceptance_criteria")
        if criteria is not None and (
            not isinstance(criteria, list) or not all(isinstance(c, str) and c.strip() for c in criteria) or not any(is_gherkin(c) for c in criteria)
        ):
            return "Los criterios deben ser texto y al menos uno un escenario Dado/Cuando/Entonces."
    elif request.kind == "plan":
        known = {i["item_id"] for i in request.payload["items"] if i["action"] != "omitir"}
        excluded = edited.get("exclude")
        if not isinstance(excluded, list) or not set(excluded) <= known:
            return "Solo se pueden excluir ítems del plan que se van a publicar."
    return None


# ---- efectos (idempotentes) ----


@dataclass(frozen=True)
class EffectResult:
    outcome: str
    detail: str = ""


def apply_scope_decision(
    request: DecisionRequest, decision: HumanDecision, memory: ProjectMemory, *, today: date | None = None
) -> EffectResult:
    """Registra en la memoria del proyecto lo que decidió la persona (aprobar o rechazar el asunto)."""
    verb = "Se aprueba" if decision.decision == "approve" else "Se rechaza"
    statement = f"{verb}: {request.payload['decision_text'].strip()}"
    key = request.payload["topic_key"]
    existing = next((e for e in memory.current_decisions() if e["key"] == key), None)
    if existing and existing["value"].get("decision") == statement:
        return EffectResult("ya_registrada", "la decisión ya figuraba en la memoria")
    evidence = request.evidence[0] if request.evidence else None
    memory.register_decision(
        key,
        statement,
        decided_on=today or date.today(),
        speaker=decision.actor,
        authority=decision.actor_role,
        source=evidence.fragment_id if evidence else request.request_id,
        quote=evidence.quote if evidence else request.title,
        approved_by=decision.actor,
        supersedes=existing["memory_id"] if existing else None,
    )
    return EffectResult("registrada")


def apply_item_decision(request: DecisionRequest, decision: HumanDecision, board: Board) -> EffectResult:
    """Resuelve un desacuerdo sin consenso: aprobar (con la versión vista) o excluir el ítem."""
    item = board.items[request.ref]
    if decision.decision == "reject":
        if item.state is ItemState.OBJETADO:
            item.transition_to(ItemState.EXCLUIDO)
        return EffectResult("excluido")
    if item.state is ItemState.OBJETADO:
        for name in ITEM_FIELDS:
            setattr(item, name, request.payload[name])
        for objection in item.objections:
            objection.resolved = True
        item.transition_to(ItemState.SUSTENTADO)
    return EffectResult("sustentado")
