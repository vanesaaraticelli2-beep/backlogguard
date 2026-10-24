from pathlib import Path

import pytest

from backlogguard.board import AgentRole
from backlogguard.tools import (
    ExecutionContext,
    ToolCall,
    ToolPolicy,
    build_catalog_registry,
    load_policy_config,
)

POLICY_YAML = Path(__file__).resolve().parents[1] / "config" / "policy.yaml"

EXPECTED = {
    AgentRole.SUPERVISOR: {"delegar_tarea", "escalar_a_persona"},
    AgentRole.REQUERIMIENTOS: {"ingestar_y_fragmentar", "buscar_en_fuentes", "redactar_historia"},
    AgentRole.CRITICO: {"verificar_cita", "buscar_contraevidencia", "evaluar_dor_invest"},
    AgentRole.AUDITOR: {
        "comparar_con_preventa",
        "detectar_contradicciones",
        "consultar_decisiones_vigentes",
        "registrar_decision_aprobada",
    },
    AgentRole.INTEGRACION: {
        "buscar_en_backlog",
        "armar_plan_dry_run",
        "revalidar_plan",
        "ejecutar_plan_aprobado",
    },
}


def full_context(role: AgentRole, **overrides) -> ExecutionContext:
    data = dict(user_id="u", role=role, allow_drafts=True, allow_external_writes=True)
    data.update(overrides)
    return ExecutionContext(**data)


def visible(role: AgentRole, **overrides) -> set[str]:
    registry = build_catalog_registry()
    tools = registry.available_tools(context=full_context(role, **overrides), policy=ToolPolicy())
    return {tool.name for tool in tools}


def test_son_16_tools():
    assert len(build_catalog_registry().tools) == 16


@pytest.mark.parametrize("role", list(AgentRole))
def test_cada_rol_ve_exactamente_sus_tools(role):
    assert visible(role) == EXPECTED[role]


def test_un_agente_no_puede_llamar_tools_de_otro_rol():
    registry = build_catalog_registry()
    context = full_context(AgentRole.CRITICO)
    result = registry.run(
        ToolCall(tool_name="ejecutar_plan_aprobado", arguments={"plan_hash": "h"}),
        context=context,
        policy=ToolPolicy(),
    )
    assert result.metadata["error_type"] == "unavailable_tool"


def test_integracion_sin_permiso_de_escritura_no_ve_publicar():
    assert "ejecutar_plan_aprobado" not in visible(AgentRole.INTEGRACION, allow_external_writes=False)


def test_integracion_sin_drafts_no_ve_dry_run():
    assert "armar_plan_dry_run" not in visible(AgentRole.INTEGRACION, allow_drafts=False)


def run_publish(plan_hash: str, approved: str | None):
    registry = build_catalog_registry()
    context = full_context(AgentRole.INTEGRACION, approved_plan_hash=approved)
    return registry.run(
        ToolCall(tool_name="ejecutar_plan_aprobado", arguments={"plan_hash": plan_hash}),
        context=context,
        policy=ToolPolicy(),
    )


def test_publicar_sin_plan_aprobado_se_deniega():
    assert run_publish("abc", None).metadata["error_type"] == "authorization_error"


def test_publicar_con_hash_distinto_se_deniega():
    assert run_publish("abc", "otro").metadata["error_type"] == "authorization_error"


def test_publicar_con_plan_aprobado_pasa_la_policy():
    result = run_publish("abc", "abc")
    assert result.metadata["error_type"] == "not_implemented"


def test_policy_yaml_coincide_con_el_codigo():
    config = load_policy_config(POLICY_YAML)
    assert set(config.roles) == set(AgentRole)
    for role, role_policy in config.roles.items():
        assert set(role_policy.kinds) == ToolPolicy.KINDS_BY_ROLE[role]
        assert set(role_policy.tools) == EXPECTED[role]
