"""Importadores de fuentes propias: preventa en PDF y transcripción de una reunión en texto.

Fuera del curso. Convierten el documento al formato de fuentes de BacklogGuard (texto con metadata) y avisan de
lo que podría degradar las citas. No hay OCR: un PDF que es una imagen escaneada se rechaza con un mensaje claro.

- PDF → texto por página, marcado con `[[página N]]` (la cita muestra la página).
- Transcripción → una línea por intervención, `Nombre (rol): texto`. El encabezado (Proyecto, Participantes,
  Fecha) no es parte de la conversación: se usa para dar rol a cada orador. Lo que no lo dice una persona
  (títulos, notas del que tomó la minuta) se conserva como `Nota de la minuta`.
"""
from __future__ import annotations

import re
from html import unescape
import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_PAGES = 150
MAX_WORDS = 60_000
MIN_PDF_WORDS = 40
NOTE_SPEAKER = "Nota de la minuta"
MAX_TITLE_WORDS = 3
PAGE_MARKER = re.compile(r"^\[\[página (\d+)\]\]\s*$", re.MULTILINE)

_TIMESTAMP = r"(?:[\[(]?\d{1,2}:\d{2}(?::\d{2})?[\])]?\s*[-–]?\s*)?"
_TURN = re.compile(rf"^\s*{_TIMESTAMP}(?P<speaker>[^\W\d][^:\n]{{0,60}}?)\s*:\s*(?P<text>\S.*)$")
_PARTICIPANT = re.compile(r"^\s*(?P<name>[^:()\n]{2,40}?)\s*\((?P<role>[^)\n]{2,60})\)\s*$")
_HEADER = re.compile(r"^\s*(?P<key>Proyecto|Fecha|Reuni[oó]n|Tema|Asunto)\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
# Estilo de Zoom/Teams: «Nombre Apellido 00:12» en una línea y lo que dijo en las siguientes.
_STAMPED_SPEAKER = re.compile(r"^\s*(?P<speaker>[^\W\d][^:\n\d]{1,40}?)\s+[\[(]?\d{1,2}:\d{2}(?::\d{2})?[\])]?\s*$")
_PARTICIPANTS_TITLE = re.compile(r"^\s*Participantes\s*:?\s*$", re.IGNORECASE)
# WebVTT (Teams, Zoom, Meet): el orador viene en <v Nombre>…</v> o como «Nombre: texto»; el id del fragmento puede ser «guid/12-3»,
# donde 12 es la intervención y 3 la parte (las partes de una frase larga se intercalan con las de otros oradores).
_VTT_TIME = re.compile(r"^(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->")
_VTT_VOICE = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>(.*?)(?:</v>|$)", re.DOTALL)
_VTT_PREFIX = re.compile(r"^\s*([^\W\d][^:\n]{0,60}?)\s*:\s*(\S.*)$", re.DOTALL)
_VTT_UTTERANCE = re.compile(r"^(?:.*/)?(\d+)-(\d+)$")


class SourceImportError(ValueError):
    """El documento no se puede importar (formato, tamaño o contenido)."""


@dataclass
class ImportedSource:
    text: str
    layout: str  # "paginas" | "dialogo"
    words: int
    pages: int | None = None
    speakers: list[str] = field(default_factory=list)
    detected: dict[str, str] = field(default_factory=dict)  # encabezado de la transcripción: proyecto, fecha…
    warnings: list[str] = field(default_factory=list)


def _words(text: str) -> int:
    return len(text.split())


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


# ---------------------------------------------------------------- PDF


def import_pdf(source: bytes | str | Path) -> ImportedSource:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else source
    if len(data) > MAX_PDF_BYTES:
        raise SourceImportError(f"El PDF pesa {len(data) // (1024 * 1024)} MB; el máximo es {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise SourceImportError("El PDF está protegido con contraseña: quitale la protección y volvé a subirlo.")
        count = len(reader.pages)
        if count > MAX_PAGES:
            raise SourceImportError(f"El PDF tiene {count} páginas; el máximo es {MAX_PAGES}.")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except SourceImportError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError) as exc:
        raise SourceImportError(f"No se pudo leer el PDF: {exc}") from exc

    total = sum(_words(text) for text in pages)
    if total < MIN_PDF_WORDS:
        raise SourceImportError(
            "El PDF casi no tiene texto: probablemente es una imagen escaneada. "
            "El reconocimiento de texto en imágenes (OCR) no está incluido."
        )
    if total > MAX_WORDS:
        raise SourceImportError(f"El PDF tiene {total} palabras; el máximo es {MAX_WORDS}.")

    warnings = []
    blank = [number for number, text in enumerate(pages, 1) if _words(text) < 5]
    if blank:
        warnings.append(f"{len(blank)} página(s) casi sin texto (portadas o imágenes): {blank[:12]}.")
    body = "\n\n".join(f"[[página {number}]]\n{_drop_page_number(text)}" for number, text in enumerate(pages, 1) if text)
    warnings.append(
        "Las tablas, columnas y diagramas de un PDF se leen como texto lineal y pueden salir desordenados: revisá la vista previa."
    )
    return ImportedSource(text=body + "\n", layout="paginas", words=total, pages=count, warnings=warnings)


# Texto que los PDF generados por PowerPoint o Word agregan solo: no es contenido del documento.
_NOISE = re.compile(
    r"(?i)^\s*(icono|descripci[oó]n|generada|autom[aá]ticamente|seguinos en las redes sociales)(\s+(icono|descripci[oó]n|generada|autom[aá]ticamente))*\s*$"
)


def _drop_page_number(text: str) -> str:
    lines = text.splitlines()
    if lines and re.fullmatch(r"\d{1,3}", lines[0].strip()):
        lines = lines[1:]
    cleaned = [line for line in lines if not _NOISE.match(line)]
    return "\n".join(cleaned).strip()


# ---------------------------------------------------------------- transcripción


def decode_text(data: bytes) -> str:
    if len(data) > MAX_TEXT_BYTES:
        raise SourceImportError(f"El archivo pesa {len(data) // 1024} KB; el máximo es {MAX_TEXT_BYTES // 1024} KB.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def import_transcript(source: bytes | str | Path) -> ImportedSource:
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        text = decode_text(Path(source).read_bytes())
    elif isinstance(source, bytes):
        text = decode_text(source)
    else:
        text = source
    if is_vtt(text):
        text = vtt_to_dialogue(text)
    lines = _join_stamped_speakers([line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")])
    if _words(text) > MAX_WORDS:
        raise SourceImportError(f"La transcripción tiene {_words(text)} palabras; el máximo es {MAX_WORDS}.")

    participants, header, start = _read_header(lines)
    known = {_fold(name.split()[0]): f"{name} ({role})" for name, role in participants}  # por nombre de pila
    blocks = _paragraphs(lines[start:])

    turns: list[tuple[str | None, str]] = []  # (orador o None para una nota, texto)
    unknown: set[str] = set()
    for block in blocks:
        first = _TURN.match(block[0])
        speaker = first["speaker"].strip() if first else None
        label = None
        if speaker is not None:
            label = known.get(_fold(speaker.split()[0])) if known else (speaker if len(speaker.split()) <= 5 else None)
            if label is None and known and len(speaker.split()) <= 4:
                unknown.add(speaker)
                label = speaker
        if label is not None:
            body = " ".join([first["text"].strip(), *(line.strip() for line in block[1:])])
            turns.append((label, body))
        else:
            note = " ".join(line.strip() for line in block)
            if turns and turns[-1][0] is None:
                turns[-1] = (None, f"{turns[-1][1]} {note}")  # títulos y notas seguidos forman una sola nota
            else:
                turns.append((None, note))

    titles = [t for t in turns if t[0] is None and _words(t[1]) <= MAX_TITLE_WORDS]
    turns = [t for t in turns if t not in titles]  # «Gestión de usuarios» o «Requerimiento identificado» solos no aportan
    spoken = [turn for turn in turns if turn[0] is not None]
    warnings = []
    if titles:
        warnings.append(f"Se ignoraron {len(titles)} título(s) suelto(s) de la minuta.")
    if not spoken:
        warnings.append(
            "No encontré intervenciones con el formato «Nombre: texto». El texto se importa como un bloque sin oradores: "
            "las citas no van a poder atribuirse a una persona."
        )
    if not participants:
        warnings.append("No encontré el bloque «Participantes»: los oradores quedan sin rol.")
    if unknown:
        warnings.append(f"Oradores que no figuran en «Participantes»: {sorted(unknown)}.")
    if not spoken:
        body_text = " ".join(" ".join(block) for block in blocks)
        rendered = f"{NOTE_SPEAKER}: {body_text}\n" if body_text else ""
    else:
        rendered = "\n".join(f"{speaker or NOTE_SPEAKER}: {body}" for speaker, body in turns) + "\n"
    speakers = sorted({speaker for speaker, _ in turns if speaker})
    if not rendered.strip():
        raise SourceImportError("La transcripción está vacía.")
    return ImportedSource(
        text=rendered, layout="dialogo", words=_words(rendered), speakers=speakers, detected=header, warnings=warnings
    )


def is_vtt(text: str) -> bool:
    return text.lstrip("\ufeff \t\r\n").startswith("WEBVTT")


def vtt_to_dialogue(text: str) -> str:
    """Convierte un WebVTT en «Orador: texto», una línea por intervención y en el orden en que empezaron a hablar.

    Se descartan el encabezado, las notas, los estilos y las líneas de tiempo. Los fragmentos de una misma intervención
    (mismo número en el id) se unen aunque otro orador los interrumpa; sin ese id se unen los seguidos del mismo orador.
    """
    blocks = re.split(r"\n\s*\n", text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n"))
    cues: list[tuple[float, str | None, str, str | None, int]] = []  # (inicio, orador, texto, intervención, parte)
    for block in blocks[1:]:
        lines = block.strip("\n").split("\n")
        at = next((i for i, line in enumerate(lines) if _VTT_TIME.match(line.strip())), None)
        if at is None or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        hours, minutes, seconds, millis = _VTT_TIME.match(lines[at].strip()).groups()
        start = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
        payload = "\n".join(lines[at + 1 :])
        speaker: str | None = None
        voice = _VTT_VOICE.search(payload)
        if voice:
            speaker, payload = unescape(voice.group(1)).strip(), voice.group(2)
        else:
            plain = _VTT_PREFIX.match(re.sub(r"<[^>]+>", "", payload))
            if plain and len(plain.group(1).split()) <= 5:
                speaker, payload = plain.group(1).strip(), plain.group(2)
        said = " ".join(unescape(re.sub(r"<[^>]+>", "", payload)).split())
        if not said:
            continue
        ident = _VTT_UTTERANCE.match(lines[at - 1].strip()) if at > 0 else None
        cues.append((start, speaker, said, ident.group(1) if ident else None, int(ident.group(2)) if ident else len(cues)))

    turns: dict[str, dict] = {}
    ordered: list[dict] = []
    for start, speaker, said, utterance, part in cues:
        if utterance is not None and utterance in turns:
            turn = turns[utterance]
            turn["start"] = min(turn["start"], start)
        elif utterance is None and ordered and ordered[-1].get("loose") and ordered[-1]["speaker"] == speaker:
            turn = ordered[-1]
        else:
            turn = {"start": start, "speaker": speaker, "parts": [], "loose": utterance is None}
            ordered.append(turn)
            if utterance is not None:
                turns[utterance] = turn
        turn["parts"].append((part, said))
    ordered.sort(key=lambda t: t["start"])
    merged: list[dict] = []
    for turn in ordered:  # intervenciones seguidas del mismo orador forman una sola
        if merged and merged[-1]["speaker"] == turn["speaker"]:
            merged[-1]["parts"] += turn["parts"]
        else:
            merged.append({**turn, "parts": list(turn["parts"])})
    rendered = []
    for turn in merged:
        body = " ".join(said for _, said in sorted(turn["parts"], key=lambda p: p[0]))
        rendered.append(f"{turn['speaker']}: {body}" if turn["speaker"] else body)
    return "\n".join(rendered) + "\n"


def _join_stamped_speakers(lines: list[str]) -> list[str]:
    """Convierte «Nombre 00:12» + texto en «Nombre: texto» (una línea por intervención)."""
    joined: list[str] = []
    index = 0
    while index < len(lines):
        found = _STAMPED_SPEAKER.match(lines[index])
        if found and index + 1 < len(lines) and lines[index + 1].strip():
            spoken: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() and not _STAMPED_SPEAKER.match(lines[index]):
                spoken.append(lines[index].strip())
                index += 1
            joined.append(f"{found['speaker'].strip()}: {' '.join(spoken)}")
            continue
        joined.append(lines[index])
        index += 1
    return joined


def _read_header(lines: list[str]) -> tuple[list[tuple[str, str]], dict[str, str], int]:
    """Participantes, datos del encabezado y la línea donde empieza la conversación."""
    participants: list[tuple[str, str]] = []
    header: dict[str, str] = {}
    index, limit = 0, min(len(lines), 40)
    while index < limit:
        line = lines[index]
        if _PARTICIPANTS_TITLE.match(line):
            index += 1
            while index < limit and (not lines[index].strip() or _PARTICIPANT.match(lines[index])):
                found = _PARTICIPANT.match(lines[index])
                if found:
                    participants.append((found["name"].strip(), found["role"].strip()))
                index += 1
            continue
        meta = _HEADER.match(line)
        if meta and not _participant_turn(line, participants):
            header[_fold(meta["key"])] = meta["value"]
            index += 1
            continue
        looks_like_title = _words(line) <= 12 and _TURN.match(line) is None
        if line.strip() and (participants or header) and looks_like_title and index < 6:
            index += 1  # título suelto del documento, solo si ya se reconoció un encabezado
            continue
        if not line.strip():
            index += 1
            continue
        break
    return participants, header, index


def _participant_turn(line: str, participants: list[tuple[str, str]]) -> bool:
    found = _TURN.match(line)
    return bool(found) and _fold(found["speaker"].split()[0]) in {_fold(name.split()[0]) for name, _ in participants}


def _paragraphs(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        # una línea nueva con «Nombre:» abre otra intervención aunque no haya una línea en blanco
        if current and _TURN.match(line) and _TURN.match(current[0]):
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def estimate(words: int) -> dict[str, int]:
    """Tamaño aproximado de una fuente: palabras y tokens (en español, ~1,4 tokens por palabra)."""
    return {"words": words, "tokens": round(words * 1.4)}
