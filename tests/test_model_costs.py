"""Tarjeta «Modelos y costos»: proporción entrada/salida por agente, precio mezclado y elección por proyecto."""
import pytest

from backlogguard.board import AgentRole
from backlogguard.llm.model_config import ModelSpec, ModelsConfig
from backlogguard.llm.model_costs import (
    DEFAULT_MIX,
    TokenMix,
    blended_price,
    display_name,
    load_notes,
    spec_for,
    model_options,
    models_path,
    notes_for,
    provider_for,
    save_models_config,
    load_effective_models,
    token_mix,
)

PRICING = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5), "gemini-3.8-flash": (0.25, 1.5)}


def task(target, entrada, salida):
    return {"target": target, "input_tokens": entrada, "output_tokens": salida}


def test_la_proporcion_se_calcula_por_agente_sumando_todas_las_corridas():
    runs = [[task("critico", 800, 100), task("requerimientos", 940, 60)], [task("critico", 80, 20), task("decidir", 0, 0)]]
    mix = token_mix(runs)
    assert mix[AgentRole.CRITICO] == TokenMix(880, 120, 2)
    assert mix[AgentRole.CRITICO].input_share == pytest.approx(0.88)
    assert mix[AgentRole.REQUERIMIENTOS].tasks == 1


def test_un_agente_sin_tareas_medidas_usa_la_proporcion_por_defecto():
    mix = token_mix([[task("critico", 10, 0)]])
    assert mix[AgentRole.AUDITOR] == DEFAULT_MIX
    assert mix[AgentRole.AUDITOR].tasks == 0
    assert set(mix) == set(AgentRole)


def test_las_tareas_sin_tokens_o_de_personas_no_cuentan():
    mix = token_mix([[task("critico", 0, 0), task("persona", 50, 5)]])
    assert mix[AgentRole.CRITICO].tasks == 0


def test_precio_mezclado_por_millon():
    mix = TokenMix(882, 118, 3)
    assert blended_price(mix, PRICING["claude-opus-5-5"]) == pytest.approx(0.882 * 4 + 0.118 * 20)
    assert blended_price(mix, None) is None


def test_opciones_y_proveedor_salen_de_los_precios():
    assert model_options(PRICING)[0] == "claude-haiku-5-5"  # de más barato a más caro
    assert provider_for("gemini-3.8-flash") == "gemini"
    assert provider_for("claude-opus-5-5") == "anthropic"


def test_nombres_con_version_y_esfuerzo_solo_donde_la_api_lo_acepta():
    assert display_name("claude-opus-5-5") == "Opus 5.5"
    assert display_name("claude-fable-5") == "Fable 5"
    assert display_name("claude-haiku-4-5") == "Haiku 4.5"
    assert display_name("gemini-3.8-flash") == "Gemini Flash"
    assert spec_for("claude-sonnet-4-6", "low").effort == "low"
    assert spec_for("claude-haiku-4-5", "low").effort is None
    assert spec_for("gemini-3.8-flash", "low") == ModelSpec(provider="gemini", model="gemini-3.8-flash")


def test_los_precios_configurados_incluyen_los_modelos_de_anthropic_y_gemini_flash():
    from backlogguard.llm.metering import load_pricing

    pricing = load_pricing()
    for model in ("claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-haiku-4-5", "gemini-3.8-flash"):
        assert model in pricing


def config(critico="claude-opus-5-5"):
    agents = {role: ModelSpec(provider="anthropic", model="claude-sonnet-5-5", effort="low") for role in AgentRole}
    agents[AgentRole.CRITICO] = ModelSpec(provider="anthropic", model=critico, effort="medium")
    return ModelsConfig(agents=agents)


def test_la_eleccion_se_guarda_en_los_datos_del_proyecto_y_tiene_prioridad(tmp_path):
    root, data = tmp_path / "root", tmp_path / "datos"
    (root / "config").mkdir(parents=True)
    save_models_config(config(), root / "config" / "models.yaml")
    assert models_path(root, data) == root / "config" / "models.yaml"
    save_models_config(config(critico="claude-haiku-5-5"), data / "models.yaml")
    assert models_path(root, data) == data / "models.yaml"
    assert load_effective_models(root, data).for_role(AgentRole.CRITICO).model == "claude-haiku-5-5"


def test_las_notas_especificas_del_agente_tienen_prioridad(tmp_path):
    path = tmp_path / "notas.yaml"
    path.write_text(
        "generales:\n  claude-opus-5-5: {mas: [general], menos: [caro]}\n"
        "agentes:\n  critico:\n    claude-opus-5-5: {mas: [riguroso], menos: []}\n",
        encoding="utf-8",
    )
    notes = load_notes(path)
    assert notes_for(notes, AgentRole.CRITICO, "claude-opus-5-5") == (["riguroso"], [])
    assert notes_for(notes, AgentRole.AUDITOR, "claude-opus-5-5") == (["general"], ["caro"])
    assert notes_for(notes, AgentRole.AUDITOR, "otro") == ([], [])
    assert load_notes(tmp_path / "no-existe.yaml") == {}
