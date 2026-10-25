"""Backlog simulado que se comporta como Azure DevOps: ids numerados, versiones, etiquetas y padres.

Se guarda en un archivo JSON para que persista entre corridas (`path=None` lo deja en memoria).
`failures` inyecta fallos en las escrituras, para probar la idempotencia y los fallos parciales:
- "create_error": la creación falla antes de aplicarse;
- "create_lost_response": la creación se aplica pero la respuesta se pierde (resultado ambiguo);
- "update_error": la actualización falla.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from backlogguard.integrations.gateway import BacklogError, BacklogTimeout, ConflictError, WorkItem

FIRST_ID = 1001


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


class SimulatedBacklog:
    def __init__(self, path: str | Path | None = None, failures: list[str] | None = None):
        self.path = Path(path) if path else None
        self.failures = list(failures or [])
        self._items: dict[int, WorkItem] = {}
        self._next_id = FIRST_ID
        self.writes = 0  # cantidad de escrituras aplicadas (útil para probar que el dry-run no escribe)
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = {item["id"]: WorkItem(**item) for item in data["items"]}
            self._next_id = data["next_id"]

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"next_id": self._next_id, "items": [item.model_dump() for item in self._items.values()]}
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self._items, self._next_id, self.writes = {}, FIRST_ID, 0
        self._save()

    def _fail(self, kind: str) -> bool:
        if self.failures and self.failures[0] == kind:
            self.failures.pop(0)
            return True
        return False

    # ---- lectura ----

    def search(self, *, text: str | None = None, tag: str | None = None) -> list[WorkItem]:
        found = list(self._items.values())
        if tag is not None:
            found = [item for item in found if tag in item.tags]
        if text:
            needle = _fold(text)
            found = [item for item in found if needle in _fold(item.title)]
        return [item.model_copy(deep=True) for item in found]

    def get(self, work_item_id: int) -> WorkItem | None:
        item = self._items.get(work_item_id)
        return item.model_copy(deep=True) if item else None

    # ---- escritura ----

    def create(self, *, type, title, description, acceptance_criteria, tags, parent_id):
        if self._fail("create_error"):
            raise BacklogError("falla simulada al crear")
        if parent_id is not None and parent_id not in self._items:
            raise BacklogError(f"el work item padre #{parent_id} no existe")
        item = WorkItem(
            id=self._next_id,
            type=type,
            title=title,
            description=description,
            acceptance_criteria=list(acceptance_criteria),
            tags=list(tags),
            parent_id=parent_id,
        )
        self._items[item.id] = item
        self._next_id += 1
        self.writes += 1
        self._save()
        if self._fail("create_lost_response"):
            raise BacklogTimeout("se perdió la respuesta de la creación")
        return item.model_copy(deep=True)

    def _versioned(self, work_item_id: int, expected_rev: int) -> WorkItem:
        item = self._items.get(work_item_id)
        if item is None:
            raise BacklogError(f"el work item #{work_item_id} no existe")
        if item.rev != expected_rev:
            raise ConflictError(f"#{work_item_id}: versión {item.rev}, se esperaba {expected_rev}")
        return item

    def update(self, work_item_id, *, expected_rev, title, description, acceptance_criteria, tags):
        if self._fail("update_error"):
            raise BacklogError("falla simulada al actualizar")
        item = self._versioned(work_item_id, expected_rev)
        item.title, item.description = title, description
        item.acceptance_criteria, item.tags = list(acceptance_criteria), list(tags)
        item.rev += 1
        self.writes += 1
        self._save()
        return item.model_copy(deep=True)

    def link_parent(self, work_item_id, parent_id, *, expected_rev):
        item = self._versioned(work_item_id, expected_rev)
        if parent_id not in self._items:
            raise BacklogError(f"el work item padre #{parent_id} no existe")
        item.parent_id = parent_id
        item.rev += 1
        self.writes += 1
        self._save()
        return item.model_copy(deep=True)

    # ---- datos de demostración ----

    def seed_demo(self) -> None:
        """Work items cargados a mano por otra persona (sin etiquetas de BacklogGuard)."""
        for title in ("Ingreso al portal con SSO corporativo", "Pantalla de ayuda y preguntas frecuentes"):
            self.create(
                type="User Story",
                title=title,
                description="Cargado manualmente antes de BacklogGuard.",
                acceptance_criteria=[],
                tags=[],
                parent_id=None,
            )
