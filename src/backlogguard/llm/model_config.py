"""Carga y validación de config/models.yaml (modelo por agente).

Extensión fuera del curso: el curso fija el modelo con una variable de entorno.
Acá cada agente tiene el suyo y el Crítico debe ser independiente del productor
(Agente de Requerimientos): otro proveedor o, al menos, otro modelo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backlogguard.board import AgentRole

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["anthropic", "gemini", "fake"]
    model: str = Field(min_length=1)
    effort: Effort | None = None

    @model_validator(mode="after")
    def _effort_only_for_claude(self) -> ModelSpec:
        if self.effort is not None and self.provider != "anthropic":
            raise ValueError("effort solo aplica a modelos de Anthropic")
        return self


class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agents: dict[AgentRole, ModelSpec]

    @model_validator(mode="after")
    def _validate(self) -> ModelsConfig:
        missing = set(AgentRole) - set(self.agents)
        if missing:
            raise ValueError(f"faltan modelos para: {sorted(role.value for role in missing)}")
        producer = self.agents[AgentRole.REQUERIMIENTOS]
        critic = self.agents[AgentRole.CRITICO]
        if (critic.provider, critic.model) == (producer.provider, producer.model):
            raise ValueError(
                "el Crítico debe ser independiente del productor: "
                "no puede usar el mismo proveedor y modelo que Requerimientos"
            )
        return self

    def for_role(self, role: AgentRole) -> ModelSpec:
        return self.agents[role]


def load_models_config(path: str | Path) -> ModelsConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        return ModelsConfig.model_validate(yaml.safe_load(handle))
