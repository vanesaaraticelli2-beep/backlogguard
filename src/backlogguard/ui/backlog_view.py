"""Vista del backlog simulado: jerarquía de work items, qué cambió en la corrida y la ficha de cada uno.

Funciones puras sobre los work items (dicts o `WorkItem`) y el tablero; la pantalla solo las dibuja.
"""
from __future__ import annotations

from dataclasses import dataclass

ITEM_TAG = "bg-item:"
KEY_TAG = "bg-key:"
TYPE_RANK = {"Epic": 0, "User Story": 1, "Task": 2, "Test Case": 3}
CHANGES = {"nuevo": "🟢 Nuevo", "actualizado": "🟠 Actualizado", "sin cambios": "Sin cambios", "": "—"}
FILTERS = ["Todos", "Nuevos y actualizados", "Cargados a mano"]


@dataclass(frozen=True)
class Node:
    id: int
    type: str
    title: str
    state: str
    tags: list[str]
    parent_id: int | None
    depth: int
    change: str  # nuevo | actualizado | sin cambios | "" (no hay estado anterior para comparar)
    origin: str  # "BacklogGuard" | "manual"
    board_id: str | None  # id del ítem del tablero del que salió (etiqueta bg-item)
    description: str
    criteria: list[str]
    rev: int


def _dict(work_item) -> dict:
    return work_item if isinstance(work_item, dict) else work_item.model_dump()


def board_id_of(tags: list[str]) -> str | None:
    return next((tag[len(ITEM_TAG):] for tag in tags if tag.startswith(ITEM_TAG)), None)


def change_of(item: dict, before: dict[int, dict] | None) -> str:
    if before is None:
        return ""
    old = before.get(item["id"])
    if old is None:
        return "nuevo"
    return "actualizado" if old.get("rev") != item.get("rev") else "sin cambios"


def build_nodes(items: list, before: list | None = None) -> list[Node]:
    """Work items en orden de árbol (cada padre antes que sus hijos), con su nivel de sangría y qué les pasó en la corrida."""
    rows = [_dict(i) for i in items]
    previous = None if before is None else {b["id"]: b for b in map(_dict, before)}
    by_id = {r["id"]: r for r in rows}
    children: dict[int | None, list[dict]] = {}
    for row in rows:
        parent = row.get("parent_id") if row.get("parent_id") in by_id else None  # un padre que no existe lo deja como raíz
        children.setdefault(parent, []).append(row)
    for group in children.values():
        group.sort(key=lambda r: (TYPE_RANK.get(r["type"], 9), r["id"]))

    nodes: list[Node] = []

    def visit(row: dict, depth: int) -> None:
        tags = list(row.get("tags", []))
        nodes.append(Node(
            id=row["id"], type=row["type"], title=row["title"], state=row.get("state", ""), tags=tags,
            parent_id=row.get("parent_id"), depth=depth, change=change_of(row, previous),
            origin="BacklogGuard" if board_id_of(tags) else "manual", board_id=board_id_of(tags),
            description=row.get("description", ""), criteria=list(row.get("acceptance_criteria", [])), rev=row.get("rev", 1),
        ))
        for child in children.get(row["id"], []):
            visit(child, depth + 1)

    for root in children.get(None, []):
        visit(root, 0)
    return nodes


def apply_filter(nodes: list[Node], name: str) -> list[Node]:
    """Filtra sin perder el contexto: con «Nuevos y actualizados» se conservan los padres de lo que cambió."""
    if name == "Cargados a mano":
        return [n for n in nodes if n.origin == "manual"]
    if name == "Nuevos y actualizados":
        keep = {n.id for n in nodes if n.change in ("nuevo", "actualizado")}
        parents = {n.id: n.parent_id for n in nodes}
        for node_id in list(keep):
            parent = parents.get(node_id)
            while parent in parents and parent not in keep:
                keep.add(parent)
                parent = parents[parent]
        return [n for n in nodes if n.id in keep]
    return list(nodes)


def counts(nodes: list[Node]) -> dict[str, int]:
    return {
        "total": len(nodes),
        "nuevos": sum(1 for n in nodes if n.change == "nuevo"),
        "actualizados": sum(1 for n in nodes if n.change == "actualizado"),
        "manuales": sum(1 for n in nodes if n.origin == "manual"),
    }


def rows(nodes: list[Node]) -> list[dict]:
    """Una fila por work item para la tabla; la sangría muestra la jerarquía."""
    titles = {n.id: n.title for n in nodes}
    return [
        {
            "#": n.id,
            "Tipo": n.type,
            "Título": ("    " * n.depth + ("↳ " if n.depth else "") + n.title),
            "Estado": n.state,
            "Cambio": CHANGES.get(n.change, n.change),
            "Origen": n.origin,
            "Padre": f"#{n.parent_id} {titles[n.parent_id]}" if n.parent_id in titles else (f"#{n.parent_id}" if n.parent_id else "—"),
        }
        for n in nodes
    ]


def option_label(node: Node) -> str:
    return f"#{node.id} · {node.type} · {node.title}"


def detail_markdown(node: Node, board_item=None) -> str:
    """Ficha del work item: descripción, criterios y, si salió de BacklogGuard, de qué requisito y con qué evidencia."""
    lines = [f"**{node.type} #{node.id}** · {node.state} · versión {node.rev} · {CHANGES.get(node.change, '')}".rstrip(" ·")]
    if node.description:
        lines.append(f"**Descripción**\n\n{node.description}")
    if node.criteria:
        lines.append("**Criterios de aceptación**\n\n" + "\n".join(f"- {c.replace(chr(10), '  ' + chr(10) + '  ')}" for c in node.criteria))
    if node.origin == "manual":
        lines.append("_Cargado a mano en el backlog: BacklogGuard no lo creó ni lo modifica._")
    elif board_item is not None and getattr(board_item, "requirement_id", None):
        lines.append(f"**Requisito:** {board_item.requirement_id} v{board_item.requirement_version}")
    return "\n\n".join(lines)
