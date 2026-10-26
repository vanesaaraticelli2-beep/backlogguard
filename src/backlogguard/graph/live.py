"""Vista en vivo de una corrida: convierte cada evento de los agentes en una línea legible.

Los eventos salen del ciclo de agente (`on_event`) y del grafo. Esta función es la misma que usará
la interfaz para mostrar la actividad.
"""
from __future__ import annotations

import json

NODE_TITLES = {
    "plan": "Supervisor planifica",
    "produce": "Requerimientos redacta",
    "review": "Crítico revisa un ítem",
    "audit": "Auditor audita el proyecto",
    "escalate": "Escalaciones por reglas",
    "decide": "Una persona decide",
    "approve_plan": "Se aprueba el plan de publicación",
    "integrate": "Integración arma el plan de publicación",
    "summarize": "Supervisor resume",
}
AGENT_NAMES = {
    "supervisor": "Supervisor",
    "requerimientos": "Requerimientos",
    "critico": "Crítico",
    "auditor": "Auditor",
    "integracion": "Integración",
    "grafo": "Grafo",
}


def _short(text: object, limit: int = 110) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _args(arguments: dict) -> str:
    return ", ".join(f"{key}={_short(value, 40)}" for key, value in arguments.items())


def format_trace(entries: list[dict]) -> list[str]:
    """Recorrido guardado de una corrida (una entrada por etapa), para verla después.

    La actividad paso a paso de cada agente no se guarda: solo queda este resumen por etapa.
    """
    lines = []
    for entry in entries:
        detail = ", ".join(f"{key}={_short(value, 60)}" for key, value in entry.items() if key != "node" and value not in (None, [], {}, ""))
        lines.append(f"▶ {NODE_TITLES.get(entry['node'], entry['node'])}" + (f"  ·  {detail}" if detail else ""))
    return lines


def format_event(event: dict) -> str | None:
    """Línea de texto para un evento, o `None` si no aporta a la vista."""
    agent = AGENT_NAMES.get(event.get("agent", ""), event.get("agent", "?"))
    kind = event.get("event")
    if kind == "node_start":
        return f"\n▶ {NODE_TITLES.get(event['node'], event['node'])}"
    if kind == "node_end":
        return None
    if kind == "decision":
        decision = event["decision"]
        if decision["action"] == "tool":
            return f"  {agent} → {decision['tool_name']}({_args(decision['arguments'])})"
        return f"  {agent} termina: {_short(decision.get('final_answer'), 160)}"
    if kind == "observation":
        observation = event["observation"]
        mark = "ok" if observation["ok"] else "ERROR"
        origin = f"  {agent} (precalculada) {event['tool']}\n" if event.get("precalculada") else ""
        return f"{origin}      ↳ {mark}: {_short(observation['content'])}"
    if kind == "llm_error":
        return f"  {agent}: falló el modelo → {_short(event['error'])}"
    return json.dumps(event, ensure_ascii=False)[:160]
