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


# ---- elegir qué se envía ----


def selectable_ids(items: list[dict]) -> list[str]:
    """Ítems que una persona puede mandar o dejar afuera: los que el plan no omite por sí solo."""
    return [i["item_id"] for i in items if i["action"] != "omitir"]


def exclusions_for(items: list[dict], chosen: set[str]) -> list[str]:
    """Lo que hay que excluir del plan para que se publique solo lo elegido."""
    return sorted(item_id for item_id in selectable_ids(items) if item_id not in chosen)


def orphan_warnings(items: list[dict], chosen: set[str]) -> list[str]:
    """Avisos de ítems elegidos cuyo padre del plan se dejó afuera: quedarían sueltos en Azure."""
    pending = set(selectable_ids(items))
    titles = {i["item_id"]: i["title"] for i in items}
    return [
        f"«{i['title']}» se publicaría sin su padre «{titles[i['parent_item_id']]}» y quedaría suelto en Azure."
        for i in items
        if i["item_id"] in chosen and i.get("parent_item_id") in pending and i["parent_item_id"] not in chosen
    ]


def selection_line(items: list[dict], chosen: set[str]) -> str:
    total = len(selectable_ids(items))
    omitted = sum(1 for i in items if i["action"] == "omitir")
    line = f"Se enviarán **{len(chosen)}** de {total} · quedan afuera **{total - len(chosen)}**"
    return line + (f" · {omitted} omitido(s) por el plan (ya publicados o posibles duplicados)" if omitted else "")


def no_pending_plan_text(status: str | None, running: bool) -> str:
    """Por qué no hay nada para elegir: el selector solo aparece mientras un plan espera la aprobación del ingeniero."""
    if running:
        return "La corrida sigue trabajando. Cuando arme el plan de publicación, vas a poder elegir acá qué se envía a Azure."
    how = "El selector aparece en esta pestaña cuando un plan está esperando tu aprobación."
    if status == "publicada":
        return f"No hay un plan pendiente: el plan de la última corrida **ya se publicó**, y los work items de abajo ya están en Azure. {how} Para elegir qué enviar, iniciá una corrida nueva."
    if status == "plan_rechazado":
        return f"No hay un plan pendiente: el último plan fue **rechazado** y no se publicó nada. {how}"
    if status in ("completada", "completada_con_errores"):
        return f"No hay un plan pendiente: la última corrida terminó sin nada nuevo para publicar. {how}"
    return f"No hay un plan de publicación esperando aprobación. {how} Se arma al final de una corrida, después de las decisiones."
