"""Presupuesto de una corrida (config/budgets.yaml). Fuera del curso, igual que models.yaml y policy.yaml."""
from __future__ import annotations

import time
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backlogguard.graph.failures import account_blocked


class RunBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tokens: int = Field(default=400_000, gt=0)
    max_items_to_review: int = Field(default=12, gt=0)
    max_seconds: float = Field(default=1800.0, gt=0)
    max_parallel_reviews: int = Field(default=1, ge=1, le=8)  # ítems que el Crítico revisa a la vez (1 = en fila, como antes)


class BudgetsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunBudget = RunBudget()


def load_budget(path: str | Path) -> RunBudget:
    with Path(path).open("r", encoding="utf-8") as handle:
        return BudgetsConfig.model_validate(yaml.safe_load(handle)).run


def over_budget(state: dict, budget: RunBudget, *, now: float | None = None, check_time: bool = True) -> str | None:
    """Motivo por el que la corrida debe cortar, o `None` si puede seguir.

    `check_time=False` se usa después de las pausas humanas: esperar a una persona no gasta presupuesto.
    """
    if any(account_blocked(str(error.get("error", ""))) for error in state.get("errors", [])):
        return "cuenta"  # límite de gasto, saldo o clave: cada llamada siguiente fallaría igual
    if state.get("tokens", 0) >= budget.max_tokens:
        return "tokens"
    if len(state.get("reviewed", {})) >= budget.max_items_to_review and state.get("pending"):
        return "items"
    started = state.get("started_at")
    if check_time and started is not None and (now if now is not None else time.time()) - started >= budget.max_seconds:
        return "tiempo"
    return None
