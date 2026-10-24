from datetime import date

import pytest

from backlogguard.memory import ProjectMemory


@pytest.fixture
def memory(tmp_path):
    return ProjectMemory(tmp_path / "memory.sqlite", project_id="p1")


def decide(memory: ProjectMemory, text: str, *, approved_by="Service manager", **kwargs):
    return memory.register_decision(
        "formato-reporte",
        text,
        decided_on=kwargs.pop("decided_on", date(2026, 10, 5)),
        speaker="Ana",
        authority="cliente",
        source="Reunión kickoff",
        quote="Queremos exportar a Excel.",
        approved_by=approved_by,
        **kwargs,
    )


def test_decision_sin_aprobacion_humana_se_rechaza(memory):
    with pytest.raises(ValueError):
        decide(memory, "Exportar a Excel", approved_by=None)
    assert memory.current_decisions() == []


def test_decision_aprobada_guarda_trazabilidad(memory):
    decide(memory, "Exportar a Excel")
    [item] = memory.current_decisions()
    assert item["value"]["approved_by"] == "Service manager"
    assert item["value"]["speaker"] == "Ana" and item["value"]["decided_on"] == "2026-10-05"


def test_decision_evolucionada_reemplaza_a_la_vigente(memory):
    old_id = decide(memory, "Exportar a Excel")
    decide(memory, "Exportar a PDF", decided_on=date(2026, 10, 19), supersedes=old_id)
    [current] = memory.current_decisions()
    assert current["value"]["decision"] == "Exportar a PDF"
    history = memory.decision_history("formato-reporte")
    assert {item["status"] for item in history} == {"active", "superseded"}


def test_preguntas_pendientes_y_resolucion(memory):
    question_id = memory.register_open_question(
        "api-pagos", "¿Qué proveedor de pagos?", source="Minuta 3", approved_by="PO"
    )
    assert [q["value"]["question"] for q in memory.open_questions()] == ["¿Qué proveedor de pagos?"]
    memory.resolve_question(question_id)
    assert memory.open_questions() == []


def test_decisiones_y_preguntas_no_se_mezclan(memory):
    decide(memory, "Exportar a Excel")
    memory.register_open_question("api-pagos", "¿Proveedor?", source="Minuta 3", approved_by="PO")
    assert len(memory.current_decisions()) == 1 and len(memory.open_questions()) == 1


def test_proyectos_aislados(tmp_path):
    path = tmp_path / "memory.sqlite"
    decide(ProjectMemory(path, "p1"), "Exportar a Excel")
    assert ProjectMemory(path, "p2").current_decisions() == []
