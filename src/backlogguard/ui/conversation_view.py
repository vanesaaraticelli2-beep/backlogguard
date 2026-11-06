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
TONE_TAGS = {"ok": "Conforme", "warn": "Observación", "wait": "En espera"}


def _label(who: str) -> str:
    return SENDER_LABELS.get(who, who)


def _rich(text: str) -> str:
    """Escapa el texto y respeta el negrita y los saltos de línea que traiga el resumen del Supervisor."""
    html = escape(text)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    return html.replace("\n", "<br>")


def _party(who: str) -> str:
    return f'<i style="--c:{COLORS.get(who, HUMAN_COLOR)}"></i>{escape(_label(who))}'


def message_html(m: Message, number: int = 1) -> str:
    """Una fila del registro: número de orden, quién lo dice, a quién, el mensaje y su referencia (tarea, historia y estado)."""
    text = [_rich(m.text)]
    if m.points:
        text.append("<ul>" + "".join(f"<li>{escape(p)}</li>" for p in m.points) + "</ul>")
    if m.quote:
        source = f"<small>{escape(m.quote_from)}</small>" if m.quote_from else ""
        text.append(f'<div class="bg-cite">«{escape(m.quote)}»{source}</div>')
    ref = " · ".join(escape(r) for r in (m.task, m.ref) if r) or "—"
    tag = f'<br><span class="bg-tag {m.tone}">{TONE_TAGS[m.tone]}</span>' if m.tone in TONE_TAGS else ""
    return (
        f'<div class="bg-row"><div class="bg-n">{number:02d}</div><div class="bg-who bg-from">{_party(m.sender)}</div>'
        f'<div class="bg-who bg-to">{_party(m.receiver)}</div><div class="bg-text">{"".join(text)}</div>'
        f'<div class="bg-ref">{ref}{tag}</div></div>'
    )


def chat_html(messages: list[Message] | list[tuple[int, Message]], *, latest: bool = False) -> str:
    """El registro numerado en una caja de altura media con el encabezado fijo.

    Acepta los mensajes solos (se numeran desde 1) o ya numerados, para que un filtro conserve el número original.
    Con `latest` la caja queda anclada al último mensaje (column-reverse), como conviene en vivo."""
    numbered = [m if isinstance(m, tuple) else (i, m) for i, m in enumerate(messages, 1)]
    rows = "".join(message_html(m, n) for n, m in numbered)
    head = "".join(f"<div>{h}</div>" for h in ("N.º", "De", "Para", "Mensaje", "Referencia"))
    return (
        f'<div class="bg-reg"><div class="bg-reg-head">{head}</div>'
        f'<div class="bg-reg-body{" latest" if latest else ""}"><div class="bg-reg-rows">{rows}</div></div></div>'
    )


def scroll_html(messages: list[Message]) -> str:
    """La conversación en vivo: el mismo registro, anclado al último mensaje."""
    return chat_html(messages, latest=True)


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
    st.markdown("### Registro de la conversación entre agentes")
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
        "Registro de cómo se pasaron el trabajo los agentes, numerado en el orden en que ocurrió. Cada mensaje sale de algo que pasó "
        "en la corrida: nada está inventado. Las citas son textuales."
    )
    if not messages:
        st.info("Todavía no hay conversación. Iniciá una corrida o abrí una guardada.")
        return
    agents = sorted({_label(m.sender) for m in messages} | {_label(m.receiver) for m in messages})
    picked = st.multiselect("Mostrar solo lo que emite o recibe", agents, key="conversacion_agentes", placeholder="Todos los participantes")
    shown = [(n, m) for n, m in enumerate(messages, 1) if not picked or _label(m.sender) in picked or _label(m.receiver) in picked]
    st.caption(f"{len(shown)} de {len(messages)} mensajes" if picked else f"{len(messages)} mensajes")
    st.markdown(chat_html(shown), unsafe_allow_html=True)
