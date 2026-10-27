"""La conversación entre agentes en pantalla: un panel arriba de «Corrida» (lo último, en vivo) y una pestaña con todo.

Los mensajes los arma `graph/conversation.py` a partir del estado de la corrida; acá solo se dibujan.
"""
from __future__ import annotations

import re
from html import escape

import streamlit as st

from backlogguard.graph.conversation import SENDER_LABELS, Message, build_conversation
from backlogguard.ui.controller import RunController

LIVE_MESSAGES = 8
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
    parts.append(f'<div class="bg-head"><b>{escape(_label(m.sender))}</b><span> → {escape(_label(m.receiver))}</span></div>')
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


@st.fragment(run_every=2)
def live_conversation(controller: RunController) -> None:
    """Lo último que se dijeron los agentes. Se actualiza solo mientras la corrida avanza."""
    messages = build_conversation(controller.state())
    if not messages:
        return
    st.markdown("### Lo que se están diciendo los agentes")
    shown = messages[-LIVE_MESSAGES:]
    if len(messages) > len(shown):
        st.caption(f"Mostrando los últimos {len(shown)} de {len(messages)} mensajes. La conversación completa está en la pestaña «Conversación».")
    st.markdown(chat_html(shown), unsafe_allow_html=True)


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
    with st.expander("Detalle técnico"):
        lines = controller.activity()
        st.code("\n".join(lines) if lines else "Todavía no hay actividad.", language="text")
