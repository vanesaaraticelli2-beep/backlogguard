"""Revisión humana de las propuestas: lotes, decisiones individuales, roles y reclasificación de inciertos."""
import pytest
from test_catalogo import approve_and_apply, draft, evidence, proposal

from backlogguard.catalog import Catalog, CatalogError, ProposalKind, ProposalState, RequirementStatus
from backlogguard.catalog.review import (
    PRODUCT_OWNER,
    SERVICE_MANAGER,
    decide_batch,
    decide_one,
    decider_role,
    pending_batch,
    pending_individual,
)


@pytest.fixture
def catalog(tmp_path):
    return Catalog(tmp_path / "catalogo.sqlite")


def existing(catalog):
    return approve_and_apply(catalog, catalog.propose(proposal(key="base", source_id="reunion_00", fp="old"))).affected[0]


def test_el_lote_solo_junta_nuevo_y_refina_en_orden(catalog):
    rid = existing(catalog)
    catalog.propose(proposal(key="a"))
    catalog.propose(proposal(ProposalKind.REFINA, key="b", targets=[rid]))
    catalog.propose(proposal(ProposalKind.CONTRADICE, key="c", targets=[rid]))
    catalog.propose(proposal(ProposalKind.INCIERTO, key="d", drafts=[draft()]))
    assert [p.candidate_key for p in pending_batch(catalog, "reunion_01")] == ["a", "b"]
    assert [p.candidate_key for p in pending_individual(catalog, "reunion_01")] == ["c", "d"]


def test_una_reunion_fuera_de_orden_no_admite_lote(catalog):
    saved = catalog.propose(proposal(key="a").model_copy(update={"out_of_order": True}))
    assert pending_batch(catalog, "reunion_01") == []
    with pytest.raises(CatalogError, match="una por una"):
        decide_batch(catalog, [saved.id], approve=True, role=PRODUCT_OWNER)


def test_aprobar_un_lote_crea_los_requisitos_y_guarda_el_rol(catalog):
    first, second = catalog.propose(proposal(key="a")), catalog.propose(proposal(key="b", drafts=[draft("Otra cosa distinta")]))
    result = decide_batch(catalog, [first.id, second.id], approve=True, role=PRODUCT_OWNER)
    assert [p.state for p in result.applied] == [ProposalState.APLICADA] * 2
    assert {r.id for r in catalog.requirements()} == {"RQ-001", "RQ-002"}
    assert catalog.requirement("RQ-001").current.approved_by == PRODUCT_OWNER


def test_un_lote_con_una_propuesta_que_no_corresponde_no_cambia_nada(catalog):
    rid = existing(catalog)
    ok, scope = catalog.propose(proposal(key="a")), catalog.propose(proposal(ProposalKind.CONTRADICE, key="c", targets=[rid]))
    with pytest.raises(CatalogError, match="una por una"):
        decide_batch(catalog, [ok.id, scope.id], approve=True, role=PRODUCT_OWNER)
    assert catalog.proposal(ok.id).state is ProposalState.PENDIENTE
    assert len(catalog.requirements()) == 1


def test_rechazar_un_lote_no_toca_el_catalogo(catalog):
    saved = catalog.propose(proposal(key="a"))
    result = decide_batch(catalog, [saved.id], approve=False, role=PRODUCT_OWNER, note="no es de este proyecto")
    assert result.rejected[0].state is ProposalState.RECHAZADA and result.rejected[0].note == "no es de este proyecto"
    assert catalog.requirements() == []


def test_un_cambio_de_alcance_lo_decide_el_service_manager(catalog):
    rid = existing(catalog)
    saved = catalog.propose(proposal(ProposalKind.CONTRADICE, key="c", targets=[rid]))
    assert decider_role(saved) == SERVICE_MANAGER
    with pytest.raises(CatalogError, match="service_manager"):
        decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER)
    done = decide_one(catalog, saved.id, approve=True, role=SERVICE_MANAGER)
    assert done.state is ProposalState.APLICADA and done.decided_by == SERVICE_MANAGER


def test_una_division_aprobada_deja_al_original_dividido(catalog):
    rid = existing(catalog)
    saved = catalog.propose(proposal(ProposalKind.DIVIDE, key="s", targets=[rid], drafts=[draft("Parte uno del pedido"), draft("Parte dos del pedido")]))
    decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER)
    assert catalog.requirement(rid).status is RequirementStatus.DIVIDIDO


def test_un_incierto_no_se_aprueba_pero_se_reclasifica_o_se_descarta(catalog):
    saved = catalog.propose(proposal(ProposalKind.INCIERTO, key="d", drafts=[draft()]))
    with pytest.raises(CatalogError, match="reclasific"):
        decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER)
    resolved = catalog.reclassify(saved.id, ProposalKind.NUEVO)
    assert resolved.kind is ProposalKind.NUEVO and resolved.state is ProposalState.PENDIENTE and catalog.requirements() == []
    assert decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER).affected == ["RQ-001"]
    other = catalog.propose(proposal(ProposalKind.INCIERTO, key="e", drafts=[draft("No es un requisito real")]))
    assert decide_one(catalog, other.id, approve=False, role=PRODUCT_OWNER).state is ProposalState.RECHAZADA


def test_reclasificar_a_cubierto_exige_un_destino_activo_y_suma_evidencia(catalog):
    rid = existing(catalog)
    saved = catalog.propose(proposal(ProposalKind.INCIERTO, key="d", drafts=[draft("Lo mismo dicho de otra forma")], ev=[evidence(quote="validar siempre el CUIT")]))
    with pytest.raises(CatalogError, match="destino"):
        catalog.reclassify(saved.id, ProposalKind.CUBIERTO)
    with pytest.raises(CatalogError, match="solo se resuelve"):
        catalog.reclassify(saved.id, ProposalKind.DIVIDE, target=rid)
    catalog.reclassify(saved.id, ProposalKind.CUBIERTO, target=rid)
    decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER)
    assert len(catalog.requirement(rid).current.evidence) == 2


def test_solo_se_reclasifica_un_incierto(catalog):
    saved = catalog.propose(proposal(key="a"))
    with pytest.raises(CatalogError, match="incierto"):
        catalog.reclassify(saved.id, ProposalKind.NUEVO)


def test_editar_el_borrador_antes_de_aprobar_cambia_lo_que_se_guarda(catalog):
    saved = catalog.propose(proposal(key="a"))
    catalog.edit(saved.id, draft("Validar el CUIT con ARCA"))
    decide_one(catalog, saved.id, approve=True, role=PRODUCT_OWNER)
    assert catalog.requirement("RQ-001").current.draft.title == "Validar el CUIT con ARCA"
    with pytest.raises(CatalogError, match="editar"):
        catalog.edit(saved.id, draft("Ya no se puede"))


def test_una_decision_sin_rol_se_rechaza(catalog):
    saved = catalog.propose(proposal(key="a"))
    with pytest.raises(CatalogError):
        catalog.decide(saved.id, approve=True, by=" ")
