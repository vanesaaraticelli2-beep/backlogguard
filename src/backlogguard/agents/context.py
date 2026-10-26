"""Presupuesto de contexto y compactación determinística del historial (fuera del curso).

Cada paso del ciclo reenvía al modelo todas las observaciones anteriores, así que el gasto crece con los pasos.
Acá se acota sin perder trazabilidad:

- Solo las últimas `window` observaciones viajan completas; las anteriores se reducen a un resumen fijo por tipo de
  herramienta. El resumen lo arma el código con campos que ya estaban en la observación (nunca un modelo): no agrega
  texto, solo recorta, y conserva los ids de fragmentos.
- Las observaciones precalculadas (el expediente del Crítico y del Auditor) no se compactan: son la base de su veredicto.
- La traza y el estado guardan siempre la observación completa; compactar afecta solo al prompt.
- Cada agente tiene un tope de caracteres de prompt (`config/context_budget.yaml`). Si se supera, se compacta más
  (ventana de 1, luego de 0) y después se recortan las observaciones largas; el paso queda registrado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "context_budget.yaml"
PREVIEW_CHARS = 120
FALLBACK_CHARS = 300
MARKER = "[compactada: el texto completo se vuelve a pedir con la misma herramienta]"


@dataclass(frozen=True)
class ContextLimits:
    window: int = 2  # observaciones recientes que viajan completas
    max_prompt_chars: int = 120_000


def load_limits(role: str, path: Path = CONFIG_PATH) -> ContextLimits:
    if not path.is_file():
        return ContextLimits()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    row = (data.get("context") or {}).get(role) or {}
    return ContextLimits(
        window=int(row.get("window", ContextLimits.window)),
        max_prompt_chars=int(row.get("max_prompt_chars", ContextLimits.max_prompt_chars)),
    )


def _preview(text: object) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= PREVIEW_CHARS else flat[:PREVIEW_CHARS] + "…"


def _fragments(rows: list) -> list[dict]:
    kept = []
    for row in rows:
        entry = {key: row[key] for key in ("chunk_id", "reunion", "pagina", "orador") if row.get(key) is not None}
        if "texto" in row:
            entry["texto"] = _preview(row["texto"])
        kept.append(entry)
    return kept


def digest(tool: str, content: str) -> str:
    """Resumen fijo de una observación antigua. Solo recorta o selecciona; no escribe nada nuevo."""
    try:
        data = json.loads(content)
    except ValueError:
        data = None
    if tool in ("buscar_en_fuentes", "buscar_contraevidencia") and isinstance(data, list):
        return json.dumps({"fragmentos": _fragments(data), "nota": MARKER}, ensure_ascii=False)
    if tool == "evaluar_dor_invest" and isinstance(data, dict):
        item = data.get("item", {})
        return json.dumps(
            {"item": item.get("id"), "titulo": item.get("titulo"), "controles_fallidos": [c for c in data.get("controles", []) if not c.get("ok")]},
            ensure_ascii=False,
        )
    if tool == "verificar_cita" and isinstance(data, list):
        return json.dumps({"citas_fallidas": [c for c in data if not c.get("ok")], "citas_revisadas": len(data)}, ensure_ascii=False)
    if tool == "comparar_con_preventa" and isinstance(data, dict):
        return json.dumps(
            {
                "items_analizados": [i.get("id") for i in data.get("items", [])],
                "preventa_analizada": [c.get("chunk_id") for c in data.get("preventa", [])],
                "reuniones_analizadas": [c.get("chunk_id") for c in data.get("reuniones", [])],
                "nota": MARKER,
            },
            ensure_ascii=False,
        )
    if tool == "detectar_contradicciones" and isinstance(data, list):
        pairs = [
            {"anterior": p.get("anterior", {}).get("chunk_id"), "posterior": p.get("posterior", {}).get("chunk_id"), "similitud": p.get("similitud")}
            for p in data
        ]
        return json.dumps({"pares_analizados": pairs, "nota": MARKER}, ensure_ascii=False)
    if len(content) <= FALLBACK_CHARS:
        return content
    return content[:FALLBACK_CHARS] + "… " + MARKER


# `redactar_historia` y los errores son cortos: viajan completos aunque sean antiguos.
ALWAYS_FULL = {"redactar_historia", "delegar_tarea", "escalar_a_persona", "consultar_decisiones_vigentes"}


def compactable(tool: str | None, ok: bool, pinned: bool) -> bool:
    return bool(tool) and tool not in ALWAYS_FULL and ok and not pinned
