"""Chunking de fuentes (clase 5 del curso).

`normalize_text`, `stable_chunk_id`, `fixed_size_chunks` y `recursive_chunks` siguen el curso.
Adaptación: `transcript_chunks` respeta los turnos de orador ("Orador: texto") y conserva
quién habló y dónde, para que cada cita sea textual y atribuible.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_TURN = re.compile(r"^(?P<speaker>[^:\n]{1,40}):\s*(?P<text>\S.*)$")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def stable_chunk_id(document_id: str, strategy: str, index: int, text: str) -> str:
    digest = hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()[:8]
    return f"{document_id}:{strategy}:{index:03d}:{digest}"


def fixed_size_chunks(text: str, *, target_words: int = 55, overlap_words: int = 10) -> list[str]:
    if target_words <= 0:
        raise ValueError("target_words debe ser positivo")
    if not 0 <= overlap_words < target_words:
        raise ValueError("overlap_words inválido")

    words = normalize_text(text).split()
    if not words:
        return []

    step = target_words - overlap_words
    result: list[str] = []
    for start in range(0, len(words), step):
        piece = words[start : start + target_words]
        # Evita dejar un último chunk demasiado corto.
        if len(piece) < 10 and result:
            result[-1] = normalize_text(result[-1] + " " + " ".join(piece))
            break
        result.append(" ".join(piece))
    return result


def recursive_chunks(text: str, *, target_words: int = 55, overlap_words: int = 8) -> list[str]:
    paragraphs = [
        normalize_text(part) for part in re.split(r"\n\s*\n", text) if normalize_text(part)
    ] or [normalize_text(text)]

    units: list[str] = []
    for paragraph in paragraphs:
        sentences = [
            normalize_text(sentence)
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
            if normalize_text(sentence)
        ]
        units.extend(sentences or [paragraph])

    chunks: list[str] = []
    current: list[str] = []
    for unit in units:
        candidate = " ".join(current + [unit]).strip()
        if current and len(candidate.split()) > target_words:
            chunks.append(" ".join(current))
            # Corrección al curso: con overlap 0, `[-0:]` devolvía todo el chunk anterior.
            overlap = " ".join(" ".join(current).split()[-overlap_words:]) if overlap_words else ""
            current = [overlap, unit] if overlap else [unit]
        else:
            current.append(unit)
    if current:
        chunks.append(" ".join(current))
    return [normalize_text(chunk) for chunk in chunks if chunk.strip()]


def split_turns(text: str) -> list[dict[str, Any]]:
    """Separa una transcripción en turnos {speaker, text, start, end}.

    Una línea sin "Orador:" continúa el turno anterior; un texto sin ningún orador
    se devuelve como un único turno sin orador.
    """
    turns: list[dict[str, Any]] = []
    position = 0
    for line in text.splitlines(keepends=True):
        start, position = position, position + len(line)
        stripped = line.strip()
        if not stripped:
            continue
        match = _TURN.match(stripped)
        if match:
            turns.append({
                "speaker": match["speaker"].strip(),
                "text": match["text"].strip(),
                "start": start,
                "end": position,
            })
        elif turns:
            turns[-1]["text"] = normalize_text(turns[-1]["text"] + " " + stripped)
            turns[-1]["end"] = position
        else:
            turns.append({"speaker": None, "text": stripped, "start": start, "end": position})
    return turns


def transcript_chunks(
    text: str, *, target_words: int = 55, overlap_words: int = 8
) -> list[dict[str, Any]]:
    """Un chunk por turno de orador; los turnos largos se parten con `recursive_chunks`."""
    chunks: list[dict[str, Any]] = []
    for turn in split_turns(text):
        pieces = (
            recursive_chunks(turn["text"], target_words=target_words, overlap_words=overlap_words)
            if len(turn["text"].split()) > target_words
            else [turn["text"]]
        )
        for piece in pieces:
            chunks.append({
                "text": piece,
                "speaker": turn["speaker"],
                "start": turn["start"],
                "end": turn["end"],
            })
    return chunks


PAGE_MARKER = re.compile(r"^\[\[página (\d+)\]\]\s*$", re.MULTILINE)
PAGE_TARGET_WORDS = 140
MIN_PAGE_CHUNK_WORDS = 8
DIALOGUE_MAX_WORDS = 50


def page_chunks(text: str, *, target_words: int = PAGE_TARGET_WORDS) -> list[dict[str, Any]]:
    """Fragmentos de un documento por páginas (marcadas con `[[página N]]`): por oraciones, sin orador."""
    marks = list(PAGE_MARKER.finditer(text))
    if not marks:
        return [{"text": piece, "speaker": None, "start": 0, "end": len(text), "page": None}
                for piece in recursive_chunks(text, target_words=target_words, overlap_words=0)]
    chunks: list[dict[str, Any]] = []
    for position, mark in enumerate(marks):
        end = marks[position + 1].start() if position + 1 < len(marks) else len(text)
        body = text[mark.end():end]
        for piece in recursive_chunks(body, target_words=target_words, overlap_words=0):
            if len(piece.split()) >= MIN_PAGE_CHUNK_WORDS:  # un título suelto («Nuestra Propuesta 4») no es contenido
                chunks.append({"text": piece, "speaker": None, "start": mark.end(), "end": end, "page": int(mark[1])})
    return chunks


def dialogue_chunks(text: str, *, max_words: int = DIALOGUE_MAX_WORDS) -> list[dict[str, Any]]:
    """Agrupa intervenciones seguidas (hasta `max_words`) para que una pregunta y su respuesta queden juntas.

    Cada línea del fragmento conserva «Nombre (rol): …», y `speaker` lista a quienes hablan en él.
    """
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def close() -> None:
        if current:
            speakers = list(dict.fromkeys(turn["speaker"] for turn in current if turn["speaker"]))
            chunks.append({
                "text": " ".join(f"{t['speaker']}: {t['text']}" if t["speaker"] else t["text"] for t in current),
                "speaker": ", ".join(speakers) or None,
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "page": None,
            })
            current.clear()

    for turn in split_turns(text):
        words = len(turn["text"].split())
        if words > max_words:  # una intervención larga se parte aparte y conserva su orador
            close()
            for piece in recursive_chunks(turn["text"], target_words=max_words, overlap_words=0):
                chunks.append({"text": f"{turn['speaker']}: {piece}" if turn["speaker"] else piece,
                               "speaker": turn["speaker"], "start": turn["start"], "end": turn["end"], "page": None})
            continue
        if current and sum(len(t["text"].split()) for t in current) + words > max_words:
            close()
        current.append(turn)
    close()
    return chunks


def build_chunks(
    document_id: str,
    text: str,
    metadata: dict[str, Any],
    *,
    target_words: int = 55,
    overlap_words: int = 8,
    strategy: str | None = None,
) -> list[dict[str, Any]]:
    """Chunks listos para indexar: id estable, texto y metadata de la fuente.

    La estrategia sale de `metadata["layout"]`: «turnos» (un fragmento por intervención, el formato de las
    fuentes de ejemplo), «dialogo» (intervenciones seguidas juntas) o «paginas» (documentos como un PDF).
    """
    layout = metadata.get("layout", "turnos")
    strategy = strategy or layout
    if layout == "paginas":
        pieces = page_chunks(text)
    elif layout == "dialogo":
        pieces = dialogue_chunks(text)
    else:
        pieces = transcript_chunks(text, target_words=target_words, overlap_words=overlap_words)
    chunks = []
    for index, piece in enumerate(pieces):
        page = piece.get("page")
        chunks.append({
            "chunk_id": stable_chunk_id(document_id, strategy, index, piece["text"]),
            "document_id": document_id,
            "text": piece["text"],
            "source": metadata.get("source_name", document_id),
            "page": page,
            "metadata": {
                **metadata,
                "document_id": document_id,
                "speaker": piece["speaker"],
                "start": piece["start"],
                "end": piece["end"],
                "page": page,
            },
        })
    return chunks
