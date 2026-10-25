from pathlib import Path

import pytest

from backlogguard.board import AgentRole
from backlogguard.rag import SourceLibrary
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry, load_policy_config
from backlogguard.tools.supervisor import SupervisorToolkit

ROOT = Path(__file__).resolve().parent.parent
POLICY = load_policy_config(ROOT / "config" / "policy.yaml")


@pytest.fixture
def toolkit():
    return SupervisorToolkit(SourceLibrary(ROOT / "evals" / "fixtures"), POLICY)


def run(toolkit, name, role=AgentRole.SUPERVISOR, **arguments):
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(user_id="u", role=role)
    return registry.run(ToolCall(tool_name=name, arguments=arguments), context=context, policy=ToolPolicy())


def test_las_tools_del_supervisor_son_solo_del_supervisor(toolkit):
    registry = build_catalog_registry(toolkit.implementations())
    context = ExecutionContext(user_id="u", role=AgentRole.SUPERVISOR)
    visible = {t.name: t.kind for t in ToolPolicy().allowed_tools(registry, context)}
    assert visible == {"delegar_tarea": "compute", "escalar_a_persona": "compute"}
    for role in (AgentRole.REQUERIMIENTOS, AgentRole.CRITICO, AgentRole.AUDITOR, AgentRole.INTEGRACION):
        denied = run(toolkit, "delegar_tarea", role=role, agent="critico", task="revisar")
        assert denied.metadata["error_type"] == "unavailable_tool"
    assert toolkit.delegations == [] and toolkit.escalations == []


def test_delegar_registra_una_tarea_valida(toolkit):
    result = run(toolkit, "delegar_tarea", agent="requerimientos", task="redactar",
                 sources=["reunion_01_kickoff"], instruction="Una historia por requerimiento.")
    assert result.ok and toolkit.delegations[0].sources == ["reunion_01_kickoff"]


@pytest.mark.parametrize(
    "arguments,error",
    [
        ({"agent": "critico", "task": "redactar"}, "invalid_task"),
        ({"agent": "requerimientos", "task": "redactar"}, "missing_sources"),
        ({"agent": "requerimientos", "task": "redactar", "sources": ["no_existe"]}, "unknown_source"),
        ({"agent": "requerimientos", "task": "redactar", "sources": ["../README"]}, "validation_error"),
        ({"agent": "integracion", "task": "redactar"}, "validation_error"),
    ],
)
def test_delegar_valida_agente_tarea_y_fuentes(toolkit, arguments, error):
    assert run(toolkit, "delegar_tarea", **arguments).metadata["error_type"] == error
    assert toolkit.delegations == []


def test_delegar_no_repite_agente_ni_supera_el_maximo(toolkit):
    run(toolkit, "delegar_tarea", agent="critico", task="revisar")
    assert run(toolkit, "delegar_tarea", agent="critico", task="revisar").metadata["error_type"] == "duplicate_delegation"
    limited = SupervisorToolkit(SourceLibrary(ROOT / "evals" / "fixtures"), POLICY, max_delegations=1)
    run(limited, "delegar_tarea", agent="critico", task="revisar")
    assert run(limited, "delegar_tarea", agent="auditor", task="auditar").metadata["error_type"] == "too_many_delegations"


@pytest.mark.parametrize(
    "reason,decides",
    [
        ("cambio_de_alcance", "service_manager"),
        ("vendido_no_tratado", "service_manager"),
        ("contradiccion", "product_owner"),
        ("desacuerdo_sin_consenso", "product_owner"),
    ],
)
def test_escalar_usa_la_politica_y_no_duplica(toolkit, reason, decides):
    first = run(toolkit, "escalar_a_persona", reason=reason, ref="HU-1", detail="motivo")
    again = run(toolkit, "escalar_a_persona", reason=reason, ref="HU-1")
    assert first.ok and first.metadata["decides"] == decides
    assert again.ok and "ya estaba registrada" in again.content and len(toolkit.escalations) == 1


def test_el_modelo_no_puede_elegir_quien_decide_ni_inventar_razones(toolkit):
    forged = run(toolkit, "escalar_a_persona", reason="contradiccion", ref="HU-1", decides="nadie")
    assert forged.metadata["error_type"] == "validation_error"
    invented = run(toolkit, "escalar_a_persona", reason="porque_si", ref="HU-1")
    assert invented.metadata["error_type"] == "validation_error" and toolkit.escalations == []
