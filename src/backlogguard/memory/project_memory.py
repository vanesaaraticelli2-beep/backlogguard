"""Memoria del proyecto: decisiones vigentes y preguntas pendientes.

Capa fina sobre `MemoryStore` (clase 10). Fuera del curso: los tipos `decision` y
`pregunta_pendiente` y esta fachada, necesarios para las tools del Auditor
(`consultar_decisiones_vigentes`, `registrar_decision_aprobada`). Solo se escribe
con aprobación humana: `approved_by` alimenta el campo `confirmed` del Write Gate.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from backlogguard.memory.store import MemoryCandidate, MemoryScope, MemoryStore

TEAM_USER_ID = "factory"
DECISION = "decision"
OPEN_QUESTION = "pregunta_pendiente"
_ALL = 10_000


class ProjectMemory:
    def __init__(self, db_path: str | Path, project_id: str):
        self.store = MemoryStore(db_path)
        self.scope = MemoryScope(user_id=TEAM_USER_ID, project_id=project_id)

    def _candidate(self, kind: str, key: str, value: dict[str, Any], source: str, approved_by: str | None):
        return MemoryCandidate(
            kind=kind,
            key=key,
            value={**value, "approved_by": approved_by},
            source=source,
            confirmed=bool(approved_by),
            durable=True,
        )

    def register_decision(
        self,
        key: str,
        decision: str,
        *,
        decided_on: date,
        speaker: str,
        authority: str,
        source: str,
        quote: str,
        approved_by: str | None,
        supersedes: str | None = None,
    ) -> str:
        """Registra una decisión aprobada. Con `supersedes`, la anterior queda como histórica."""
        value = {
            "decision": decision,
            "decided_on": decided_on.isoformat(),
            "speaker": speaker,
            "authority": authority,
            "quote": quote,
        }
        return self.store.write(
            scope=self.scope,
            candidate=self._candidate(DECISION, key, value, source, approved_by),
            supersedes=supersedes,
        )

    def current_decisions(self, query: str | None = None) -> list[dict[str, Any]]:
        return self.store.retrieve(scope=self.scope, query=query, kinds={DECISION}, limit=_ALL)

    def decision_history(self, key: str) -> list[dict[str, Any]]:
        """Todas las versiones de una decisión (vigente y reemplazadas), de la más nueva a la más vieja."""
        return [
            item
            for item in self.store.list_scope(self.scope, include_inactive=True)
            if item["kind"] == DECISION and item["key"] == key and item["status"] != "deleted"
        ]

    def register_open_question(
        self, key: str, question: str, *, source: str, approved_by: str | None
    ) -> str:
        return self.store.write(
            scope=self.scope,
            candidate=self._candidate(OPEN_QUESTION, key, {"question": question}, source, approved_by),
        )

    def open_questions(self) -> list[dict[str, Any]]:
        return self.store.retrieve(scope=self.scope, kinds={OPEN_QUESTION}, limit=_ALL)

    def resolve_question(self, memory_id: str) -> None:
        self.store.delete(memory_id, scope=self.scope)
