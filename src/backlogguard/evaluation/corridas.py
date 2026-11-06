"""Comparar corridas guardadas: cuánto objetó el Crítico, cuántas quedaron sin consenso y cuánto costó cada historia (fuera del curso).

Sirve para medir una mejora: se corre lo mismo antes y después y se comparan los números. Todo sale del estado guardado
de la corrida (sus tareas, con el modelo y los tokens de cada una); no se llama a ningún modelo.

Con `requisitos` se comparan solo las historias de esos requisitos. El gasto de redactar se registra por tanda y no
por historia, así que en ese caso se prorratea por la cantidad de historias.
"""
from __future__ import annotations

from collections import Counter

from backlogguard.llm.metering import estimate_cost

STAGES = {"redactar": "redacción", "revisar": "revisión (Crítico)", "corregir": "corrección"}


def _cost(task: dict, pricing: dict) -> float:
    return estimate_cost(task.get("model") or "", task.get("input_tokens", 0), task.get("output_tokens", 0), pricing) or 0.0


def metrics(name: str, state: dict, pricing: dict, requisitos: set[str] | None = None) -> dict:
    """Los números de una corrida (o de sus historias de `requisitos`)."""
    items = (state.get("board") or {}).get("items", {})
    keep = {i for i, item in items.items() if not requisitos or item.get("requirement_id") in requisitos}
    tasks = state.get("tasks", [])
    every_review = [t for t in tasks if t["kind"] == "revisar" and t.get("ref") in keep]
    reviews = [t for t in every_review if t.get("status") != "fallida"]  # una revisión que falló no dio veredicto
    first = [t for t in reviews if t.get("round") == 1]
    objected = [t for t in first if str(t.get("detail", "")).startswith("objetado")]
    last = {t["ref"]: t for t in reviews}  # la última revisión de cada historia: si terminó objetada, no hubo consenso
    no_consensus = sum(1 for t in last.values() if str(t.get("detail", "")).startswith("objetado"))
    share = len(keep) / len(items) if items else 0.0
    cost = Counter()
    tokens = 0
    for task in tasks:
        stage = STAGES.get(task["kind"])
        if stage is None:
            continue
        if task["kind"] == "redactar":
            weight = share  # por tanda: se prorratea
        elif task.get("ref") in keep:
            weight = 1.0
        else:
            continue
        cost[stage] += _cost(task, pricing) * weight
        tokens += int((task.get("input_tokens", 0) + task.get("output_tokens", 0)) * weight)
    total = sum(cost.values())
    return {
        "corrida": name,
        "historias": len(keep),
        "objetadas_ronda_1": len(objected),
        "revisadas_ronda_1": len(first),
        "tasa_objecion_ronda_1": len(objected) / len(first) if first else None,
        "revisiones_fallidas": len(every_review) - len(reviews),
        "sin_consenso": no_consensus,  # aunque después una persona lo haya aprobado
        "correcciones": sum(1 for t in tasks if t["kind"] == "corregir" and t.get("ref") in keep),
        "tokens": tokens,
        "costo_usd": total,
        "costo_por_historia": total / len(keep) if keep else None,
        "costo_por_etapa": dict(cost),
        "prorrateado": bool(requisitos),
    }


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _usd(value: float | None) -> str:
    return "—" if value is None else f"US$ {value:.2f}"


def table(rows: list[dict]) -> str:
    """Tabla en Markdown para el informe."""
    lines = [
        "| Corrida | Historias | Objetadas en la 1ª ronda | Sin consenso | Correcciones | Tokens | Costo | Por historia |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['corrida']} | {r['historias']} | {r['objetadas_ronda_1']} de {r['revisadas_ronda_1']} ({_pct(r['tasa_objecion_ronda_1'])}) | "
            f"{r['sin_consenso']} | {r['correcciones']} | {r['tokens']:,} | {_usd(r['costo_usd'])} | {_usd(r['costo_por_historia'])} |"
        )
    if any(r["prorrateado"] for r in rows):
        lines.append("")
        lines.append("El gasto de redactar se registra por tanda: al filtrar por requisitos se prorratea por historia.")
    return "\n".join(lines)
