"""Biblioteca de fuentes: carpeta controlada por la aplicación.

Fuera del curso. Cada fuente es un `.md` con metadata en un encabezado YAML
(`source_name`, `source_type`, `source_date`) y turnos "Orador: texto". El modelo pide
una fuente por `document_id` (el nombre del archivo) y nunca una ruta: no puede leer
archivos arbitrarios ni inventar la metadata.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from backlogguard.board import SourceType

DOCUMENT_ID = re.compile(r"^[a-z0-9_-]{1,60}$")
_FRONT_MATTER = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_type: SourceType
    source_date: date


class SourceDocument(BaseModel):
    document_id: str
    metadata: SourceMetadata
    text: str


class SourceNotFound(LookupError):
    """La fuente pedida no existe en la biblioteca."""


class SourceLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list_ids(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.md") if DOCUMENT_ID.match(path.stem))

    def describe(self) -> list[tuple[str, SourceMetadata]]:
        """Id y metadata de cada fuente (sin cargar el texto en el prompt)."""
        return [(document_id, self.load(document_id).metadata) for document_id in self.list_ids()]

    def load(self, document_id: str) -> SourceDocument:
        if not DOCUMENT_ID.match(document_id):
            raise SourceNotFound(f"document_id inválido: {document_id!r}")
        path = self.root / f"{document_id}.md"
        if not path.is_file():
            raise SourceNotFound(f"No existe la fuente {document_id!r}")
        match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
        if not match:
            raise ValueError(f"{path.name}: falta el encabezado de metadata")
        metadata = SourceMetadata.model_validate(yaml.safe_load(match["meta"]))
        return SourceDocument(document_id=document_id, metadata=metadata, text=match["body"])
