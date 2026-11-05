"""Estado del grafo de la corrida (clase 11: State explícito y serializable).

El tablero viaja como JSON; los demás campos son tipos simples para poder guardarlos en SQLite.
`trace` se acumula (los nodos solo agregan); el resto de los campos se reemplaza.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def collect_results(current: list[dict] | None, update: list[dict] | None) -> list[dict]:
    """Reducer de las ramas paralelas: junta los resultados; `None` vacía la lista (cada ola empieza de cero)."""
    if update is None:
        return []
    return [*(current or []), *update]


class RunState(TypedDict, total=False):
    run_id: str
    objective: str
    board: dict
    plan: dict
    sources: list[dict]
    pending: list[str]
    coverage_scope: list[dict]  # requisitos aprobados que esta corrida debía dejar en una historia (id y título)
    not_drafted: dict[str, str]  # requisito → por qué no se redactó
    wave: list[str]  # ítems que se revisan a la vez en la ola actual (solo con revisión en paralelo)
    review_results: Annotated[list[dict], collect_results]  # lo que devuelve cada rama; lo junta `merge_reviews`
    reviewed: dict[str, dict]
    audit: dict
    publish_plan: dict
    requests: list[dict]
    plan_request: dict | None
    plan_exclusions: list[str]
    decision_error: str | None
    decisions: Annotated[list[dict], operator.add]
    publication: dict
    audit_passes: int
    escalations: list[dict]
    errors: Annotated[list[dict], operator.add]
    summary: str
    status: str
    stop_reason: str | None
    tokens: int
    started_at: float
    trace: Annotated[list[dict], operator.add]
    tasks: Annotated[list[dict], operator.add]  # tareas que se pasan los agentes, en orden
