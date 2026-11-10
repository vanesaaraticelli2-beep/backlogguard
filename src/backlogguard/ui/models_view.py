"""Tarjeta «Modelos y costos» del menú izquierdo: elegir el modelo de cada agente comparando precios.

El precio es US$ por millón de tokens *mezclado* según lo que lee y escribe cada agente, con la proporción
recalculada desde las corridas guardadas. Debajo de cada agente, lo + y lo − del modelo elegido para ese rol.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from backlogguard.board import AgentRole
from backlogguard.llm.metering import load_pricing
from backlogguard.llm.model_config import ModelSpec, ModelsConfig
from backlogguard.llm.model_costs import (
    TokenMix,
    blended_price,
    display_name,
    load_notes,
    model_options,
    notes_for,
    provider_for,
    spec_for,
    token_mix,
)
from backlogguard.ui.controller import RunController

AGENTS = {
    AgentRole.SUPERVISOR: ("Supervisor", "planifica"),
    AgentRole.REQUERIMIENTOS: ("Requerimientos", "redacta"),
    AgentRole.CRITICO: ("Crítico", "revisa"),
    AgentRole.AUDITOR: ("Auditor", "alcance"),
    AgentRole.INTEGRACION: ("Integración", "publica"),
}
FEW_TASKS = 5  # con menos tareas medidas, la proporción es poco confiable

CSS = """
<style>
.mc-row{display:flex;justify-content:space-between;align-items:baseline;font-size:.82rem;margin:-.4rem 0 .15rem}
.mc-row .was{color:#8a87a8}
.mc-row .down{color:#3F7D12;font-weight:600}.mc-row .up{color:#b3261e;font-weight:600}
.mc-pc{display:grid;grid-template-columns:14px 1fr;gap:1px 4px;font-size:.78rem;line-height:1.3;margin-bottom:.5rem}
.mc-pc.hl{background:#f6faf1;border-radius:5px;padding:4px 6px}
.mc-pc .p{color:#3F7D12;font-weight:700}.mc-pc .m{color:#b3261e;font-weight:700}
</style>
"""


def usd(value: float | None) -> str:
    return "sin precio" if value is None else f"{value:,.2f}".replace(".", ",")


def times(ratio: float) -> str:
    return f"{ratio:,.1f}".replace(".", ",").removesuffix(",0")


def comparison(previous: str, before: float, after: float, price: tuple[float, float]) -> tuple[bool, str]:
    """(¿es mejor en precio?, frase) frente al modelo anterior, para este agente."""
    detail = f"({usd(before)} → {usd(after)}; entrada {usd(price[0])} / salida {usd(price[1])})"
    name = display_name(previous)
    if after < before:
        saving = 1 - after / before
        text = f"{times(before / after)} veces más barato que {name} para este agente" if saving >= 0.75 else f"{saving:.0%} más barato que {name} para este agente"
        return True, f"{text} {detail}."
    if after > before:
        text = f"{times(after / before)} veces más caro que {name} para este agente" if after >= 2 * before else f"{after / before - 1:.0%} más caro que {name} para este agente"
        return False, f"{text} {detail}."
    return True, f"Mismo precio que {name} {detail}."


@st.cache_data(show_spinner=False)
def _mix(data_dir: str, stamp: float, _controller: RunController) -> dict[AgentRole, TokenMix]:
    return token_mix(_controller.saved_tasks())


def _pros_cons(pros: list[str], cons: list[str], changed: bool) -> str:
    lines = [f'<span class="p">+</span><span>{escape(p)}</span>' for p in pros]
    lines += [f'<span class="m">−</span><span>{escape(c)}</span>' for c in cons]
    return f'<div class="mc-pc{" hl" if changed else ""}">{"".join(lines)}</div>' if lines else ""


def models_card(controller: RunController) -> None:
    pricing = load_pricing()
    notes = load_notes(controller.root / "config" / "model_notes.yaml")
    current = controller.models()
    runs_db = controller.data_dir / "corridas.sqlite"
    mix = _mix(str(controller.data_dir), runs_db.stat().st_mtime if runs_db.exists() else 0.0, controller)
    options = model_options(pricing)

    box = st.sidebar.container(border=True)
    box.markdown(CSS, unsafe_allow_html=True)
    box.markdown("**Modelos y costos**")
    box.caption("US$ por millón de tokens, mezclado según lo que lee y escribe cada agente en las corridas guardadas.")

    chosen: dict[AgentRole, ModelSpec] = {}
    for role, (label, duty) in AGENTS.items():
        spec = current.for_role(role)
        role_options = options if spec.model in options else [spec.model, *options]
        m = mix[role]
        measured = f"lee {m.input_share:.0%} / escribe {m.output_share:.0%}" if m.tasks else "sin tareas medidas"
        model = box.selectbox(
            f"{label} · {duty}", role_options, index=role_options.index(spec.model), format_func=display_name,
            key=f"modelo-{role.value}", help=f"{measured} · {m.tasks} tareas medidas",
        )
        changed = model != spec.model
        chosen[role] = spec_for(model, spec.effort) if changed else spec
        before, after = blended_price(m, pricing.get(spec.model)), blended_price(m, pricing.get(model))
        delta = ""
        if changed and before and after is not None:
            pct = (after - before) / before
            delta = f' <span class="{"down" if pct < 0 else "up"}">{pct:+.0%}</span>'
        box.markdown(
            f'<div class="mc-row"><span class="was">{measured}</span>'
            f'<span>{"<span class=was>" + usd(before) + " → </span>" if changed else ""}{usd(after)}{delta}</span></div>',
            unsafe_allow_html=True,
        )
        pros, cons = notes_for(notes, role, model)
        if changed and before and after is not None:
            cheaper, text = comparison(spec.model, before, after, pricing[model])
            pros, cons = ([text, *pros], cons) if cheaper else (pros, [text, *cons])
        producer = chosen.get(AgentRole.REQUERIMIENTOS)
        if role is AgentRole.CRITICO and producer and (provider_for(model), model) == (producer.provider, producer.model):
            cons = ["Mismo modelo que Requerimientos: pierde la independencia y comparte sus sesgos.", *cons]
        if m.tasks and m.tasks < FEW_TASKS:
            cons = [*cons, f"Solo {m.tasks} tareas medidas: la proporción lee/escribe es poco confiable."]
        box.markdown(_pros_cons(pros, cons, changed), unsafe_allow_html=True)

    error = None
    try:
        proposal = ModelsConfig(agents=chosen)
    except ValueError:
        proposal = None
        error = "Crítico y Requerimientos quedan con el mismo modelo: la regla de independencia no deja aplicar el cambio."
    if error:
        box.warning(error, icon="⚠️")
    if controller.mode != "real":
        box.caption("En modo demo o simulado los modelos no se usan: la elección rige cuando corras con LIVE_MODE=1.")
    pending = proposal is not None and proposal != current
    if box.button("Usar en la próxima corrida", key="aplicar-modelos", type="primary",
                  disabled=not pending or controller.running, width="stretch"):
        controller.apply_models(proposal)
        st.toast("Modelos guardados para la próxima corrida.")
        st.rerun()
