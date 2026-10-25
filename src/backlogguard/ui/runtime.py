"""Un controlador de corrida por configuración, compartido por todas las sesiones del proceso.

Streamlit vuelve a ejecutar el script en cada interacción, pero el módulo se importa una sola vez: acá vive
el estado que debe sobrevivir (la corrida en curso). No depende de Streamlit, así se comparte con las pruebas.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from backlogguard.llm import Settings
from backlogguard.ui.controller import RunController

ROOT = Path(os.environ.get("BACKLOGGUARD_ROOT", Path(__file__).resolve().parents[3]))
DEFAULT_RECORDING = ROOT / "evals" / "recordings" / "demo_acme.json"

_controllers: dict[tuple[str, str, bool], RunController] = {}
_lock = threading.Lock()


def get_controller(data_dir: str, replay: str, live: bool) -> RunController:
    key = (data_dir, replay, live)
    with _lock:
        if key not in _controllers:
            settings = Settings.from_env(ROOT / ".env").model_copy(update={"live_mode": live})
            _controllers[key] = RunController(ROOT, settings, Path(data_dir), Path(replay) if replay else None)
        return _controllers[key]


def make_controller() -> RunController:
    """Controlador según el entorno: modelos reales con LIVE_MODE=1; si no, la corrida grabada (modo demo)."""
    settings = Settings.from_env(ROOT / ".env")
    data_dir = os.environ.get("BACKLOGGUARD_DATA", str(ROOT / "data"))
    recording = Path(os.environ.get("BACKLOGGUARD_RECORDING", str(DEFAULT_RECORDING)))
    replay = "" if settings.live_mode or not recording.exists() else str(recording)
    return get_controller(data_dir, replay, settings.live_mode)
