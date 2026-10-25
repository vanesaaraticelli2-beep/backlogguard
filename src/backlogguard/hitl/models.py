"""Contratos de las decisiones humanas (clase 11: ProposedAction / HumanDecision / args_hash).

Adaptación: `DecisionRequest` cumple el papel de `ProposedAction`. Cada pedido lleva versión y hash del
contenido que la persona vio, y la decisión debe devolverlos: una decisión vieja o adulterada se rechaza.
Una edición crea una versión nueva que hay que aprobar otra vez.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DecisionKind = Literal["approve", "edit", "reject"]
RequestKind = Literal["alcance", "item", "plan"]
HASH_LENGTH = 24


def canonical_hash(value: Any) -> str:
    """Huella SHA-256 estable de un valor JSON-serializable (claves ordenadas)."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:HASH_LENGTH]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_id: str
    quote: str
    source_name: str
    source_date: str
    speaker: str | None = None
    page: int | None = None


class DecisionRequest(BaseModel):
    """Lo que una persona debe decidir. El hash cubre todo menos la versión."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    kind: RequestKind
    reason: str
    decides: str
    ref: str
    title: str
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    editable: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    args_hash: str = ""

    def content(self) -> dict:
        return {
            "request_id": self.request_id,
            "kind": self.kind,
            "reason": self.reason,
            "decides": self.decides,
            "ref": self.ref,
            "title": self.title,
            "summary": self.summary,
            "payload": self.payload,
        }

    def sealed(self) -> DecisionRequest:
        """Copia con el hash calculado sobre su contenido actual."""
        return self.model_copy(update={"args_hash": canonical_hash(self.content())})

    def next_version(self, edited: dict[str, Any]) -> DecisionRequest:
        """Versión nueva con los campos editados; la aprobación anterior no se hereda."""
        return self.model_copy(update={"payload": {**self.payload, **edited}, "version": self.version + 1}).sealed()


class HumanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: DecisionKind
    actor: str = Field(min_length=2)
    actor_role: str = Field(min_length=2)
    request_id: str
    request_version: int = Field(ge=1)
    args_hash: str
    edited: dict[str, Any] | None = None
    comment: str = ""


class DecisionRecord(BaseModel):
    """Entrada del registro de auditoría: qué se decidió, quién, cuándo y si se aceptó."""

    request_id: str
    version: int
    args_hash: str
    decision: str
    actor: str
    actor_role: str
    at: str = Field(default_factory=utc_now_iso)
    comment: str = ""
    accepted: bool = True
    error: str | None = None
