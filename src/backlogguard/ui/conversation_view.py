"""La conversación entre agentes en pantalla: un panel arriba de «Corrida» (lo último, en vivo) y una pestaña con todo.

Los mensajes los arma `graph/conversation.py` a partir del estado de la corrida; acá solo se dibujan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

import streamlit as st

from backlogguard.graph.conversation import SENDER_LABELS, Message, build_conversation
from backlogguard.ui.controller import RunController
from backlogguard.ui.guide import role_name

COLORS = {
    "supervisor": "#13056D", "requerimientos": "#3F7D12", "critico": "#B26A00", "auditor": "#0B6E8A", "integracion": "#7A4B8F",
}
HUMAN_COLOR = "#5D5B7A"


def _label(who: str) -> str:
    return SENDER_LABELS.get(who, who)


def _rich(text: str) -> str:
    """Escapa el texto y respeta el negrita y los saltos de línea que traiga el resumen del Supervisor."""
    html = escape(text)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    return html.replace("\n", "<br>")


def message_html(m: Message) -> str:
    color = COLORS.get(m.sender, HUMAN_COLOR)
    parts = [f'<div class="bg-msg {m.tone}" style="--c:{color}">']
    parts.append(f'<div class="bg-head"><b>{escape(_label(m.sender))}</b></div>')
    parts.append(f'<div class="bg-text">{_rich(m.text)}</div>')
    if m.points:
        parts.append("<ul>" + "".join(f"<li>{escape(p)}</li>" for p in m.points) + "</ul>")
    if m.quote:
        source = f"<small>{escape(m.quote_from)}</small>" if m.quote_from else ""
        parts.append(f'<blockquote class="bg-q">«{escape(m.quote)}»{source}</blockquote>')
    parts.append("</div>")
    return "".join(parts)


def chat_html(messages: list[Message]) -> str:
    return '<div class="bg-chat">' + "".join(message_html(m) for m in messages) + "</div>"


def scroll_html(messages: list[Message]) -> str:
    """Toda la conversación en una caja con scroll; la vista queda anclada al último mensaje (column-reverse)."""
    return f'<div class="bg-scroll">{chat_html(messages)}</div>'


@dataclass(frozen=True)
class RunBadge:
    css: str  # ok (verde), paused (rojo) o warn (ámbar)
    text: str


def run_badge(state: dict, *, running: bool, error: str | None, request_role: str | None = None, request_title: str | None = None) -> RunBadge | None:
    """El estado de la corrida para la persona: verde si va bien, rojo si está pausada (con el rol que debe continuar), ámbar si hubo un problema."""
    status = state.get("status")
    if error:
        return RunBadge("warn", f"La corrida falló: {error}")
    if running:
        return RunBadge("ok", "En curso: los agentes están trabajando.")
    if request_role:
        what = f" sobre «{request_title}»" if request_title else ""
        return RunBadge("paused", f"Pausada: debe continuar el {role_name(request_role)}{what}.")
    if status in ("esperando_decision", "plan_pendiente_de_aprobacion"):
        return RunBadge("paused", "Pausada: falta una decisión. Retomala desde «Corridas guardadas» (Avanzado).")
    if status in ("presupuesto_agotado", "completada_con_errores", "publicacion_detenida", "plan_rechazado"):
        return RunBadge("warn", {
            "presupuesto_agotado": "Cortada: se agotó el presupuesto. Puede haber elementos sin revisar.",
            "completada_con_errores": "Terminó con errores: revisá el detalle.",
            "publicacion_detenida": "La publicación se detuvo: revisá «Backlog simulado».",
            "plan_rechazado": "El plan se rechazó: no se publicó nada.",
        }[status])
    if status in ("publicada", "completada"):
        return RunBadge("ok", "Terminada: todo salió bien.")
    return None


def badge_html(badge: RunBadge) -> str:
    return f'<div class="bg-status {badge.css}"><span class="dot"></span>{escape(badge.text)}</div>'


def _live(controller: RunController) -> None:
    state = controller.state()
    payload = controller.pending()
    request = payload["request"] if payload else {}
    badge = run_badge(state, running=controller.running, error=controller.error, request_role=request.get("decides"), request_title=request.get("title"))
    messages = build_conversation(state)
    if not messages and badge is None:
        return
    st.markdown("### Lo que se están diciendo los agentes")
    if badge:
        st.markdown(badge_html(badge), unsafe_allow_html=True)
    if messages:
        st.markdown(scroll_html(messages), unsafe_allow_html=True)


def live_conversation(controller: RunController) -> None:
    """Toda la conversación de la corrida, en vivo. Se actualiza sola mientras avanza; al terminar deja de refrescar para poder leer con calma."""
    st.fragment(run_every=2 if controller.running else None)(_live)(controller)


def tab_conversation(controller: RunController) -> None:
    messages = build_conversation(controller.state())
    st.caption(
        "Cómo se pasaron el trabajo los agentes, en orden. Cada mensaje sale de algo que pasó en la corrida: nada está inventado. "
        "Las citas son textuales."
    )
    if not messages:
        st.info("Todavía no hay conversación. Iniciá una corrida o abrí una guardada.")
        return
    agents = sorted({_label(m.sender) for m in messages} | {_label(m.receiver) for m in messages})
    picked = st.multiselect("Mostrar solo lo que dicen o reciben", agents, key="conversacion_agentes", placeholder="Todos")
    shown = [m for m in messages if not picked or _label(m.sender) in picked or _label(m.receiver) in picked]
    st.markdown(chat_html(shown), unsafe_allow_html=True)
