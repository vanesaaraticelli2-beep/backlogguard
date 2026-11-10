"""Tarjeta «Consumo por agente» de la sección Corrida: modelo usado, lo consumido y la diferencia con la corrida anterior."""
from __future__ import annotations

from html import escape

import streamlit as st

from backlogguard.graph.tasks import PARTIES, compare_consumption, consumption_by_agent, previous_with_consumption
from backlogguard.llm.metering import load_pricing
from backlogguard.llm.model_costs import display_name
from backlogguard.ui.controller import RunController

CSS = """
<style>
.cc-table{width:100%;border-collapse:collapse;font-size:.88rem}
.cc-table th{font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;color:#8a87a8;font-weight:600;text-align:right;padding:4px 8px;border-bottom:1px solid #e3e1f3}
.cc-table th:first-child,.cc-table th:nth-child(2){text-align:left}
.cc-table td{padding:6px 8px;border-bottom:1px solid #f0eef8;text-align:right;font-variant-numeric:tabular-nums}
.cc-table td:first-child{text-align:left;font-weight:600}
.cc-table td:nth-child(2){text-align:left}
.cc-table tr.total td{border-top:2px solid #1D1B3A;border-bottom:0;font-weight:700}
.cc-table .muted{color:#8a87a8;font-weight:400}
.cc-down{color:#3F7D12;font-weight:600}.cc-up{color:#b3261e;font-weight:600}
</style>
"""


def _num(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _usd(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delta(delta: float | None) -> str:
    if delta is None:
        return '<span class="muted">—</span>'
    if abs(delta) < 0.005:
        return '<span class="muted">igual</span>'
    return f'<span class="{"cc-down" if delta < 0 else "cc-up"}">{delta:+.0%}</span>'


def consumption_card(controller: RunController, tasks: list[dict]) -> None:
    pricing = load_pricing()
    current = consumption_by_agent(tasks, pricing)
    if not any(row["tasks"] for row in current):
        return
    previous = previous_with_consumption(controller.runs_with_tasks(), controller.thread_id) if controller.thread_id else None
    before = consumption_by_agent(previous[1], pricing) if previous else None
    rows = compare_consumption(current, before)

    total_now = sum(r["cost"] for r in current)
    total_before = sum(r["cost"] for r in before) if before else None
    total_delta = (total_now - total_before) / total_before if total_before else None

    body = []
    for row in rows:
        models = ", ".join(display_name(m) for m in row["models"]) or '<span class="muted">no corrió</span>'
        body.append(
            f"<tr><td>{escape(PARTIES.get(row['agent'], row['agent']))}</td><td>{models}</td>"
            f"<td>{_num(row['input'])}</td><td>{_num(row['output'])}</td><td>{_usd(row['cost'])}</td><td>{_delta(row['delta'])}</td></tr>"
        )
    body.append(
        f'<tr class="total"><td>Total</td><td></td><td>{_num(sum(r["input"] for r in current))}</td>'
        f'<td>{_num(sum(r["output"] for r in current))}</td><td>{_usd(total_now)}</td><td>{_delta(total_delta)}</td></tr>'
    )

    box = st.container(border=True)
    box.markdown(CSS, unsafe_allow_html=True)
    box.markdown("**Consumo por agente**")
    box.markdown(
        '<table class="cc-table"><thead><tr><th>Agente</th><th>Modelo</th><th>Entrada</th><th>Salida</th><th>US$</th>'
        f'<th>vs anterior</th></tr></thead><tbody>{"".join(body)}</tbody></table>',
        unsafe_allow_html=True,
    )
    if previous:
        box.caption(
            f"«vs anterior» compara el costo con **{previous[0]}** (US$ {_usd(total_before or 0)}), la última corrida anterior con consumo. "
            "Si las corridas cubren distinta cantidad de requisitos, la diferencia refleja también ese tamaño."
        )
    else:
        box.caption("No hay una corrida anterior con consumo para comparar.")
    box.caption("Tokens de entrada (lo que lee el modelo) y de salida (lo que escribe). US$ estimados con config/pricing.yaml.")
