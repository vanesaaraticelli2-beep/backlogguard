"""Cómo se muestra un pedido de decisión: lo que se pide, las objeciones una por una y el detalle plegado.

El texto del pedido (`request["summary"]`) no cambia: está sellado con su hash. Acá solo se lo lee y se lo presenta.
"""
from __future__ import annotations

import re
from html import escape

import streamlit as st

INTRO = "El Crítico y el productor no llegaron a un acuerdo"
CHUNK = re.compile(r"([\w.-]+?)(?:_(\d{2})_(\d{2})_(\d{4}))?:(?:dialogo|prosa|texto|pagina|p)[\w-]*:(\d+):[0-9a-f]{6,}")
LABELS = (
    (("falta un escenario", "falta un caso", "ningún criterio cubre"), "Falta un escenario", "#a35a00", "#fff0d9"),
    (("choca", "contradice", "se opone", "posterior"), "Choca con otra reunión", "#b3261e", "#fde7e5"),
    (("no tiene respaldo", "cita textual", "no está citado", "no contiene", "citarlo"), "Falta respaldo en la cita", "#13056D", "#ebe9fb"),
)
ACTIONS = (
    ("Aprobar", "se acepta la historia como está, con estas objeciones a la vista."),
    ("Guardar edición", "corregís el texto vos; queda una versión nueva que hay que aprobar otra vez."),
    ("Rechazar", "se descarta la historia."),
)


def short_refs(text: str) -> str:
    """«minuta_logicorp_24_08_2026:dialogo:006:82daaec7» pasa a «minuta del 24-08, fragmento 6»."""
    def one(match: re.Match) -> str:
        day, month = match.group(2), match.group(3)
        where = f"{day}-{month}" if day else match.group(1)
        return f"[{where}, frag. {int(match.group(5))}]"

    return CHUNK.sub(one, text)


def parse_objections(summary: str) -> list[str] | None:
    """Las objeciones de un desacuerdo sin consenso, o None si el pedido es de otro tipo."""
    if not summary.startswith(INTRO):
        return None
    lines = summary.split("\n")
    items: list[str] = []
    for line in lines[1:]:
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif items and line.strip():
            items[-1] += " " + line.strip()
    return items


def headline(text: str) -> tuple[str, str]:
    """La primera oración (lo esencial) y el resto (el detalle)."""
    clean = short_refs(text)
    match = re.search(r"(?<=[.?!»)])\s+(?=[A-ZÁÉÍÓÚÑ¿¡«])", clean[40:])
    if not match:
        return clean, ""
    cut = 40 + match.start()
    return clean[:cut].strip(), clean[cut:].strip()


def label_for(text: str) -> tuple[str, str, str]:
    low = text.lower()
    for words, name, color, background in LABELS:
        if any(w in low for w in words):
            return name, color, background
    return "Objeción", "#13056D", "#ebe9fb"


def summary_view(request: dict) -> None:
    """Muestra el resumen del pedido. Un desacuerdo se ve como lista de objeciones; lo demás, como texto."""
    objections = parse_objections(request["summary"])
    if objections is None:
        st.text(request["summary"])
        return
    st.markdown(
        f'<div class="bg-next"><span>Qué se te pide</span> Decidí cómo sigue esta historia: el Crítico y el productor discreparon en 2 rondas. '
        f"Hay {len(objections)} objeción(es) sin resolver.</div>",
        unsafe_allow_html=True,
    )
    for number, text in enumerate(objections, 1):
        name, color, background = label_for(text)
        first, rest = headline(text)
        st.markdown(
            f'<div style="background:{background};border-left:5px solid {color};border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0 2px">'
            f'<span style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{color}">{number}. {escape(name)}</span>'
            f'<div style="font-size:16px;font-weight:600;margin-top:2px">{escape(first)}</div></div>',
            unsafe_allow_html=True,
        )
        if rest:
            with st.expander("Ver el detalle"):
                st.write(rest)
    st.markdown('<div class="bg-label">Qué hace cada botón</div>', unsafe_allow_html=True)
    st.markdown("\n".join(f"- **{name}**: {what}" for name, what in ACTIONS))
