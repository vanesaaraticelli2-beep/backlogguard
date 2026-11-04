"""Limpieza de una preventa en PDF, solo por eliminación (fuera del curso).

Quita texto de plantilla y páginas enteras que la persona decide excluir, sin reescribir nada y sin usar un modelo.
Como solo elimina, toda frase que sobrevive figura textual en el PDF original, y las páginas conservan su número
(una cita «p. 31» sigue siendo la página 31 del PDF).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from backlogguard.rag.importers import ImportedSource, SourceImportError

PAGE_MARKER = re.compile(r"\[\[página (\d+)\]\]")
PLACEHOLDER_TITLES = {"stack tecnológico", "infraestructura", "migración de datos", "integraciones", "integraciones a desarrollar", "procesos automáticos"}
PLACEHOLDER_BODY = re.compile(r"(?i)^-?\s*(descripci[oó]n( de api que se desarrolla)?|ver slide de procesos autom[aá]ticos)\s*$")
TEMPLATE_LINE = re.compile(r"(?i)^\s*(feature|logo de cliente|seguinos en las redes sociales|www\.\S+|info@\S+|\+54[\d\s]+)\s*$")
MAX_HEADER_WORDS = 5  # una línea corta que se repite en muchas páginas es un encabezado, no contenido
MIN_HEADER_PAGES = 5


class PageSpecError(ValueError):
    pass


def parse_pages(spec: str | None, *, total: int | None = None) -> set[int]:
    """«1,2,4,35-39» → {1, 2, 4, 35, 36, 37, 38, 39}. Avisa si una página no existe o el rango está al revés."""
    pages: set[int] = set()
    for part in (spec or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", part)
        if not match:
            raise PageSpecError(f"No entiendo «{part}»: usá números y rangos como 1,2,35-39.")
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        if start < 1 or end < start:
            raise PageSpecError(f"El rango «{part}» no es válido.")
        pages.update(range(start, end + 1))
    if total is not None and (beyond := sorted(p for p in pages if p > total)):
        raise PageSpecError(f"El documento tiene {total} páginas; no existe la {beyond[0]}.")
    return pages


@dataclass
class PageReport:
    number: int
    words_before: int
    words_after: int
    status: str  # "excluida" | "limpiada" | "sin cambios" | "vacía"
    removed: list[str] = field(default_factory=list)


@dataclass
class Cleaned:
    text: str
    words: int
    pages: list[PageReport]

    @property
    def kept(self) -> list[int]:
        return [p.number for p in self.pages if p.status in ("limpiada", "sin cambios")]

    @property
    def excluded(self) -> list[int]:
        return [p.number for p in self.pages if p.status == "excluida"]


def split_pages(text: str) -> dict[int, str]:
    marks = list(PAGE_MARKER.finditer(text))
    if not marks:
        raise SourceImportError("Esta fuente no tiene páginas marcadas: la limpieza es solo para PDF importados.")
    return {
        int(mark.group(1)): text[mark.end() : marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
        for i, mark in enumerate(marks)
    }


def _norm(line: str) -> str:
    return " ".join(line.casefold().split())


def _template_pass(lines: list[str]) -> tuple[list[str], list[str]]:
    """Plantilla del PDF: marcas «FEATURE», títulos con su texto de relleno, pies de página y números sueltos."""
    kept, removed, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if _norm(line) in PLACEHOLDER_TITLES and PLACEHOLDER_BODY.match(following.strip()):
            removed += [line, following]
            i += 2
            continue
        if TEMPLATE_LINE.match(line) or (PLACEHOLDER_BODY.match(line.strip()) and line.strip().startswith("-")):
            removed.append(line)
        else:
            kept.append(line)
        i += 1
    while kept and re.fullmatch(r"\d{1,3}", kept[-1].strip()):  # número de diapositiva al pie
        removed.append(kept.pop())
    return kept, removed


def limpiar(
    text: str, excluir: set[int] | frozenset[int] = frozenset(), *, quitar_ruido: bool = True, quitar_encabezados: bool = False
) -> Cleaned:
    """Devuelve el texto sin las páginas excluidas y, si se pide, sin texto de plantilla.

    Los encabezados repetidos solo se quitan si se pide: a veces son rótulos con sentido («Requerimientos Funcionales»).
    """
    pages = split_pages(text)
    if beyond := sorted(p for p in excluir if p not in pages):
        raise PageSpecError(f"Esta fuente no tiene la página {beyond[0]} (tiene {len(pages)} con texto).")
    work: dict[int, tuple[list[str], list[str]]] = {}
    for number, body in pages.items():
        if number in excluir:
            continue
        lines = body.splitlines()
        work[number] = _template_pass(lines) if quitar_ruido else (lines, [])

    if quitar_encabezados:  # líneas cortas idénticas en muchas páginas (solo entre las que se conservan)
        counts = Counter(_norm(line) for kept, _ in work.values() for line in set(kept) if line.strip())
        repeated = {
            key for key, n in counts.items()
            if n >= MIN_HEADER_PAGES and len(key.split()) <= MAX_HEADER_WORDS and not re.search(r"[\d•✓\-:]", key)
        }
        for number, (kept, removed) in list(work.items()):
            work[number] = ([l for l in kept if _norm(l) not in repeated], removed + [l for l in kept if _norm(l) in repeated])

    reports, parts = [], []
    for number, body in pages.items():
        before = len(body.split())
        if number in excluir:
            reports.append(PageReport(number, before, 0, "excluida"))
            continue
        kept, removed = work[number]
        cleaned = "\n".join(kept).strip()
        after = len(cleaned.split())
        if not cleaned:
            reports.append(PageReport(number, before, 0, "vacía", removed))
            continue
        reports.append(PageReport(number, before, after, "limpiada" if removed else "sin cambios", removed))
        parts.append(f"[[página {number}]]\n{cleaned}")
    return Cleaned("\n\n".join(parts) + "\n", sum(r.words_after for r in reports), reports)


def informe_markdown(cleaned: Cleaned, *, titulo: str = "Informe de limpieza") -> str:
    before = sum(p.words_before for p in cleaned.pages)
    lines = [
        f"# {titulo}",
        "",
        f"- Páginas: {len(cleaned.pages)} · conservadas: {len(cleaned.kept)} · excluidas: {len(cleaned.excluded)}",
        f"- Palabras: {before:,} → {cleaned.words:,} ({(1 - cleaned.words / before):.0%} menos)" if before else "- Sin texto",
        "- Solo se eliminó texto: lo que quedó figura textual en el PDF original y las páginas conservan su número.",
        "",
        "| Página | Palabras antes | Palabras después | Qué pasó | Líneas quitadas |",
        "|---|---|---|---|---|",
    ]
    for p in cleaned.pages:
        lines.append(f"| {p.number} | {p.words_before} | {p.words_after} | {p.status} | {len(p.removed) or ''} |")
    removed = Counter(l.strip() for p in cleaned.pages for l in p.removed if l.strip())
    if removed:
        lines += ["", "## Líneas quitadas (con cuántas veces)", ""] + [f"- ({n}×) {text}" for text, n in removed.most_common()]
    return "\n".join(lines) + "\n"


def aplicar(
    imported: ImportedSource, excluir: set[int] | frozenset[int] = frozenset(), *, quitar_ruido: bool = True, quitar_encabezados: bool = False
) -> tuple[ImportedSource, Cleaned]:
    """Una `ImportedSource` de PDF ya limpia, lista para guardar, y el detalle de lo que se quitó."""
    cleaned = limpiar(imported.text, excluir, quitar_ruido=quitar_ruido, quitar_encabezados=quitar_encabezados)
    if not cleaned.kept:
        raise SourceImportError("Con esas exclusiones no queda ninguna página con texto.")
    warnings = [w for w in imported.warnings if "casi sin texto" not in w]
    warnings.append(
        f"Limpieza: {len(cleaned.excluded)} página(s) excluida(s) y {sum(len(p.removed) for p in cleaned.pages)} línea(s) de plantilla quitadas; "
        f"{imported.words:,} → {cleaned.words:,} palabras. Se conservaron las páginas {_ranges(cleaned.kept)}."
    )
    return ImportedSource(text=cleaned.text, layout=imported.layout, words=cleaned.words, pages=imported.pages, warnings=warnings), cleaned


def _ranges(numbers: list[int]) -> str:
    out, start = [], None
    for i, n in enumerate(numbers):
        if start is None:
            start = n
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            out.append(str(start) if start == n else f"{start}-{n}")
            start = None
    return ", ".join(out)


def guardar_informe(cleaned: Cleaned, path: str | Path, *, titulo: str = "Informe de limpieza") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(informe_markdown(cleaned, titulo=titulo), encoding="utf-8")
    return path
