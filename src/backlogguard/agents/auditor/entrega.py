"""Entrega de los hallazgos: qué corrige el productor y qué decide una persona.

Regla en código (no del modelo): el productor recibe **un mensaje por ítem afectado** con todos
sus hallazgos corregibles juntos; los hallazgos que exigen una decisión humana no pasan por él.
El Auditor informa una sola vez: tras la corrección, el ítem vuelve al Crítico (tope de 2 rondas).
"""
from __future__ import annotations

from backlogguard.board import AgentMessage, AgentRole, Board, Finding, FindingKind
from backlogguard.tools.policy_config import PolicyConfig

# Qué condición de `config/policy.yaml` decide cada tipo de hallazgo que ningún agente resuelve.
PAUSE_CONDITION = {
    FindingKind.CAMBIO_DE_ALCANCE: "cambio_de_alcance",
    FindingKind.TRATADO_NO_VENDIDO: "cambio_de_alcance",
    FindingKind.CONTRADICCION: "contradiccion",
    FindingKind.VENDIDO_NO_TRATADO: "vendido_no_tratado",
}


def who_decides(finding: Finding, policy: PolicyConfig) -> str | None:
    """Persona que debe decidir según la política, o `None` si el hallazgo lo corrige el productor."""
    if finding.addressee is AgentRole.REQUERIMIENTOS:
        return None
    condition = PAUSE_CONDITION.get(finding.kind)
    return next((rule.decides for rule in policy.pauses if rule.condition == condition), None)


def corrections_by_item(findings: list[Finding]) -> dict[str, list[str]]:
    """Textos de corrección agrupados por ítem, solo de lo que le toca al productor."""
    grouped: dict[str, list[str]] = {}
    for finding in findings:
        if finding.addressee is AgentRole.REQUERIMIENTOS and finding.item_id:
            grouped.setdefault(finding.item_id, []).append(_render(finding))
    return grouped


def deliver_corrections(board: Board, findings: list[Finding]) -> list[AgentMessage]:
    """Publica en el tablero un mensaje Auditor → Requerimientos por ítem afectado."""
    messages = []
    for item_id, texts in corrections_by_item(findings).items():
        body = "\n".join(f"- {text}" for text in texts)
        message = AgentMessage(
            sender=AgentRole.AUDITOR,
            recipient=AgentRole.REQUERIMIENTOS,
            content=f"Correcciones para {item_id} ({len(texts)}):\n{body}",
        )
        board.post_message(message)
        messages.append(message)
    return messages


def _render(finding: Finding) -> str:
    quotes = "; ".join(f"«{c.quote}» ({c.source_name}, {c.source_date.isoformat()})" for c in finding.citations)
    return f"{finding.description} Fuentes: {quotes}"
