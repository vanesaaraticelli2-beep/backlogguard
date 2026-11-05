"""Cobertura de una corrida: qué pasó con cada requisito aprobado que debía quedar en una historia (fuera del curso).

Cada requisito termina con una historia o con un motivo. Nada desaparece sin aviso.
"""
from __future__ import annotations

from backlogguard.board import Board, ItemState

WITH_STORY, EXCLUDED, WITHOUT_STORY = "con_historia", "excluida", "sin_historia"
LABELS = {WITH_STORY: "Con historia", EXCLUDED: "Historia excluida", WITHOUT_STORY: "Sin historia"}


def rows(scope: list[dict], board: Board, not_drafted: dict[str, str]) -> list[dict]:
    """Una fila por requisito: su historia (si la hay), el estado y, si no está bien cubierto, el motivo."""
    by_requirement = {item.requirement_id: item for item in board.items.values() if item.requirement_id}
    found = []
    for entry in scope:
        item = by_requirement.get(entry["id"])
        if item is None:
            found.append({**entry, "item_id": None, "status": WITHOUT_STORY, "reason": not_drafted.get(entry["id"], "No se redactó una historia para este requisito.")})
        elif item.state is ItemState.EXCLUIDO:
            reason = item.objections[-1].text if item.objections else "La historia quedó excluida."
            found.append({**entry, "item_id": item.id, "status": EXCLUDED, "reason": reason})
        else:
            found.append({**entry, "item_id": item.id, "status": WITH_STORY, "reason": ""})
    return found


def from_state(state: dict) -> list[dict]:
    """La cobertura de una corrida a partir de su estado guardado (tablero, requisitos de la corrida y los que no se redactaron)."""
    if not state.get("coverage_scope"):
        return []
    board = Board.model_validate(state["board"]) if state.get("board") else Board()
    return rows(state["coverage_scope"], board, state.get("not_drafted") or {})


def summary_line(found: list[dict]) -> str:
    total = len(found)
    ok = sum(1 for r in found if r["status"] == WITH_STORY)
    gaps = total - ok
    return f"{ok} de {total} requisitos con historia" + (f" · {gaps} sin cubrir o excluidos (con su motivo)" if gaps else "")
