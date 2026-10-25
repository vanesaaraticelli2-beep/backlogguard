"""Negociación Crítico ↔ productor con tope de rondas, aplicada en código.

Fuera del curso. El Crítico no escribe en el tablero: este módulo aplica sus veredictos con
`transition_to` y `Objection`, que ya validan citas y transiciones. Dos reglas no dependen del
modelo: una cita que no se verifica impide `sustentado`, y nunca hay más de `MAX_ROUNDS` rondas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from backlogguard.agents.critico import CriticVerdict
from backlogguard.board import MAX_ROUNDS, AgentRole, Board, ItemState, Objection
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools.critico import check_citations

Review = Callable[[str], CriticVerdict]
Revise = Callable[[str, list[str]], None]


@dataclass(frozen=True)
class NegotiationResult:
    item_id: str
    outcome: Literal["sustentado", "sin_consenso"]
    rounds: int
    objections: list[str] = field(default_factory=list)


def negotiate_item(
    item_id: str,
    *,
    board: Board,
    retriever: InMemoryRetriever | QdrantRetriever,
    review: Review,
    revise: Revise,
    max_rounds: int = MAX_ROUNDS,
) -> NegotiationResult:
    """Revisa un ítem hasta `max_rounds` veces. Sin acuerdo, queda objetado para que decida una persona."""
    if not 1 <= max_rounds <= MAX_ROUNDS:
        raise ValueError(f"max_rounds debe estar entre 1 y {MAX_ROUNDS}")
    all_objections: list[str] = []

    for round_number in range(1, max_rounds + 1):
        item = board.items[item_id]
        verdict = review(item_id)
        failed = [c for c in check_citations(item, retriever) if not c.ok]
        objections = list(verdict.objections) + [
            f"Cita no verificable ({c.fragment_id}): {c.reason}" for c in failed
        ]

        if verdict.verdict == "sustentado" and not failed:
            item.transition_to(ItemState.SUSTENTADO)
            for objection in item.objections:
                objection.resolved = True
            return NegotiationResult(item_id, "sustentado", round_number, all_objections)

        if item.state is ItemState.BORRADOR:
            item.transition_to(ItemState.OBJETADO)
        for text in objections:
            item.add_objection(
                Objection(
                    id=f"{item_id}-O{len(item.objections) + 1}",
                    raised_by=AgentRole.CRITICO,
                    text=text,
                    round=round_number,
                )
            )
        all_objections.extend(objections)

        if round_number == max_rounds:
            return NegotiationResult(item_id, "sin_consenso", round_number, all_objections)
        revise(item_id, objections)

    raise AssertionError("inalcanzable: la última ronda siempre retorna")  # pragma: no cover
