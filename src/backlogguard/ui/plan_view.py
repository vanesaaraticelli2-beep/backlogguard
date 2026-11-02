"""Vista del plan de publicación: lo que se crearía, actualizaría o vincularía en Azure DevOps, ítem por ítem.

Funciones puras sobre el payload del pedido `R-plan`; la pantalla solo las dibuja.
"""
from __future__ import annotations

ACTIONS = {"crear": "Crear", "actualizar": "Actualizar", "vincular": "Vincular", "omitir": "Omitir"}
ICONS = {"crear": "🟢", "actualizar": "🟠", "vincular": "🔗", "omitir": "⚪"}


def action_label(action: str) -> str:
    return ACTIONS.get(action, action.capitalize())


def counts_line(items: list[dict]) -> str:
    """«2 para crear · 1 para actualizar · 1 omitido», solo con lo que hay."""
    words = {"crear": "para crear", "actualizar": "para actualizar", "vincular": "para vincular", "omitir": "omitido(s)"}
    parts = [f"{n} {words[a]}" for a in words if (n := sum(1 for i in items if i["action"] == a))]
    return " · ".join(parts) or "sin ítems"


def plan_rows(items: list[dict]) -> list[dict]:
    """Una fila por ítem para la tabla, con el padre por su título."""
    titles = {i["item_id"]: i["title"] for i in items}
    return [
        {
            "Acción": f"{ICONS.get(i['action'], '')} {action_label(i['action'])}",
            "Tipo": i["type"],
            "Id": i["item_id"],
            "Título": i["title"],
            "Padre": titles.get(i.get("parent_item_id") or "", i.get("parent_item_id") or "—"),
            "En Azure": f"#{i['remote_id']}" if i.get("remote_id") else "nuevo",
            "Motivo": i["reason"],
        }
        for i in items
    ]


def item_heading(item: dict) -> str:
    return f"{ICONS.get(item['action'], '')} {action_label(item['action'])} · {item['type']} · {item['item_id']} — {item['title']}"


def item_markdown(item: dict, parent_title: str | None = None) -> str:
    """Ficha del work item tal como quedaría: descripción y criterios de aceptación."""
    lines = [f"**Motivo:** {item['reason']}"]
    if parent_title or item.get("parent_item_id"):
        lines.append(f"**Padre:** {parent_title or item['parent_item_id']}")
    if item.get("remote_id"):
        lines.append(f"**Work item existente:** #{item['remote_id']}")
    if item.get("description"):
        lines.append(f"**Descripción**\n\n{item['description']}")
    criteria = item.get("acceptance_criteria") or []
    if criteria:
        lines.append("**Criterios de aceptación**\n\n" + "\n".join(f"- {c.replace(chr(10), '  ' + chr(10) + '  ')}" for c in criteria))
    return "\n\n".join(lines)
