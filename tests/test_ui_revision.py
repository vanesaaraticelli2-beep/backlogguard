"""La pestaña «Revisión» con el probador de Streamlit: un catálogo temporal, sin modelos y sin tocar los datos reales."""
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest
from test_catalogo import draft, evidence, proposal

from backlogguard.catalog import Catalog, ProposalKind, ProposalState
from backlogguard.rag import SourceLibrary
from backlogguard.rag.sources import SourceMetadata


def page():
    import os
    from pathlib import Path
    from types import SimpleNamespace

    import streamlit as st

    from backlogguard.catalog import Catalog
    from backlogguard.ui.revision import tab_catalog, tab_review

    data = Path(os.environ["BG_TEST_DATA"])
    controller = SimpleNamespace(deps=SimpleNamespace(catalog=Catalog(data / "catalogo.sqlite")), data_dir=data)
    who = SimpleNamespace(role=os.environ["BG_TEST_ROLE"], name="x")
    review, catalog = st.tabs(["Revisión", "Catálogo"])
    with review:
        tab_review(controller, who)
    with catalog:
        tab_catalog(controller)


@pytest.fixture
def world(tmp_path, monkeypatch):
    library = SourceLibrary(tmp_path / "fuentes")
    library.write("reunion_01", SourceMetadata(source_name="Reunión 1", source_type="reunion", source_date=date(2026, 1, 25), layout="dialogo"), "Ana: Hola.\n")
    catalog = Catalog(tmp_path / "catalogo.sqlite")
    for key, title, conf in (("a", "Validar el CUIT antes de crear la cuenta", 0.93), ("b", "Avisar por mail al administrativo", 0.72)):
        catalog.propose(proposal(key=key, drafts=[draft(title)], ev=[evidence()]).model_copy(update={"confidence": conf}))
    catalog.propose(proposal(ProposalKind.INCIERTO, key="c", drafts=[draft("Formato de los adjuntos")], ev=[evidence(quote="los típicos no hay problema")]))
    monkeypatch.setenv("BG_TEST_DATA", str(tmp_path))
    return catalog


def run(role):
    import os

    os.environ["BG_TEST_ROLE"] = role
    return AppTest.from_function(page, default_timeout=30).run()


def button(at, text):
    return next(b for b in at.button if text in b.label)


def test_muestra_las_pendientes_y_el_detalle_con_la_cita(world):
    at = run("product_owner")
    assert not at.exception
    assert [m.value for m in at.metric[:3]] == ["3", "0", "0"]
    assert "hay que validar el CUIT" in " ".join(m.value for m in at.markdown)


def test_el_product_owner_aprueba_una_y_queda_en_el_catalogo(world):
    at = run("product_owner")
    button(at, "Aprobar").click()
    at.run()
    assert not at.exception
    assert [r.id for r in world.requirements()] == ["RQ-001"]
    assert world.proposal("P-001").state is ProposalState.APLICADA and world.proposal("P-001").decided_by == "product_owner"
    assert [m.value for m in at.metric[:3]] == ["2", "1", "0"]


def test_otro_rol_ve_los_botones_deshabilitados_y_nada_cambia(world):
    at = run("full_stack_ia_engineer")
    assert button(at, "Aprobar").disabled and button(at, "Rechazar").disabled and button(at, "Aprobar ese lote").disabled
    assert world.requirements() == []


def test_el_lote_solo_aprueba_lo_que_supera_el_umbral(world):
    at = run("product_owner")
    button(at, "Aprobar ese lote").click()
    at.run()
    assert not at.exception
    assert [p.id for p in world.proposals(state=ProposalState.APLICADA)] == ["P-001"]  # P-002 tiene 0,72 < 0,80
    assert [p.id for p in world.proposals(state=ProposalState.PENDIENTE)] == ["P-002", "P-003"]


def test_un_incierto_no_se_puede_aprobar_pero_se_reclasifica(world):
    at = run("product_owner")
    next(b for b in at.button if b.label.startswith("P-003")).click()
    at.run()
    assert not [b for b in at.button if b.label == "Aprobar"]
    button(at, "Reclasificar").click()
    at.run()
    assert not at.exception
    assert world.proposal("P-003").kind is ProposalKind.NUEVO and world.proposal("P-003").state is ProposalState.PENDIENTE


def test_el_catalogo_lista_los_requisitos_aprobados(world):
    at = run("product_owner")
    button(at, "Aprobar").click()
    at.run()
    assert any("RQ-001" in e.label for e in at.expander)
