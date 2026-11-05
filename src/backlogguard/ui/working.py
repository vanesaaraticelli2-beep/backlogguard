"""El «hombrecito» corriendo que acompaña todo procesamiento, en lugar del círculo que gira.

Es un SVG animado (CSS dentro del propio SVG) que se muestra como imagen: no depende del tema ni de Streamlit.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from html import escape
from typing import Iterator

import streamlit as st

_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
<style>
.f{transform-origin:24px 40px;animation:bob .5s ease-in-out infinite}
.l,.r,.a,.b{stroke:#13056D;stroke-width:3;stroke-linecap:round;fill:none}
.l{transform-origin:24px 26px;animation:sw .5s ease-in-out infinite alternate}
.r{transform-origin:24px 26px;animation:sw .5s ease-in-out infinite alternate-reverse}
.a{transform-origin:24px 16px;animation:sw .5s ease-in-out infinite alternate-reverse}
.b{transform-origin:24px 16px;animation:sw .5s ease-in-out infinite alternate}
.t{stroke:#13056D;stroke-width:3.5;stroke-linecap:round}
.h{fill:#59AE01}
.g{stroke:#59AE01;stroke-width:2;stroke-linecap:round;animation:go .5s linear infinite}
@keyframes sw{from{transform:rotate(-45deg)}to{transform:rotate(45deg)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-2px)}}
@keyframes go{from{transform:translateX(6px);opacity:0}30%{opacity:1}to{transform:translateX(-6px);opacity:0}}
</style>
<g class="g"><line x1="6" y1="22" x2="12" y2="22"/><line x1="4" y1="30" x2="11" y2="30"/></g>
<g class="f">
<line class="t" x1="24" y1="14" x2="24" y2="28"/>
<circle class="h" cx="24" cy="8" r="5"/>
<line class="a" x1="24" y1="16" x2="24" y2="27"/>
<line class="b" x1="24" y1="16" x2="24" y2="27"/>
<line class="l" x1="24" y1="27" x2="24" y2="42"/>
<line class="r" x1="24" y1="27" x2="24" y2="42"/>
</g>
</svg>"""

RUNNER_URI = "data:image/svg+xml;base64," + base64.b64encode(_SVG.encode()).decode()


def runner_html(text: str) -> str:
    return (
        '<div style="display:flex;align-items:center;gap:12px;background:#eef0ff;border-left:6px solid #13056D;'
        'border-radius:0 8px 8px 0;padding:8px 16px;margin:4px 0 10px">'
        f'<img src="{RUNNER_URI}" width="48" height="48" alt="procesando"/>'
        f'<span style="font-size:16px;font-weight:600;color:#13056D">{escape(text)}</span></div>'
    )


@contextmanager
def working(text: str) -> Iterator[None]:
    """Muestra el hombrecito con `text` mientras dura el bloque y lo saca al terminar (también si falla)."""
    slot = st.empty()
    slot.markdown(runner_html(text), unsafe_allow_html=True)
    try:
        yield
    finally:
        slot.empty()
