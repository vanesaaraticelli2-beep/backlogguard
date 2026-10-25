"""Estado del grafo de la corrida (clase 11: State explícito y serializable).

El tablero viaja como JSON; los demás campos son tipos simples para poder guardarlos en SQLite.
`trace` se acumula (los nodos solo agregan); el resto de los campos se reemplaza.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class RunState(TypedDict, total=False):
    run_id: str
    objective: str
    board: dict
    plan: dict
    pending: list[str]
    reviewed: dict[str, dict]
    audit: dict
    publish_plan: dict
    audit_passes: int
    escalations: list[dict]
    errors: Annotated[list[dict], operator.add]
    summary: str
    status: str
    stop_reason: str | None
    tokens: int
    started_at: float
    trace: Annotated[list[dict], operator.add]
