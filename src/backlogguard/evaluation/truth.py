"""Respuestas conocidas de un caso: qué requisitos y qué hallazgos debería encontrar el sistema."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def normalizar(text: str) -> str:
    """Minúsculas, sin tildes y con espacios simples, para comparar textos sin que importen esas diferencias."""
    plain = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(plain.casefold().split())


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Esperado(_Strict):
    id: str
    texto: str
    grupos: list[list[str]] = Field(min_length=1, description="Basta con que se cumpla un grupo; un grupo se cumple si aparecen todas sus palabras")
    tipo: str = ""
    tipos_aceptados: list[str] = Field(default_factory=list, description="Tipos de hallazgo que valen; vacío = cualquiera")

    def especificidad(self, text: str) -> int:
        """Cuántas palabras tiene el grupo más largo que se cumple (0 = no coincide). Gana el elemento más específico."""
        plain = normalizar(text)
        return max((len(group) for group in self.grupos if all(normalizar(word) in plain for word in group)), default=0)

    def coincide(self, text: str) -> bool:
        return self.especificidad(text) > 0


class Inyeccion(_Strict):
    texto: str
    obedecida_si: list[list[str]]


class Verdad(_Strict):
    nombre: str
    descripcion: str = ""
    nota_de_emparejamiento: str = ""
    requisitos: list[Esperado]
    opcionales: list[Esperado] = Field(default_factory=list)
    hallazgos: list[Esperado]
    toleradas: list[Esperado] = Field(default_factory=list)
    inyeccion: Inyeccion | None = None


def cargar_verdad(path: str | Path) -> Verdad:
    return Verdad.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
