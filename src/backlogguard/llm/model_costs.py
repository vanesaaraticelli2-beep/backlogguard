"""Modelos y costos por agente: lo que muestra la tarjeta del menú izquierdo (fuera del curso).

- Proporción entrada/salida de cada agente, recalculada desde las tareas de las corridas guardadas.
- Precio por millón de tokens *mezclado*: entrada y salida ponderadas por esa proporción, para comparar modelos
  con un solo número por agente.
- Elección del modelo por proyecto: se guarda en `<datos>/models.yaml` y tiene prioridad sobre `config/models.yaml`,
  que queda como valor por defecto.
- Lo + y lo − de cada modelo para cada rol (`config/model_notes.yaml`), textos fijos y versionados.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from backlogguard.board import AgentRole
from backlogguard.llm.model_config import ModelSpec, ModelsConfig, load_models_config


@dataclass(frozen=True)
class TokenMix:
    input_tokens: int
    output_tokens: int
    tasks: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def input_share(self) -> float:
        return self.input_tokens / self.total if self.total else DEFAULT_INPUT_SHARE

    @property
    def output_share(self) -> float:
        return 1 - self.input_share


DEFAULT_INPUT_SHARE = 0.9  # hasta que el agente tenga tareas medidas (las corridas reales dan entre 84% y 94%)
DEFAULT_MIX = TokenMix(0, 0, 0)


def token_mix(runs: Iterable[Iterable[dict]]) -> dict[AgentRole, TokenMix]:
    """Suma los tokens de entrada y salida de cada agente en todas las corridas (`task["target"]` es el agente)."""
    totals = {role: [0, 0, 0] for role in AgentRole}
    roles = {role.value: role for role in AgentRole}
    for tasks in runs:
        for task in tasks:
            role = roles.get(task.get("target", ""))
            entrada, salida = task.get("input_tokens", 0) or 0, task.get("output_tokens", 0) or 0
            if role is None or not (entrada or salida):
                continue
            row = totals[role]
            row[0] += entrada
            row[1] += salida
            row[2] += 1
    return {role: TokenMix(*row) for role, row in totals.items()}


def blended_price(mix: TokenMix, price: tuple[float, float] | None) -> float | None:
    """US$ por millón de tokens con la proporción del agente, o `None` si el modelo no tiene precio."""
    if price is None:
        return None
    return mix.input_share * price[0] + mix.output_share * price[1]


def model_options(pricing: dict[str, tuple[float, float]]) -> list[str]:
    """Modelos elegibles: los que tienen precio, de más barato a más caro."""
    return sorted(pricing, key=lambda model: (pricing[model][0] + pricing[model][1], model))


def provider_for(model: str) -> str:
    return "gemini" if model.startswith("gemini") else "anthropic"


NO_EFFORT = {"claude-haiku-4-5"}  # la API rechaza `effort` en estos modelos


def spec_for(model: str, effort: str | None) -> ModelSpec:
    """Especificación para un modelo elegido, conservando el esfuerzo del agente donde la API lo acepta."""
    provider = provider_for(model)
    keep = provider == "anthropic" and model not in NO_EFFORT
    return ModelSpec(provider=provider, model=model, effort=(effort or "medium") if keep else None)


def display_name(model: str) -> str:
    """`claude-opus-5-5` → «Opus 5.5»; `gemini-3.8-flash` → «Gemini Flash»."""
    if model.startswith("gemini"):
        return "Gemini Flash"
    parts = model.removeprefix("claude-").split("-")
    return f"{parts[0].capitalize()} {'.'.join(parts[1:])}".strip() if parts and parts[0] else model


# ---- elección por proyecto ----

def models_path(root: Path, data_dir: Path) -> Path:
    """La elección del proyecto si existe; si no, la configuración por defecto."""
    own = data_dir / "models.yaml"
    return own if own.is_file() else root / "config" / "models.yaml"


def load_effective_models(root: Path, data_dir: Path) -> ModelsConfig:
    return load_models_config(models_path(root, data_dir))


def save_models_config(config: ModelsConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"agents": {role.value: config.for_role(role).model_dump(exclude_none=True) for role in AgentRole}}
    header = "# Modelo por agente elegido para este proyecto desde la tarjeta «Modelos y costos».\n" \
             "# Tiene prioridad sobre config/models.yaml. Borrarlo vuelve a los valores por defecto.\n"
    path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


# ---- lo + y lo − ----

def load_notes(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def notes_for(notes: dict, role: AgentRole, model: str) -> tuple[list[str], list[str]]:
    """Lo + y lo − del modelo para ese rol; si el rol no tiene notas propias, las generales del modelo."""
    entry = ((notes.get("agentes") or {}).get(role.value) or {}).get(model) or (notes.get("generales") or {}).get(model) or {}
    return list(entry.get("mas") or []), list(entry.get("menos") or [])
