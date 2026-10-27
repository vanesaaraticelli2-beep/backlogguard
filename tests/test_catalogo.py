"""Catálogo persistente: identidad estable, versiones, evidencias, propuestas aprobadas y fuentes idempotentes."""
from datetime import date

import pytest
from pydantic import ValidationError

from backlogguard.board import SourceType
from backlogguard.catalog import (
    Catalog,
    CatalogError,
    Draft,
    Evidence,
    EvidenceRole,
    Proposal,
    ProposalKind,
    ProposalState,
    Relation,
    RequirementStatus,
)


def evidence(fragment="reunion_01:1", quote="hay que validar el CUIT", source_id="reunion_01", fp="aaaa", kind=SourceType.REUNION, page=None):
    return Evidence(
        fragment_id=fragment, quote=quote, source_name="Reunión 1", source_type=kind, source_date=date(2026, 1, 25),
        page=page, source_id=source_id, source_fingerprint=fp,
    )


def draft(title="Validar el CUIT antes de crear la cuenta", **extra):
    return Draft(title=title, description="d", acceptance_criteria=["a"], **extra)


def proposal(kind=ProposalKind.NUEVO, key="c1", targets=(), drafts=None, ev=None, source_id="reunion_01", fp="aaaa"):
    drafts = [draft()] if drafts is None and kind in (ProposalKind.NUEVO, ProposalKind.REFINA) else (drafts or [])
    return Proposal(source_id=source_id, fingerprint=fp, candidate_key=key, kind=kind, targets=list(targets), drafts=drafts, evidence=ev or [evidence()])


@pytest.fixture
def catalog(tmp_path):
    return Catalog(tmp_path / "catalogo.sqlite")


def approve_and_apply(catalog, saved, by="PO"):
    catalog.decide(saved.id, approve=True, by=by)
    return catalog.apply(saved.id)


def test_un_requisito_nuevo_necesita_aprobacion_y_recibe_un_id_estable(catalog):
    saved = catalog.propose(proposal())
    assert saved.id == "P-001" and saved.state is ProposalState.PENDIENTE
    with pytest.raises(CatalogError, match="no está aprobada"):
        catalog.apply(saved.id)
    assert catalog.requirements() == []  # nada cambia hasta que una persona aprueba
    done = approve_and_apply(catalog, saved)
    assert done.state is ProposalState.APLICADA and done.affected == ["RQ-001"]
    req = catalog.requirement("RQ-001")
    assert req.status is RequirementStatus.ACTIVO and req.current.number == 1 and req.current.relation is Relation.NUEVO
    assert req.current.approved_by == "PO" and [e.quote for e in req.current.evidence] == ["hay que validar el CUIT"]


def test_el_id_no_depende_del_titulo_ni_se_reutiliza(catalog):
    first = approve_and_apply(catalog, catalog.propose(proposal(key="a")))
    second = approve_and_apply(catalog, catalog.propose(proposal(key="b")))  # mismo título, otro candidato
    assert first.affected == ["RQ-001"] and second.affected == ["RQ-002"]
    assert catalog.requirement("RQ-001").current.draft.title == catalog.requirement("RQ-002").current.draft.title


def test_decidir_exige_un_rol_y_una_propuesta_decidida_no_se_decide_dos_veces(catalog):
    saved = catalog.propose(proposal())
    with pytest.raises(CatalogError, match="rol"):
        catalog.decide(saved.id, approve=True, by="  ")
    catalog.decide(saved.id, approve=False, by="PO", note="no aplica")
    with pytest.raises(CatalogError, match="ya está rechazada"):
        catalog.decide(saved.id, approve=True, by="PO")
    with pytest.raises(CatalogError, match="no está aprobada"):
        catalog.apply(saved.id)
    assert catalog.requirements() == []


