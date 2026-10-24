"""Snapshots versionados del tablero por `run_id`.

Sigue el patrón `JsonCheckpointStore` de la clase 11: JSON durable con control de
versión optimista (`StaleCheckpointError`). No sustituye un compare-and-swap
transaccional entre procesos concurrentes.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from backlogguard.board.models import Board


class BoardRunState(BaseModel):
    run_id: str = Field(min_length=1)
    checkpoint_version: int = 0
    board: Board = Field(default_factory=Board)


class StaleCheckpointError(RuntimeError):
    """El snapshot que se quiere guardar no es el último persistido."""


class BoardCheckpointStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def save(self, state: BoardRunState) -> BoardRunState:
        """Persiste el estado y avanza su `checkpoint_version`.

        Raises:
            StaleCheckpointError: Si el store ya avanzó a otra versión.
        """
        data = json.loads(self.path.read_text(encoding="utf-8"))
        current = data.get(state.run_id)
        current_version = current["version"] if current else 0

        if state.checkpoint_version != current_version:
            raise StaleCheckpointError(
                f"snapshot viejo: state={state.checkpoint_version}, store={current_version}"
            )

        new_version = current_version + 1
        saved = state.model_copy(update={"checkpoint_version": new_version})
        data[state.run_id] = {"version": new_version, "state": saved.model_dump(mode="json")}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return saved

    def load(self, run_id: str) -> BoardRunState:
        """Recupera y valida el último estado persistido de una corrida.

        Raises:
            KeyError: Si el `run_id` nunca fue persistido.
        """
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if run_id not in data:
            raise KeyError(f"Run inexistente: {run_id}")
        return BoardRunState.model_validate(data[run_id]["state"])
