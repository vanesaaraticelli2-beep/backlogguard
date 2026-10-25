"""Presupuesto de una corrida (config/budgets.yaml). Fuera del curso, igual que models.yaml y policy.yaml."""
from __future__ import annotations

import time
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RunBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tokens: int = Field(default=400_000, gt=0)
    max_items_to_review: int = Field(default=12, gt=0)
    max_seconds: float = Field(default=1800.0, gt=0)


class BudgetsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunBudget = RunBudget()


def load_budget(path: str | Path) -> RunBudget:
    with Path(path).open("r", encoding="utf-8") as handle:
        return BudgetsConfig.model_validate(yaml.safe_load(handle)).run


def over_budget(state: dict, budget: RunBudget, *, now: float | None = None) -> str | None:
    """Motivo por el que la corrida debe cortar, o `None` si puede seguir."""
    if state.get("tokens", 0) >= budget.max_tokens:
        return "tokens"
    if len(state.get("reviewed", {})) >= budget.max_items_to_review and state.get("pending"):
        return "items"
    started = state.get("started_at")
    if started is not None and (now if now is not None else time.time()) - started >= budget.max_seconds:
        return "tiempo"
    return None
