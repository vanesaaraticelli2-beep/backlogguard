"""Guía del flujo para la persona (fuera del curso): en qué paso está el proyecto y qué le toca hacer ahora.

`next_step` es una función pura sobre un resumen del estado, sin Streamlit, para poder probarla. La pantalla solo la dibuja.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from backlogguard.catalog import ProposalState
from backlogguard.catalog.review import decider_role

FUENTES, REVISION, CORRIDA, DECISIONES, HISTORIAS, AVANZADO = (
    "Fuentes", "Revisión", "Corrida", "Mis decisiones", "Historias de usuario", "Avanzado",
)
TABS = [FUENTES, REVISION, CORRIDA, HISTORIAS, DECISIONES, AVANZADO]
ADVANCED_TABS = ["Conversación", "Catálogo", "Corridas guardadas", "Tareas entre agentes", "Backlog simulado", "Actividad"]
ENGINEER = "full_stack_ia_engineer"  # carga fuentes y aprueba el plan de publicación; la corrida la puede iniciar cualquier rol
ROLE_NAMES = {"product_owner": "product owner", "service_manager": "service manager", "full_stack_ia_engineer": "ingeniero"}
HELP = {
    FUENTES: "Paso 1. Cargá la preventa y las reuniones. Los agentes las leen y proponen requisitos.",
    REVISION: "Paso 2. El product owner (o el service manager, si cambia el alcance) aprueba o descarta lo que los agentes entendieron.",
    CORRIDA: "Paso 3. Los agentes redactan una historia por cada requisito aprobado. Acá se inicia y se sigue la corrida.",
    DECISIONES: "Paso 4. Acá se responde lo que los agentes no pueden decidir solos, y se aprueba el plan de publicación.",
    HISTORIAS: "Paso 5. Las historias de usuario terminadas: se leen completas y se descargan en Word, una por una.",
    AVANZADO: "Detalle técnico para revisar cómo trabajaron los agentes. No hace falta para avanzar.",
}


@dataclass(frozen=True)
class Snapshot:
    """Lo que la guía necesita saber, ya calculado."""
    running: bool
    read_only: bool
    sources_processed: int
    proposals_mine: int
    proposals_others: tuple[str, ...]  # roles que tienen propuestas pendientes y no son el de la persona
    active: int
    to_publish: int
    published: int
    request_title: str | None
    request_role: str | None
    role: str
    stories: int


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    detail: str
    done: bool


@dataclass(frozen=True)
class Next:
    text: str
    tab: str | None  # pestaña a la que lleva el botón; None si no hay nada que hacer acá
    button: str = ""
    step: str = ""


def role_name(role: str | None) -> str:
    return ROLE_NAMES.get(role or "", role or "")


def snapshot(controller, who) -> Snapshot:
    catalog = controller.deps.catalog
    summary = controller.catalog_summary()
    open_props = catalog.proposals(state=ProposalState.PENDIENTE) if catalog is not None else []
    mine = sum(1 for p in open_props if decider_role(p) == who.role)
    others = tuple(sorted({decider_role(p) for p in open_props if decider_role(p) != who.role}))
    payload = controller.pending()
    request = payload["request"] if payload else None
    board = controller.state().get("board") or {}
    stories = sum(1 for i in (board.get("items") or {}).values() if i.get("kind") == "historia")
    return Snapshot(
        running=controller.running, read_only=controller.read_only,
        sources_processed=len(catalog.processed_sources()) if catalog is not None else 0,
        proposals_mine=mine, proposals_others=others, active=summary["active"], to_publish=summary["to_publish"], published=summary["published"],
        request_title=request["title"] if request else None, request_role=request["decides"] if request else None, role=who.role, stories=stories,
    )


def steps_of(s: Snapshot) -> list[Step]:
    pending = s.proposals_mine + len(s.proposals_others)  # al menos una por rol: el conteo exacto lo muestra la pestaña
    return [
        Step(FUENTES, "1 Fuentes", f"{s.sources_processed} leídas" if s.sources_processed else "sin leer", s.sources_processed > 0),
        Step(REVISION, "2 Revisión", "al día" if s.sources_processed and not pending else ("pendiente" if pending else "—"), bool(s.sources_processed) and not pending),
        Step(CORRIDA, "3 Corrida", f"{s.to_publish} por redactar" if s.to_publish else (f"{s.published} publicados" if s.published else "—"), s.active > 0 and not s.to_publish),
        Step(DECISIONES, "4 Decisiones", "1 pendiente" if s.request_title else "ninguna", s.request_title is None and s.published > 0),
        Step(HISTORIAS, "5 Historias", f"{s.published} listas" if s.published else "—", s.published > 0 and not s.to_publish and s.request_title is None),
    ]


def next_step(s: Snapshot) -> Next:
    if s.read_only:
        return Next("Estás viendo una corrida guardada (solo lectura). Para seguir trabajando, abrí la pestaña «Corrida».", CORRIDA, "Ir a Corrida")
    if s.running:
        return Next("Los agentes están trabajando. No hace falta hacer nada: cuando necesiten algo de vos, te lo van a decir acá.", None, step=CORRIDA)
    if s.request_title is not None:
        if s.request_role == s.role:
            return Next(f"Falta tu decisión como {role_name(s.role)}: «{s.request_title}».", DECISIONES, "Ir a decidir", step=DECISIONES)
        return Next(
            f"La corrida espera la decisión del {role_name(s.request_role)}. Cambiá el rol en la barra lateral para decidirla.", None, step=DECISIONES,
        )
    if not s.sources_processed:
        if s.role != ENGINEER:
            return Next("Todavía no se leyó ninguna reunión: la carga el ingeniero. Por ahora no tenés nada para hacer.", None, step=FUENTES)
        return Next("Empezá cargando la preventa y leyendo una reunión.", FUENTES, "Ir a Fuentes", step=FUENTES)
    if s.proposals_mine:
        return Next(f"Tenés {s.proposals_mine} propuesta(s) por revisar como {role_name(s.role)}.", REVISION, "Ir a Revisión", step=REVISION)
    if s.proposals_others:
        roles = " y ".join(role_name(r) for r in s.proposals_others)
        return Next(f"Hay propuestas que decide el {roles}. Cambiá el rol en la barra lateral para revisarlas.", None, step=REVISION)
    if s.to_publish:
        return Next(f"Hay {s.to_publish} requisito(s) aprobado(s) sin historia. Iniciá la corrida para que los agentes las redacten.", CORRIDA, "Ir a Corrida", step=CORRIDA)
    if s.published or s.stories:
        return Next("Todo al día. Las historias terminadas están listas para leer y descargar en Word.", HISTORIAS, "Ver historias", step=HISTORIAS)
    return Next("No hay requisitos aprobados todavía. Leé una reunión en «Fuentes» y aprobá sus propuestas en «Revisión».", FUENTES, "Ir a Fuentes", step=FUENTES)


def mine(s: Snapshot) -> str:
    """Lo que le toca decidir al rol de la persona, aparte de lo que puede hacer cualquiera (iniciar la corrida)."""
    parts = []
    if s.proposals_mine:
        parts.append(f"{s.proposals_mine} propuesta(s) por revisar")
    if s.request_title is not None and s.request_role == s.role:
        parts.append("1 decisión de la corrida")
    rest = " · ".join(parts) if parts else "nada por ahora"
    return f"Tus pendientes como {role_name(s.role)}: {rest}."


def steps_html(steps: list[Step], current: str) -> str:
    cells = []
    for step in steps:
        css = "now" if step.key == current else ("done" if step.done else "")
        mark = "✔ " if step.done and step.key != current else ""
        cells.append(f'<span class="bg-step {css}"><b>{mark}{escape(step.label)}</b><small>{escape(step.detail)}</small></span>')
    return f'<div class="bg-steps">{"".join(cells)}</div>'


def go(tab: str) -> None:
    st.session_state["nav"] = tab


def render_guide(controller, who) -> None:
    """Barra de pasos y cartel «qué sigue», arriba de las pestañas."""
    snap = snapshot(controller, who)
    step = next_step(snap)
    st.markdown(steps_html(steps_of(snap), step.step), unsafe_allow_html=True)
    text, button = st.columns([5, 1.4], vertical_alignment="center")
    text.markdown(f'<div class="bg-next"><span>Qué sigue</span> {escape(step.text)}</div>', unsafe_allow_html=True)
    text.caption(mine(snap))
    if step.tab:
        button.button(step.button, key="guia-ir", type="primary", width="stretch", on_click=go, args=(step.tab,))
