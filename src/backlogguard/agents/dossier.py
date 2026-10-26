"""Interruptor del expediente precalculado (fuera del curso).

Los controles fijos del Crítico y del Auditor los corre el código antes de la primera decisión del modelo
(ver `initial_calls` en `loop.py`), en vez de gastar un paso del modelo por cada uno. El interruptor vive en
`config/context_budget.yaml`; un argumento explícito tiene prioridad sobre el archivo.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "context_budget.yaml"


def dossier_enabled(role: str, override: bool | None = None, path: Path = CONFIG_PATH) -> bool:
    if override is not None:
        return override
    if not path.is_file():
        return True
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return bool(config.get("precalculated_dossier", {}).get(role, True))
