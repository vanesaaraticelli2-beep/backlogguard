"""Anonimización de las fuentes antes de guardarlas (fuera del curso).

Reemplaza nombres de empresas y de personas, y datos de contacto, por alias fijos, de modo que ningún texto que llega a un
modelo identifique al cliente. El diccionario vive en un archivo local (`evals/real/anonimizacion.yaml`, ignorado por git)
y es el mismo para todas las fuentes, así un alias significa siempre lo mismo y las contradicciones entre documentos se
siguen viendo. Como se anonimiza ANTES de guardar, las citas se verifican contra el texto anonimizado.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from backlogguard.rag.importers import ImportedSource

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
HANDLE = re.compile(r"(?<!\w)@[\w.]{3,}")
PHONE = re.compile(r"\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}")
LONG_NUMBER = re.compile(r"\b\d{7,11}\b")  # DNI, CUIT, CBU parciales: no se reemplaza, se avisa
GENERIC = ((EMAIL, "correo@ejemplo.com"), (URL, "www.ejemplo.com"), (HANDLE, "@usuario"), (PHONE, "+00 0 0000 0000"))


class DictionaryError(ValueError):
    pass


def _plain(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(stripped.casefold().split())


def _pattern(term: str) -> str:
    """El término sin importar mayúsculas, tildes ni saltos de línea entre sus palabras (los PDF parten los nombres)."""
    accents = {"a": "aáàä", "e": "eéèë", "i": "iíìï", "o": "oóòö", "u": "uúùü"}
    bare = "".join(c for c in unicodedata.normalize("NFD", term) if unicodedata.category(c) != "Mn")
    parts = []
    for word in bare.split():
        parts.append("".join(f"[{accents[c.lower()]}{accents[c.lower()].upper()}]" if c.lower() in accents else re.escape(c) for c in word))
    return r"\s+".join(parts)


@dataclass(frozen=True)
class Regla:
    buscar: tuple[str, ...]
    por: str


@dataclass(frozen=True)
class Diccionario:
    reglas: tuple[Regla, ...]

    def __post_init__(self) -> None:
        for regla in self.reglas:
            if not regla.por.strip() or not regla.buscar:
                raise DictionaryError("Cada regla necesita términos a buscar y un alias.")
        searched = {_plain(t) for r in self.reglas for t in r.buscar}
        for regla in self.reglas:
            if clash := next((t for t in searched if t and re.search(rf"(?<!\w){re.escape(t)}(?!\w)", _plain(regla.por))), None):
                raise DictionaryError(f"El alias «{regla.por}» contiene el término «{clash}», que también se reemplaza: elegí otro alias.")

    @property
    def alias(self) -> dict[str, str]:
        return {_plain(t): r.por for r in self.reglas for t in r.buscar}

    @property
    def regex(self) -> re.Pattern | None:
        terms = sorted({t for r in self.reglas for t in r.buscar}, key=len, reverse=True)
        if not terms:
            return None
        return re.compile(r"(?<!\w)(?:" + "|".join(_pattern(t) for t in terms) + r")(?!\w)", re.IGNORECASE)


def cargar(path: str | Path) -> Diccionario:
    """Lee el diccionario: `reemplazos: [{buscar: [..], por: ".."}]`."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise DictionaryError(f"No se pudo leer el diccionario de anonimización: {exc}") from exc
    rows = data.get("reemplazos")
    if not isinstance(rows, list) or not rows:
        raise DictionaryError("El diccionario necesita una lista «reemplazos» con al menos una regla.")
    rules = []
    for row in rows:
        terms = row.get("buscar") if isinstance(row, dict) else None
        terms = [terms] if isinstance(terms, str) else terms
        if not terms or not isinstance(row.get("por"), str):
            raise DictionaryError("Cada reemplazo lleva «buscar» (uno o varios términos) y «por» (el alias).")
        rules.append(Regla(tuple(str(t) for t in terms), row["por"]))
    return Diccionario(tuple(rules))


@dataclass
class Resultado:
    text: str
    reemplazos: Counter = field(default_factory=Counter)  # alias → veces
    genericos: Counter = field(default_factory=Counter)  # correos, direcciones web, teléfonos
    avisos: list[str] = field(default_factory=list)
    revisar: list[str] = field(default_factory=list)  # palabras con mayúscula que se repiten: posibles nombres sin cubrir


def anonimizar(text: str, dictionary: Diccionario) -> Resultado:
    result = Resultado(text)
    alias, regex = dictionary.alias, dictionary.regex

    def swap(match: re.Match) -> str:
        replacement = alias[_plain(match.group(0))]
        result.reemplazos[replacement] += 1
        return replacement

    out = regex.sub(swap, text) if regex else text
    for pattern, replacement in GENERIC:
        out, n = pattern.subn(replacement, out)
        if n:
            result.genericos[replacement] += n
    result.text = out
    if numbers := LONG_NUMBER.findall(out):
        result.avisos.append(f"Hay {len(numbers)} número(s) largo(s) (¿DNI, CUIT, CBU?) que no se reemplazaron: revisalos.")
    result.revisar = _candidates(out, set(alias.values()))
    return result


def _candidates(text: str, known: set[str]) -> list[str]:
    """Palabras con mayúscula que se repiten y nunca aparecen en minúscula: suelen ser nombres propios que faltan en el diccionario."""
    lowercase = {w for w in re.findall(r"\b[a-záéíóúñ]{3,}\b", text)}
    capitalized = Counter(w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ]{3,}\b", text) if w.lower() not in lowercase)
    skip = {w for alias in known for w in alias.split()} | {"Nota"}  # «Nota de la minuta» es el rótulo que agrega el importador
    return [f"{w} ({n}×)" for w, n in capitalized.most_common(40) if n >= 2 and w not in skip]


def resumen(result: Resultado) -> str:
    parts = [f"{alias} ({n}×)" for alias, n in result.reemplazos.most_common()]
    parts += [f"{alias} ({n}×, dato de contacto)" for alias, n in result.genericos.most_common()]
    return "; ".join(parts) or "no se reemplazó nada"


def aplicar(imported: ImportedSource, dictionary: Diccionario) -> tuple[ImportedSource, Resultado]:
    """La fuente importada, anonimizada (texto, oradores y encabezado detectado), y el detalle de lo reemplazado."""
    result = anonimizar(imported.text, dictionary)
    speakers = [anonimizar(s, dictionary).text for s in imported.speakers]
    detected = {k: anonimizar(v, dictionary).text for k, v in imported.detected.items()}
    note = f"Anonimizada: {resumen(result)}."
    return replace(imported, text=result.text, speakers=speakers, detected=detected, warnings=[*imported.warnings, note, *result.avisos]), result


def anonimizar_nombre(name: str, dictionary: Diccionario) -> str:
    """El nombre de la fuente también llega a los modelos (aparece en las citas): se anonimiza igual."""
    return anonimizar(name, dictionary).text
