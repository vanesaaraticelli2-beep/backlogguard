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
    controller = SimpleNamespace(
        deps=SimpleNamespace(catalog=Catalog(data / "catalogo.sqlite")),
        data_dir=data,
        read_only=False,
        running=False,
    )
    who = SimpleNamespace(role=os.environ["BG_TEST_ROLE"], name="x")
    review, catalog = st.tabs(["Revisión", "Catálogo"])
    with review:
        tab_review(controller, who)
    with catalog:
        tab_catalog(controller, who)


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


def test_retiro_explicito_requiere_confirmacion_y_no_escribe_azure(world):
    decided = world.decide("P-001", approve=True, by="product_owner")
    requirement_id = world.apply(decided.id).affected[0]
    world.mark_published(requirement_id, remote_id=8123)
    before = run("full_stack_ia_engineer")

    assert not before.exception
    assert button(before, "Retirar requisito").disabled
    before.text_input(key="catalog_retire_reason").set_value("Ya no forma parte del alcance").run()
    before.checkbox(key="catalog_retire_confirm").check().run()
    button(before, "Retirar requisito").click().run()

    assert not before.exception
    assert world.requirement(requirement_id).status.value == "retirado"
    assert world.retirement_decision(requirement_id)["retired_by"] == "x"
    assert any("Azure todavía no fue modificado" in item.value for item in before.caption)


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


def test_el_catalogo_muestra_la_cobertura_de_lo_vendido_si_hay_compromisos(world, tmp_path):
    from backlogguard.rag.compromisos import Baseline, BaselineStore, Commitment

    library = SourceLibrary(tmp_path / "fuentes")
    library.write("preventa", SourceMetadata(source_name="Propuesta", source_type="preventa", source_date=date(2026, 1, 5), layout="dialogo"), "Vendedor: Incluye un portal.\n")
    commitment = Commitment(id="C-001", epic="Portal", capability="Portal de clientes", scope="incluido", page=1, quote="Incluye un portal")
    BaselineStore(tmp_path / "linea_base").save(
        Baseline(document_id="preventa", fingerprint=library.load("preventa").fingerprint, model="m", extracted_at="2026-11-02", commitments=[commitment])
    )
    at = run("product_owner")
    assert not at.exception
    assert any("Cobertura de lo vendido" in e.label for e in at.expander)
    assert "Ninguna reunión fue leída todavía" in " ".join(w.value for w in at.warning)


def test_una_propuesta_rechazada_se_reabre_desde_la_pantalla(world):
    world.decide("P-001", approve=False, by="product_owner", note="vínculo incoherente")
    at = run("product_owner")
    at.button(key="sel-P-001").click().run()  # se elige la rechazada en «Resueltas»
    assert any("Reabrir" in b.label for b in at.button)
    button(at, "Reabrir").click()
    at.run()
    assert not at.exception
    assert world.proposal("P-001").state is ProposalState.PENDIENTE and "vínculo incoherente" in world.proposal("P-001").note


def test_otro_rol_no_puede_reabrir(world):
    world.decide("P-001", approve=False, by="product_owner")
    at = run("service_manager")
    at.button(key="sel-P-001").click().run()
    assert button(at, "Reabrir").disabled


def test_confidence_level_colors():
    from backlogguard.ui.revision import confidence_level

    assert confidence_level(0.55)[1] == "baja" and confidence_level(0.69)[1] == "baja"
    assert confidence_level(0.70)[1] == "media" and confidence_level(0.79)[1] == "media"
    assert confidence_level(0.80)[1] == "alta" and confidence_level(1.0)[1] == "alta"
    assert len({confidence_level(v)[0] for v in (0.5, 0.75, 0.9)}) == 3


