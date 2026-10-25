from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from backlogguard.board import AgentRole
from backlogguard.llm import (
    AnthropicProvider,
    FakeProvider,
    GeminiProvider,
    ModelSpec,
    ModelsConfig,
    ProviderConfigurationError,
    Settings,
    build_provider,
    load_models_config,
)

MODELS_YAML = Path(__file__).resolve().parents[1] / "config" / "models.yaml"


def raw_config() -> dict:
    return yaml.safe_load(MODELS_YAML.read_text(encoding="utf-8"))


def test_el_models_yaml_real_carga():
    config = load_models_config(MODELS_YAML)
    assert config.for_role(AgentRole.REQUERIMIENTOS).model == "claude-sonnet-5-5"  # ver models.yaml
    assert config.for_role(AgentRole.CRITICO).model == "claude-opus-5-5"


def test_el_critico_no_puede_igualar_al_productor():
    data = raw_config()
    data["agents"]["critico"] = dict(data["agents"]["requerimientos"])
    with pytest.raises(ValidationError, match="independiente"):
        ModelsConfig.model_validate(data)


def test_mismo_modelo_en_otro_proveedor_cuenta_como_distinto():
    data = raw_config()
    data["agents"]["critico"] = {"provider": "fake", "model": "gemini-3.8-flash"}
    ModelsConfig.model_validate(data)


def test_faltan_agentes():
    data = raw_config()
    del data["agents"]["auditor"]
    with pytest.raises(ValidationError, match="faltan"):
        ModelsConfig.model_validate(data)


def test_effort_solo_para_claude():
    with pytest.raises(ValidationError):
        ModelSpec(provider="gemini", model="gemini-3.8-flash", effort="low")


def test_campos_extra_se_rechazan():
    data = raw_config()
    data["agents"]["supervisor"]["temperature"] = 0.2
    with pytest.raises(ValidationError):
        ModelsConfig.model_validate(data)


def test_sin_live_mode_siempre_hay_proveedor_falso():
    spec = load_models_config(MODELS_YAML).for_role(AgentRole.CRITICO)
    provider = build_provider(spec, Settings(live_mode=False))
    assert isinstance(provider, FakeProvider) and provider.model == "fake:claude-opus-5-5"


def test_live_mode_sin_clave_falla():
    config = load_models_config(MODELS_YAML)
    settings = Settings(live_mode=True)
    for role in (AgentRole.CRITICO, AgentRole.REQUERIMIENTOS):
        with pytest.raises(ProviderConfigurationError):
            build_provider(config.for_role(role), settings)


def test_live_mode_con_clave_arma_el_proveedor_correcto():
    pytest.importorskip("anthropic")
    pytest.importorskip("google.genai")
    config = load_models_config(MODELS_YAML)
    settings = Settings(live_mode=True, anthropic_api_key="sk-test", gemini_api_key="g-test")
    assert isinstance(build_provider(config.for_role(AgentRole.CRITICO), settings), AnthropicProvider)
    assert isinstance(build_provider(config.for_role(AgentRole.REQUERIMIENTOS), settings), AnthropicProvider)
    gemini = ModelSpec(provider="gemini", model="gemini-3.8-flash")
    assert isinstance(build_provider(gemini, settings), GeminiProvider)


def test_settings_no_expone_claves(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LIVE_MODE=1\nANTHROPIC_API_KEY=sk-secreto\n", encoding="utf-8")
    settings = Settings.from_env(env)
    assert settings.live_mode and settings.anthropic_key_value() == "sk-secreto"
    safe = settings.safe_dict()
    assert safe["anthropic_api_key"] == "***configurada***" and "sk-secreto" not in str(safe)
    assert "sk-secreto" not in repr(settings)
