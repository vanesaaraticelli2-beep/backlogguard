"""Historial de decisiones del proyecto (fuera del curso): todo lo que una persona ya definió, venga de donde venga.

Junta tres lugares que guardan decisiones por rol: las propuestas del catálogo, las decisiones de alcance de la memoria del proyecto
y los pedidos de las corridas (desacuerdos y aprobación del plan). Es una función pura sobre datos ya leídos, para poder probarla.
"""
from __future__ import annotations

from typing import Any

from backlogguard.catalog import Proposal, ProposalState

ROLES = {"product_owner": "product owner", "service_manager": "service manager", "full_stack_ia_engineer": "ingeniero"}
ACTIONS = {"approve": "Aprobado", "reject": "Rechazado", "edit": "Editado"}
LIMIT = 160


def _clip(text: str, limit: int = LIMIT) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _role(role: str | None) -> str:
    return ROLES.get(role or "", role or "")


def _from_proposals(proposals: list[Proposal]) -> list[dict[str, Any]]:
    rows = []
    for p in proposals:
        if p.state is ProposalState.PENDIENTE:
            continue
        title = p.drafts[0].title if p.drafts else (p.evidence[0].quote if p.evidence else p.id)
        rejected = p.state is ProposalState.RECHAZADA
        result = "Rechazada" if rejected else ("Cubierto, automático" if p.decided_by == "automático" else "Aprobada")
        rows.append({"momento": p.created_at[:16].replace("T", " "), "tipo": "Revisión de propuesta", "qué": f"{p.id} · {_clip(title)}",
                     "resultado": result, "rol": "sistema" if p.decided_by == "automático" else _role(p.decided_by), "comentario": _clip(p.note)})
    return rows


def _from_scope(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for d in decisions:
        value = d.get("value") or {}
        text = value.get("decision", "")
        approved = text.startswith("Se aprueba")
        rows.append({"momento": str(d.get("created_at") or value.get("decided_on", ""))[:16].replace("T", " "), "tipo": "Cambio de alcance",
                     "qué": _clip(text.partition(": ")[2] or text), "resultado": "Aprobado" if approved else "Rechazado",
                     "rol": _role(value.get("approved_by") or value.get("authority")), "comentario": ""})
    return rows


def _request_name(request_id: str, titles: dict[str, str]) -> str:
    """El título del pedido si la corrida lo guardó; si no, un nombre legible a partir de su id."""
    if request_id in titles:
        return titles[request_id]
    if request_id.startswith("R-item-"):
        return f"Desacuerdo sobre la historia {request_id.removeprefix('R-item-')}"
    return "Plan de publicación" if request_id.startswith("R-plan") else request_id


def _from_runs(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for state in states:
        titles = {r["request_id"]: r["title"] for r in state.get("requests", []) if r.get("request_id")}
        plan = state.get("plan_request")
        if plan and plan.get("request_id"):
            titles[plan["request_id"]] = plan.get("title", "Plan de publicación")
        for d in state.get("decisions", []):
            if not d.get("accepted", True):
                continue  # un intento rechazado por el sistema no es una decisión
            rows.append({"momento": d["at"][:16].replace("T", " "), "tipo": "Pedido de la corrida", "qué": _clip(_request_name(d["request_id"], titles)),
                         "resultado": ACTIONS.get(d["decision"], d["decision"]), "rol": _role(d["actor_role"]), "comentario": _clip(d.get("comment", ""))})
    return rows


def history(proposals: list[Proposal], scope_decisions: list[dict[str, Any]], run_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Todas las decisiones del proyecto, la más reciente primero."""
    rows = _from_proposals(proposals) + _from_scope(scope_decisions) + _from_runs(run_states)
    return sorted(rows, key=lambda r: r["momento"], reverse=True)
