"""Registro de publicaciones (SQLite): qué se publicó, con qué clave y bajo qué plan.

Sirve para la idempotencia: antes de escribir se anota la intención (`intent`) y al terminar se marca
`done`. Si el proceso se corta entre ambas, el reintento reconoce el resultado ambiguo. También guarda
los planes armados, para poder auditarlos o reanudar la publicación desde otro proceso.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicationLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS publications ("
                "key TEXT PRIMARY KEY, item_id TEXT NOT NULL, remote_id INTEGER, status TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            conn.execute("CREATE TABLE IF NOT EXISTS plans (hash TEXT PRIMARY KEY, json TEXT NOT NULL, created_at TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_intent(self, key: str, item_id: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO publications(key, item_id, remote_id, status, updated_at) VALUES (?, ?, NULL, 'intent', ?) "
                "ON CONFLICT(key) DO UPDATE SET status = CASE WHEN status = 'done' THEN 'done' ELSE 'intent' END, updated_at = excluded.updated_at",
                (key, item_id, _now()),
            )

    def mark_done(self, key: str, remote_id: int) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE publications SET remote_id = ?, status = 'done', updated_at = ? WHERE key = ?",
                (remote_id, _now(), key),
            )

    def get(self, key: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM publications WHERE key = ?", (key,)).fetchone()
        return dict(row) if row else None

    def save_plan(self, plan_hash: str, plan_json: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO plans(hash, json, created_at) VALUES (?, ?, ?)", (plan_hash, plan_json, _now())
            )

    def load_plan(self, plan_hash: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT json FROM plans WHERE hash = ?", (plan_hash,)).fetchone()
        return row["json"] if row else None
