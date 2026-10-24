"""Carga y validación de config/policy.yaml.

Extensión fuera del curso: el curso define la política en código (`ToolPolicy`).
Este YAML la declara de forma legible y un test exige que coincida con el código,
que sigue siendo la autoridad.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backlogguard.board import AgentRole


class RolePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kinds: list[str] = Field(min_length=1)
    tools: list[str] = Field(min_length=1)


class PauseRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str
    decides: str


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: dict[AgentRole, RolePolicy]
    pauses: list[PauseRule]


def load_policy_config(path: str | Path) -> PolicyConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        return PolicyConfig.model_validate(yaml.safe_load(handle))
