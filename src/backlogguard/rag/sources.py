"""Biblioteca de fuentes: carpeta controlada por la aplicación.

Fuera del curso. Cada fuente es un `.md` con metadata en un encabezado YAML
(`source_name`, `source_type`, `source_date`) y turnos "Orador: texto". El modelo pide
una fuente por `document_id` (el nombre del archivo) y nunca una ruta: no puede leer
archivos arbitrarios ni inventar la metadata.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from backlogguard.board import EVIDENCE_TYPES, SourceType

DOCUMENT_ID = re.compile(r"^[a-z0-9_-]{1,60}$")
_FRONT_MATTER = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_type: SourceType
    source_date: date
    layout: Literal["turnos", "dialogo", "paginas"] = "turnos"
    fingerprint: str | None = None  # huella del texto cuando se importó; las fuentes de ejemplo no la tienen


class SourceDocument(BaseModel):
    document_id: str
    metadata: SourceMetadata
    text: str
    fingerprint: str = ""  # huella del texto que hay hoy en el archivo
    fingerprint_ok: bool | None = None  # ¿coincide con la guardada? None si la fuente no guarda huella


def fingerprint(text: str) -> str:
    """Huella del contenido: cambia si cambia una sola palabra; no depende de espacios al borde."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ImportStatus:
    """Qué pasaría al importar: la fuente es nueva, no cambia nada, o cambia algo (y qué)."""

    status: Literal["nueva", "sin_cambios", "cambio"]
    new_fingerprint: str
    previous_fingerprint: str | None = None
    changes: list[str] = field(default_factory=list)


def slugify(name: str, *, limit: int = 60) -> str:
    """Identificador seguro para una fuente: minúsculas, sin acentos, solo letras, números, guiones y guion bajo."""
    folded = unicodedata.normalize("NFKD", name.casefold())
    ascii_name = "".join(char for char in folded if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")[:limit].strip("_")
    return slug or "fuente"


class SourceNotFound(LookupError):
    """La fuente pedida no existe en la biblioteca."""


class SourceUnchanged(Exception):
    """La fuente que se quiere importar es idéntica a la que ya está: no hay nada que escribir."""


class SourceChangeNeedsConfirmation(Exception):
    """La fuente ya existe y cambió: reemplazarla exige una confirmación explícita."""


class SourceLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list_ids(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.md") if DOCUMENT_ID.match(path.stem))

    def describe(self) -> list[tuple[str, SourceMetadata]]:
        """Id y metadata de cada fuente (sin cargar el texto en el prompt)."""
        return [(document_id, self.load(document_id).metadata) for document_id in self.list_ids()]

    def inventory(self) -> list[dict]:
        """Registro de las fuentes tal como están hoy: lo que se anota en cada corrida."""
        rows = []
        for document_id in self.list_ids():
            document = self.load(document_id)
            rows.append(
                {
                    "id": document_id,
                    "name": document.metadata.source_name,
                    "type": document.metadata.source_type.value,
                    "date": document.metadata.source_date.isoformat(),
                    "layout": document.metadata.layout,
                    "fingerprint": document.fingerprint,
                    "fingerprint_ok": document.fingerprint_ok,
                    "words": len(document.text.split()),
                    "role": "evidencia" if document.metadata.source_type in EVIDENCE_TYPES else "linea_base",
                }
            )
        return rows

    def import_status(self, document_id: str, metadata: SourceMetadata, text: str) -> ImportStatus:
        """Compara lo que se quiere importar con lo que ya hay, sin escribir nada."""
        new = fingerprint(text)
        if not (self.root / f"{document_id}.md").is_file():
            return ImportStatus("nueva", new)
        try:
            current = self.load(document_id)
        except (ValueError, OSError):  # un archivo ilegible se trata como distinto
            return ImportStatus("cambio", new, None, ["el archivo actual no se puede leer"])
        changes = []
        if current.fingerprint != new:
            changes.append("contenido")
        for label, before, after in (
            ("nombre", current.metadata.source_name, metadata.source_name),
            ("fecha", current.metadata.source_date, metadata.source_date),
            ("tipo", current.metadata.source_type, metadata.source_type),
            ("formato", current.metadata.layout, metadata.layout),
        ):
            if before != after:
                changes.append(label)
        return ImportStatus("cambio" if changes else "sin_cambios", new, current.fingerprint, changes)

    def save(self, document_id: str, metadata: SourceMetadata, text: str, *, replace: bool = False) -> ImportStatus:
        """Importa con control de cambios: lo idéntico no se escribe y lo que cambió pide confirmación."""
        status = self.import_status(document_id, metadata, text)
        if status.status == "sin_cambios":
            if self.load(document_id).metadata.fingerprint is None:  # fuente anterior a las huellas: se completa el registro
                self.write(document_id, metadata, text, overwrite=True)
                raise SourceUnchanged(
                    f"Sin cambios: «{metadata.source_name}» ya estaba cargada con el mismo contenido. "
                    f"Era anterior a las huellas y se registró la suya ({status.new_fingerprint}); el contenido no se tocó."
                )
            raise SourceUnchanged(
                f"Sin cambios: «{metadata.source_name}» ya estaba cargada con el mismo contenido (huella {status.new_fingerprint}). No se escribió nada."
            )
        if status.status == "cambio" and not replace:
            if status.previous_fingerprint == status.new_fingerprint:
                detail = f"El contenido es el mismo (huella {status.new_fingerprint})."
            else:
                detail = f"Huella {status.previous_fingerprint or 'ilegible'} → {status.new_fingerprint}."
            raise SourceChangeNeedsConfirmation(
                f"«{metadata.source_name}» ya existe y cambió ({', '.join(status.changes)}). {detail} Confirmá el reemplazo para continuar."
            )
        self.write(document_id, metadata, text, overwrite=status.status == "cambio")
        return status

    def delete(self, document_id: str) -> bool:
        if not DOCUMENT_ID.match(document_id):
            raise SourceNotFound(f"document_id inválido: {document_id!r}")
        path = self.root / f"{document_id}.md"
        existed = path.is_file()
        path.unlink(missing_ok=True)
        return existed

    def write(self, document_id: str, metadata: SourceMetadata, text: str, *, overwrite: bool = False) -> Path:
        """Guarda una fuente como `.md` con su metadata en el encabezado, dentro de la biblioteca (y nada más)."""
        if not DOCUMENT_ID.match(document_id):
            raise SourceNotFound(f"document_id inválido: {document_id!r}")
        path = self.root / f"{document_id}.md"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Ya existe la fuente {document_id!r}.")
        self.root.mkdir(parents=True, exist_ok=True)
        header = yaml.safe_dump(
            {
                "source_name": metadata.source_name,
                "source_type": metadata.source_type.value,
                "source_date": metadata.source_date.isoformat(),
                "layout": metadata.layout,
                "fingerprint": fingerprint(text),
            },
            allow_unicode=True,
            sort_keys=False,
        )
        path.write_text(f"---\n{header}---\n{text}", encoding="utf-8")
        return path

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
        actual = fingerprint(match["body"])
        verified = None if metadata.fingerprint is None else metadata.fingerprint == actual
        return SourceDocument(
            document_id=document_id, metadata=metadata, text=match["body"], fingerprint=actual, fingerprint_ok=verified
        )
