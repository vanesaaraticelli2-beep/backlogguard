"""Cobertura de la corrida a la vista: cada requisito aprobado con su historia, o con el motivo por el que no la tiene."""
from __future__ import annotations

import streamlit as st

from backlogguard.graph.coverage import EXCLUDED, LABELS, WITH_STORY, from_state, summary_line

COLORS = {WITH_STORY: "#2f6a0a", EXCLUDED: "#a35a00", "sin_historia": "#b3261e"}
BACKGROUNDS = {WITH_STORY: "#eaf5dc", EXCLUDED: "#fff3df", "sin_historia": "#fdeceb"}


def coverage_line(state: dict) -> str | None:
    """Una frase con la cobertura de la corrida, o None si la corrida no partió de requisitos aprobados."""
    found = from_state(state)
    return summary_line(found) if found else None


def coverage_section(state: dict) -> None:
    found = from_state(state)
    if not found:
        return
    gaps = [r for r in found if r["status"] != WITH_STORY]
    color = COLORS["sin_historia"] if gaps else COLORS[WITH_STORY]
    background = BACKGROUNDS["sin_historia"] if gaps else BACKGROUNDS[WITH_STORY]
    st.markdown(
        f'<div style="background:{background};border-left:6px solid {color};border-radius:0 8px 8px 0;padding:10px 16px;margin:6px 0 10px">'
        f'<span style="font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{color}">Cobertura de requisitos</span>'
        f'<div style="font-size:17px;font-weight:600">{summary_line(found)}</div></div>',
        unsafe_allow_html=True,
    )
    for row in gaps:
        st.markdown(f"- **{row['id']}** «{row['title']}» · **{LABELS[row['status']]}**: {row['reason']}")
    with st.expander(f"Ver los {len(found)} requisitos y su historia"):
        st.dataframe(
            [{"requisito": r["id"], "título": r["title"], "historia": r["item_id"] or "—", "estado": LABELS[r["status"]]} for r in found],
            hide_index=True, width="stretch",
        )