def test_refinar_crea_una_version_nueva_y_conserva_la_anterior(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    refine = proposal(ProposalKind.REFINA, key="c2", targets=[rid], drafts=[draft("Validar el CUIT y mostrar el dato oficial")], ev=[evidence("reunion_02:4", "y que muestre el dato oficial", "reunion_02", "bbbb")])
    approve_and_apply(catalog, catalog.propose(refine))
    req = catalog.requirement(rid)
    assert [v.number for v in req.versions] == [1, 2] and req.current.number == 2 and req.current.relation is Relation.REFINA
    assert req.versions[0].draft.title == "Validar el CUIT antes de crear la cuenta" and not req.versions[0].current
    assert len(req.current.evidence) == 2  # la evidencia de la versión 1 sigue sosteniendo al requisito


def test_ya_cubierto_suma_evidencia_sin_versionar_ni_pedir_aprobacion(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    covered = catalog.propose(proposal(ProposalKind.CUBIERTO, key="c9", targets=[rid], ev=[evidence("reunion_03:2", "lo mismo del CUIT", "reunion_03", "cccc")]))
    done = catalog.apply_covered(covered.id)
    req = catalog.requirement(rid)
    assert done.state is ProposalState.APLICADA and req.current.number == 1
    assert {e.role for e in req.current.evidence} == {EvidenceRole.ORIGEN, EvidenceRole.REFUERZO}
    with pytest.raises(CatalogError, match="Solo se aplica sin aprobación"):
        catalog.apply_covered(catalog.propose(proposal(key="otra")).id)  # un requisito nuevo sí necesita persona


def test_la_misma_evidencia_no_se_duplica(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    for key in ("x1", "x2"):
        saved = catalog.propose(proposal(ProposalKind.CUBIERTO, key=key, targets=[rid], ev=[evidence("reunion_03:2", "lo mismo", "reunion_03", "cccc")]))
        catalog.apply_covered(saved.id)
    assert len(catalog.requirement(rid).current.evidence) == 2


def test_contradecir_sin_reemplazo_deja_el_conflicto_anotado_y_el_requisito_intacto(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    conflict = proposal(ProposalKind.CONTRADICE, key="k", targets=[rid], drafts=[], ev=[evidence("reunion_04:7", "el CUIT ya no se valida", "reunion_04", "dddd")])
    assert catalog.propose(conflict).needs_human_alone
    approve_and_apply(catalog, catalog.proposals(state=ProposalState.PENDIENTE)[0])
    req = catalog.requirement(rid)
    assert req.current.number == 1 and [c.quote for c in req.conflicts] == ["el CUIT ya no se valida"]
    assert all(e.role is not EvidenceRole.CONTRADICE for e in req.current.evidence)


def test_contradecir_con_reemplazo_versiona_con_relacion_reemplaza(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    saved = catalog.propose(proposal(ProposalKind.CONTRADICE, key="k", targets=[rid], drafts=[draft("No validar el CUIT")], ev=[evidence("reunion_04:7", "ya no se valida", "reunion_04", "dddd")]))
    approve_and_apply(catalog, saved)
    assert catalog.requirement(rid).current.relation is Relation.REEMPLAZA and catalog.requirement(rid).current.number == 2


def test_dividir_deja_el_original_dividido_y_enlaza_las_partes(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    parts = [draft("Validar el formato del CUIT"), draft("Consultar el CUIT en ARCA")]
    saved = catalog.propose(proposal(ProposalKind.DIVIDE, key="d", targets=[rid], drafts=parts, ev=[evidence("reunion_05:1", "son dos cosas distintas", "reunion_05", "eeee")]))
    done = approve_and_apply(catalog, saved)
    assert done.affected == [rid, "RQ-002", "RQ-003"]
    original = catalog.requirement(rid)
    assert original.status is RequirementStatus.DIVIDIDO and original.replaced_by == ["RQ-002", "RQ-003"]
    child = catalog.requirement("RQ-002")
    assert child.current.relation is Relation.DIVIDE and child.current.parents == [rid]


def test_fusionar_une_requisitos_activos_en_uno_nuevo(catalog):
    a = approve_and_apply(catalog, catalog.propose(proposal(key="a"))).affected[0]
    b = approve_and_apply(catalog, catalog.propose(proposal(key="b", drafts=[draft("Mostrar el dato oficial")]))).affected[0]
    saved = catalog.propose(proposal(ProposalKind.FUSIONA, key="f", targets=[a, b], drafts=[draft("Validar y mostrar el dato fiscal")], ev=[evidence("reunion_06:3", "es lo mismo", "reunion_06", "ffff")]))
    merged = approve_and_apply(catalog, saved).affected[-1]
    assert catalog.requirement(a).status is RequirementStatus.FUSIONADO and catalog.requirement(b).replaced_by == [merged]
    assert catalog.requirement(merged).current.relation is Relation.FUSIONA and catalog.requirement(merged).current.parents == [a, b]


def test_no_se_cambia_un_requisito_que_ya_no_esta_activo(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    parts = [draft("Validar el formato del CUIT"), draft("Consultar el CUIT en ARCA")]
    approve_and_apply(catalog, catalog.propose(proposal(ProposalKind.DIVIDE, key="d", targets=[rid], drafts=parts, ev=[evidence("r5:1", "dos cosas", "reunion_05", "eeee")])))
    late = catalog.propose(proposal(ProposalKind.REFINA, key="late", targets=[rid], ev=[evidence("r7:1", "ajuste", "reunion_07", "gggg")]))
    catalog.decide(late.id, approve=True, by="PO")
    with pytest.raises(CatalogError, match="no está activo"):
        catalog.apply(late.id)


def test_la_preventa_sola_no_alcanza_como_evidencia(catalog):
    only_presale = [evidence("propuesta:5", "Se incluye la validación del CUIT", "propuesta", "pppp", SourceType.PREVENTA, page=7)]
    with pytest.raises(ValidationError, match="la preventa no alcanza"):
        proposal(ev=only_presale)
    both = proposal(ev=[*only_presale, evidence()])  # con una cita de reunión sí
    assert len(catalog.propose(both).evidence) == 2


def test_la_forma_de_cada_propuesta_se_valida():
    with pytest.raises(ValidationError, match="dos borradores"):
        proposal(ProposalKind.DIVIDE, targets=["RQ-001"], drafts=[draft()])
    with pytest.raises(ValidationError, match="al menos dos destinos"):
        proposal(ProposalKind.FUSIONA, targets=["RQ-001"], drafts=[draft()])
    with pytest.raises(ValidationError, match="sin destino"):
        proposal(ProposalKind.NUEVO, targets=["RQ-001"])


def test_reprocesar_la_misma_fuente_no_duplica_propuestas(catalog):
    first = catalog.propose(proposal())
    again = catalog.propose(proposal())
    assert again.id == first.id and len(catalog.proposals()) == 1
    changed = catalog.propose(proposal(fp="zzzz"))  # otra huella = otra lectura
    assert changed.id != first.id


def test_las_fuentes_procesadas_se_reconocen_por_id_y_huella(catalog):
    assert catalog.source_status("reunion_01", "aaaa") == "nueva"
    catalog.mark_source_processed("reunion_01", "aaaa")
    catalog.mark_source_processed("reunion_01", "aaaa")
    assert catalog.source_status("reunion_01", "aaaa") == "procesada" and len(catalog.processed_sources()) == 1
    assert catalog.source_status("reunion_01", "bbbb") == "cambiada" and catalog.source_status("reunion_02", "aaaa") == "nueva"


def test_el_catalogo_sobrevive_a_un_reinicio_y_solo_se_vacia_a_pedido(tmp_path):
    path = tmp_path / "catalogo.sqlite"
    first = Catalog(path)
    approve_and_apply(first, first.propose(proposal()))
    first.mark_source_processed("reunion_01", "aaaa")
    reopened = Catalog(path)  # otro proceso, otra corrida
    assert [r.id for r in reopened.requirements()] == ["RQ-001"] and reopened.source_status("reunion_01", "aaaa") == "procesada"
    reopened.clear()
    assert reopened.requirements() == [] and reopened.proposals() == [] and reopened.source_status("reunion_01", "aaaa") == "nueva"
    assert approve_and_apply(reopened, reopened.propose(proposal())).affected == ["RQ-001"]  # los ids vuelven a empezar


def test_la_clave_de_publicacion_cambia_con_la_version_y_marca_cuando_hay_que_actualizar(catalog):
    rid = approve_and_apply(catalog, catalog.propose(proposal())).affected[0]
    key_v1 = catalog.publication_key(rid)
    assert catalog.publication(rid) is None
    catalog.mark_published(rid, remote_id=501)
    assert catalog.publication(rid) == {**catalog.publication(rid), "remote_id": 501, "version": 1, "needs_update": False}
    approve_and_apply(catalog, catalog.propose(proposal(ProposalKind.REFINA, key="r", targets=[rid], drafts=[draft("Validar el CUIT y el dominio")], ev=[evidence("r2:1", "ajuste", "reunion_02", "bbbb")])))
    assert catalog.publication_key(rid) != key_v1 and catalog.publication(rid)["needs_update"] is True
    catalog.mark_published(rid, remote_id=501)  # se actualiza el mismo ítem remoto
    assert catalog.publication(rid)["needs_update"] is False and catalog.publication(rid)["version"] == 2


# ---- conexión con la corrida y la pantalla ----

from pathlib import Path  # noqa: E402

from backlogguard.llm import Settings  # noqa: E402
from backlogguard.rag import SourceLibrary  # noqa: E402
from backlogguard.rag.sources import SourceMetadata  # noqa: E402
from backlogguard.ui.controller import RunController  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def project(tmp_path, monkeypatch):
    data = tmp_path / "datos"
    library = SourceLibrary(data / "fuentes")
    library.write("propuesta", SourceMetadata(source_name="P", source_type="preventa", source_date=date(2025, 10, 1), layout="paginas"), "[[página 1]]\nTexto.\n")
    library.write("reunion", SourceMetadata(source_name="R", source_type="reunion", source_date=date(2026, 1, 25), layout="dialogo"), "Ana: Hola.\n")
    monkeypatch.setattr(RunController, "_spawn", lambda self, work, *args: None)  # no se llama a ningún modelo
    return RunController(ROOT, Settings(live_mode=True, anthropic_api_key="x", gemini_api_key="x"), data), data


def test_iniciar_una_corrida_con_fuentes_propias_no_borra_la_memoria_durable(project):
    controller, data = project
    approve_and_apply(controller.deps.catalog, controller.deps.catalog.propose(proposal()))
    controller.deps.memory.register_decision("d1", "Se valida el CUIT", decided_on=date(2026, 1, 25), speaker="Ana", authority="PO", source="r", quote="q", approved_by="PO")
    controller.start("Armá el backlog")
    assert [r.id for r in controller.deps.catalog.requirements()] == ["RQ-001"]
    assert len(controller.deps.memory.current_decisions()) == 1  # sigue ahí en la corrida siguiente
    controller.start("Otra corrida")
    assert [r.id for r in controller.deps.catalog.requirements()] == ["RQ-001"] and len(controller.deps.memory.current_decisions()) == 1


def test_empezar_proyecto_nuevo_vacia_la_memoria_pero_conserva_fuentes_y_linea_base(project):
    controller, data = project
    approve_and_apply(controller.deps.catalog, controller.deps.catalog.propose(proposal()))
    controller.deps.memory.register_decision("d1", "Se valida el CUIT", decided_on=date(2026, 1, 25), speaker="Ana", authority="PO", source="r", quote="q", approved_by="PO")
    (data / "linea_base").mkdir()
    (data / "linea_base" / "propuesta.json").write_text("{}", encoding="utf-8")
    controller.new_project()
    assert controller.deps.catalog.requirements() == [] and controller.deps.memory.current_decisions() == []
    assert (data / "linea_base" / "propuesta.json").exists() and controller.using_own_sources  # las fuentes y la línea base siguen


def test_reiniciar_la_demo_no_vacia_el_catalogo_de_un_proyecto_con_fuentes_propias(project):
    controller, _ = project
    approve_and_apply(controller.deps.catalog, controller.deps.catalog.propose(proposal()))
    controller.reset_demo(seed=False)
    assert [r.id for r in controller.deps.catalog.requirements()] == ["RQ-001"]


def test_la_pantalla_ofrece_empezar_proyecto_nuevo_solo_con_confirmacion(project, monkeypatch):
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from backlogguard.ui import runtime

    controller, data = project
    approve_and_apply(controller.deps.catalog, controller.deps.catalog.propose(proposal()))
    monkeypatch.setenv("LIVE_MODE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("BACKLOGGUARD_DATA", str(data))
    at = streamlit_testing.AppTest.from_file(str(runtime.ROOT / "src" / "backlogguard" / "ui" / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception and not [b for b in at.sidebar.button if b.key == "reiniciar"]
    button = at.sidebar.button(key="proyecto-nuevo")
    assert button.disabled  # sin confirmar no se puede
    at.sidebar.checkbox(key="confirmar-proyecto-nuevo").check().run()
    at.sidebar.button(key="proyecto-nuevo").click().run()
    assert not at.exception and Catalog(data / "catalogo.sqlite").requirements() == []