def test_al_rechazar_pasa_a_la_siguiente_de_la_lista(world):
    at = run("product_owner")
    button(at, "P-002").click()
    at.run()
    button(at, "Rechazar").click()
    at.run()
    assert not at.exception and world.proposal("P-002").state is ProposalState.RECHAZADA
    assert at.session_state["rev_sel"] == "P-003"  # la que sigue, no la primera


def test_al_descartar_un_incierto_pasa_a_la_siguiente(world):
    at = run("product_owner")
    button(at, "P-003").click()
    at.run()
    button(at, "Descartar").click()
    at.run()
    assert not at.exception and world.proposal("P-003").state is ProposalState.RECHAZADA
    assert at.session_state["rev_sel"] == "P-001"  # no quedan más abajo: vuelve a la primera pendiente


def test_el_por_que_separa_catalogo_y_preventa():
    from backlogguard.catalog import LinkCheck
    from backlogguard.ui.revision import reason_parts

    p = proposal(key="z", drafts=[draft("Escanear DNI")], ev=[evidence()]).model_copy(update={
        "rationale": "Ningún requisito aprobado dice lo mismo. | Vínculos con la propuesta: C-191 confirmado (difiere: x).",
        "links": [LinkCheck(commitment_id="C-191", relation="mismo", difference="propuesta: escanear; reunión: autocompletar"),
                  LinkCheck(commitment_id="C-013", relation="distinto", reason="es el CRUD genérico")],
    })
    catalog_text, lines = reason_parts(p)
    assert catalog_text == "Ningún requisito aprobado dice lo mismo."
    from types import SimpleNamespace

    titled = reason_parts(p, {"C-191": SimpleNamespace(capability="Escanear DNI para tomar datos")})[1]
    assert titled[0].startswith("**C-191** «Escanear DNI para tomar datos» confirmado") and titled[1].startswith("**C-013** descartado")
    assert lines[0] == "**C-191** confirmado · difiere: propuesta: escanear; reunión: autocompletar"
    assert lines[1] == "**C-013** descartado · es el CRUD genérico"
    old = p.model_copy(update={"links": []})  # propuesta vieja: queda el texto del motivo
    assert reason_parts(old)[1] == ["C-191 confirmado (difiere: x)."]
    assert reason_parts(p.model_copy(update={"rationale": "Solo catálogo.", "links": []})) == ("Solo catálogo.", [])


def test_el_rotulo_de_la_confianza_dice_en_que(world):
    at = run("product_owner")
    texts = " ".join(m.value for m in at.markdown)
    assert "Confianza en que es nuevo" in texts


def test_al_decidir_la_pantalla_pide_subir_al_titulo_de_la_siguiente(world):
    at = run("product_owner")
    assert not [h for h in at.get("html") if "bg-detail-top" in str(h.proto)]  # sin decidir, no se mueve
    button(at, "Rechazar").click()
    at.run()
    assert not at.exception
    scripts = [h for h in at.get("html") if "scrollIntoView" in str(h.proto) and "bg-detail-top" in str(h.proto)]
    assert len(scripts) == 1
    at.run()  # una recarga cualquiera no vuelve a subir
    assert not [h for h in at.get("html") if "scrollIntoView" in str(h.proto)]


def test_al_entrar_queda_elegida_la_reunion_con_pendientes(world, tmp_path):
    library = SourceLibrary(tmp_path / "fuentes")
    library.write("reunion_00", SourceMetadata(source_name="Reunión 0", source_type="reunion", source_date=date(2026, 1, 20), layout="dialogo"), "Ana: Hola.\n")
    world.propose(proposal(key="d", drafts=[draft("Algo de la reunión 0")], ev=[evidence()]).model_copy(update={"source_id": "reunion_00"}))
    from backlogguard.catalog.review import decide_one

    decide_one(world, world.proposals(source_id="reunion_00")[0].id, approve=False, role="product_owner")  # la primera reunión ya no tiene pendientes
    at = run("product_owner")
    assert not at.exception
    assert at.session_state["rev_reunion"] == "reunion_01"
