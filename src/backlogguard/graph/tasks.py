"""Registro de las tareas que se pasan los agentes en una corrida.

Fuera del curso. Cada vez que un agente le encarga trabajo a otro (o a una persona) se anota una tarea:
quién la pidió, quién la hizo, sobre qué ítem, cuántos tokens costó y cómo terminó. Es un registro
de lectura: no decide nada, sirve para ver el backlog de la corrida y dónde se gasta.
"""
from __future__ import annotations

from collections import defaultdict

from backlogguard.llm.metering import Usage, estimate_cost, load_pricing

KIND_TITLES = {
    "planificar": "Planificar la corrida",
    "redactar": "Redactar historias",
    "revisar": "Revisar un ítem",
    "corregir": "Corregir un ítem",
    "auditar": "Auditar el proyecto",
    "armar_plan": "Armar el plan de publicación",
    "resumir": "Resumir la corrida",
    "decidir": "Decisión de una persona",
}
PARTIES = {
    "persona": "Persona",
    "supervisor": "Supervisor",
    "requerimientos": "Requerimientos",
    "critico": "Crítico",
    "auditor": "Auditor",
    "integracion": "Integración",
}


class TaskLog:
    """Anota las tareas de un nodo con ids que siguen a las ya registradas en la corrida."""

    def __init__(self, existing: int = 0):
        self._start = existing
        self.tasks: list[dict] = []

    def add(
        self,
        origin: str,
        target: str,
        kind: str,
        *,
        ref: str | None = None,
        round: int | None = None,
        detail: str = "",
        status: str = "hecha",
        stop_reason: str = "",
        usage: Usage | None = None,
        model: str = "",
        steps: int = 0,
        corrections: int = 0,
        rejected: int = 0,
    ) -> dict:
        usage = usage or Usage()
        seq = self._start + len(self.tasks) + 1
        task = {
            "id": f"T-{seq:03d}",
            "seq": seq,
            "origin": origin,
            "target": target,
            "kind": kind,
            "ref": ref,
            "round": round,
            "detail": " ".join(detail.split())[:4000],
            "status": status,
            "stop_reason": stop_reason,
            "tokens": usage.tokens,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "llm_calls": usage.calls,
            "model": model,
            "steps": steps,
            "corrections": corrections,  # correcciones que salieron bien
            "rejected": rejected,  # intentos de corregir otra vez el mismo ítem, rechazados por el tope
        }
        self.tasks.append(task)
        return task


def describe_outcome(outcome: dict) -> dict:
    """Pasos, correcciones logradas e intentos rechazados por el tope, leídos de la traza de un agente."""
    trace = outcome.get("trace", [])
    observations = [e for e in trace if e.get("event") == "observation" and e.get("tool") == "redactar_historia"]
    return {
        "steps": sum(1 for e in trace if e.get("event") == "decision"),
        "corrections": sum(
            1 for e in observations if e["observation"]["ok"] and e["arguments"].get("revises")
        ),
        "rejected": sum(
            1 for e in observations if e["observation"].get("metadata", {}).get("error_type") == "ya_corregido"
        ),
    }


def model_of(provider) -> str:
    return str(getattr(provider, "model", "") or "")


def task_cost(task: dict, pricing: dict) -> float | None:
    """Costo estimado de una tarea en USD; `None` si su modelo no tiene precio (una tarea sin modelo, como una decisión, cuesta 0)."""
    if not task["tokens"]:
        return 0.0
    return estimate_cost(task["model"], task.get("input_tokens", 0), task.get("output_tokens", 0), pricing)


def summarize_tasks(tasks: list[dict], pricing: dict | None = None) -> dict:
    """Totales de una corrida: tareas, correcciones, tokens y costo estimado, por agente que ejecutó y por par origen → destino."""
    pricing = load_pricing() if pricing is None else pricing
    by_agent: dict[str, dict] = defaultdict(lambda: {"tareas": 0, "tokens": 0, "entrada": 0, "salida": 0, "costo": 0.0})
    by_pair: dict[tuple[str, str], dict] = defaultdict(lambda: {"tareas": 0, "tokens": 0, "costo": 0.0})
    unpriced: set[str] = set()
    for task in tasks:
        cost = task_cost(task, pricing)
        if cost is None:
            unpriced.add(task["model"])
        for bucket in (by_agent[task["target"]], by_pair[(task["origin"], task["target"])]):
            bucket["tareas"] += 1
            bucket["tokens"] += task["tokens"]
            bucket["costo"] += cost or 0.0
        by_agent[task["target"]]["entrada"] += task.get("input_tokens", 0)
        by_agent[task["target"]]["salida"] += task.get("output_tokens", 0)
    total = sum(task["tokens"] for task in tasks)
    return {
        "tasks": len(tasks),
        "corrections": sum(1 for t in tasks if t["kind"] == "corregir"),
        "corrections_ok": sum(t["corrections"] for t in tasks),
        "rejected": sum(t["rejected"] for t in tasks),
        "failed": sum(1 for t in tasks if t["status"] == "fallida"),
        "tokens": total,
        "input_tokens": sum(t.get("input_tokens", 0) for t in tasks),
        "output_tokens": sum(t.get("output_tokens", 0) for t in tasks),
        "llm_calls": sum(t.get("llm_calls", 0) for t in tasks),
        "cost": sum(row["costo"] for row in by_agent.values()),
        "unpriced_models": sorted(unpriced),
        "by_agent": [
            {"agente": PARTIES.get(agent, agent), "tareas": row["tareas"], "tokens": row["tokens"], "entrada": row["entrada"],
             "salida": row["salida"], "costo": round(row["costo"], 4), "parte": round(row["tokens"] / total, 3) if total else 0.0}
            for agent, row in sorted(by_agent.items(), key=lambda kv: -kv[1]["tokens"])
        ],
        "by_pair": [
            {"de": PARTIES.get(origin, origin), "a": PARTIES.get(target, target), "tareas": row["tareas"], "tokens": row["tokens"],
             "costo": round(row["costo"], 4)}
            for (origin, target), row in sorted(by_pair.items(), key=lambda kv: -kv[1]["tokens"])
        ],
    }
