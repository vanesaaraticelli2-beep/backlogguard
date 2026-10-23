from datetime import date

import pytest
from pydantic import ValidationError

from backlogguard.board import (
    AgentRole,
    BacklogItem,
    Board,
    Citation,
    Finding,
    FindingKind,
    InvalidTransition,
    ItemKind,
    ItemState,
    Objection,
    SourceType,
)


def make_citation(**overrides) -> Citation:
    data = dict(
        fragment_id="m1-003",
        quote="El cliente pidió exportar a Excel.",
        source_name="Reunión kickoff",
        source_type=SourceType.REUNION,
        source_date=date(2026, 10, 5),
        speaker="Ana",
    )
    data.update(overrides)
    return Citation(**data)


def make_item(**overrides) -> BacklogItem:
    data = dict(id="H-1", kind=ItemKind.HISTORIA, title="Exportar reporte")
    data.update(overrides)
    return BacklogItem(**data)


def test_happy_path_borrador_a_aprobado():
    item = make_item(citations=[make_citation()])
    item.transition_to(ItemState.SUSTENTADO)
    item.transition_to(ItemState.APROBADO, actor="Full Stack IA Engineer")
    assert item.state is ItemState.APROBADO
    assert item.approved_by == "Full Stack IA Engineer"


def test_objecion_y_exclusion():
    item = make_item()
    item.transition_to(ItemState.OBJETADO)
    item.add_objection(
        Objection(id="o1", raised_by=AgentRole.CRITICO, text="La cita no sustenta.", round=1)
    )
    item.transition_to(ItemState.EXCLUIDO)
    assert item.state is ItemState.EXCLUIDO


@pytest.mark.parametrize(
    "start,target",
    [
        (ItemState.BORRADOR, ItemState.APROBADO),
        (ItemState.BORRADOR, ItemState.EXCLUIDO),
        (ItemState.OBJETADO, ItemState.APROBADO),
        (ItemState.SUSTENTADO, ItemState.BORRADOR),
    ],
)
def test_transiciones_ilegales(start, target):
    item = make_item(citations=[make_citation()])
    item.state = start
    with pytest.raises(InvalidTransition):
        item.transition_to(target, actor="alguien")


def test_estados_finales_no_salen():
    item = make_item(citations=[make_citation()])
    item.transition_to(ItemState.SUSTENTADO)
    item.transition_to(ItemState.EXCLUIDO)
    with pytest.raises(InvalidTransition):
        item.transition_to(ItemState.SUSTENTADO)


def test_sustentar_sin_cita_falla():
    item = make_item()
    with pytest.raises(InvalidTransition):
        item.transition_to(ItemState.SUSTENTADO)


def test_aprobar_exige_actor():
    item = make_item(citations=[make_citation()])
    item.transition_to(ItemState.SUSTENTADO)
    with pytest.raises(InvalidTransition):
        item.transition_to(ItemState.APROBADO)


def test_crear_item_aprobado_sin_trazabilidad_falla():
    with pytest.raises(ValidationError):
        make_item(state=ItemState.APROBADO, citations=[make_citation()])
    with pytest.raises(ValidationError):
        make_item(state=ItemState.SUSTENTADO)


def test_campos_extra_rechazados():
    with pytest.raises(ValidationError):
        make_item(inventado="x")


def test_cita_sin_fuente_o_texto_vacio_falla():
    with pytest.raises(ValidationError):
        make_citation(source_name="")
    with pytest.raises(ValidationError):
        make_citation(quote="")


def test_tope_de_rondas():
    with pytest.raises(ValidationError):
        Objection(id="o3", raised_by=AgentRole.CRITICO, text="x", round=3)


def test_tablero_hallazgo_requiere_item_existente():
    board = Board()
    finding = Finding(
        id="f1",
        kind=FindingKind.CAMBIO_DE_ALCANCE,
        raised_by=AgentRole.AUDITOR,
        addressee=AgentRole.SUPERVISOR,
        description="Tratado pero no vendido.",
        item_id="H-9",
    )
    with pytest.raises(ValueError):
        board.add_finding(finding)
    board.add_item(make_item(id="H-9"))
    board.add_finding(finding)
    assert len(board.findings) == 1


def test_tablero_rechaza_id_duplicado():
    board = Board()
    board.add_item(make_item())
    with pytest.raises(ValueError):
        board.add_item(make_item())
