"""Matriz de cobertura (Bloque 3): lo vendido cruzado con lo tratado, calculado por código."""
import json
from datetime import date
from pathlib import Path

import pytest

from backlogguard.agents.auditor import apply_report
from backlogguard.agents.auditor.informe import AuditReport, FindingDraft
from backlogguard.board import AgentRole, Board, FindingKind, SourceType
from backlogguard.catalog import Catalog, Draft, Evidence, Proposal, ProposalKind
from backlogguard.catalog.coverage import build_coverage, current_baseline
from backlogguard.graph.deps import index_library
from backlogguard.memory import ProjectMemory
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary
from backlogguard.rag.compromisos import Baseline, BaselineStore, Commitment
from backlogguard.tools import ExecutionContext, ToolCall, ToolPolicy, build_catalog_registry
from backlogguard.tools.auditor import AuditorToolkit

FIXTURES = Path(__file__).resolve().parent.parent / "evals" / "fixtures"
MEETING = "reunion_02_seguimiento"


def commitment(cid, quote, scope="incluido", epic="Portal"):
    return Commitment(id=cid, epic=epic, capability=f"Capacidad {cid}", scope=scope, page=1, quote=quote)


COMMITMENTS = [
    commitment("C-001", "portal de autoservicio"),
    commitment("C-002", "mediante SSO"),
    commitment("C-003", "se integra con el ERP de ACME"),
    commitment("C-004", "notificación por email", scope="excluido"),
    commitment("C-005", "reporte mensual", scope="condicion"),
    commitment("C-006", "exportable en PDF"),
]


def baseline(commitments=COMMITMENTS, fingerprint="fp-preventa"):
    return Baseline(
        document_id="preventa_acme", fingerprint=fingerprint, model="m", extracted_at="2026-11-02", commitments=list(commitments)
    )


@pytest.fixture
def world(tmp_path):
    library = SourceLibrary(FIXTURES)
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    index_library(library, retriever)
    return library, retriever, Catalog(tmp_path / "catalogo.sqlite")


def meeting_evidence(retriever, text="app móvil"):
    found = next(c for c in retriever.all_chunks({"document_id": MEETING}) if text in c.text)
    return Evidence(
        fragment_id=found.chunk_id, quote=text, source_name="Seguimiento", source_type=SourceType.REUNION,
        source_date=date(2026, 3, 20), source_id=MEETING, source_fingerprint="fp-reunion",
    )


def approve(catalog, proposal):
    saved = catalog.propose(proposal)
    catalog.decide(saved.id, approve=True, by="PO")
    catalog.apply(saved.id)
    return saved


def new_requirement(catalog, retriever, title, commitments=()):
    draft = Draft(title=title, description="d", acceptance_criteria=["a"], commitment_ids=list(commitments))
    approve(
        catalog,
        Proposal(
            source_id=MEETING, fingerprint="fp-reunion", candidate_key=title, kind=ProposalKind.NUEVO,
            drafts=[draft], evidence=[meeting_evidence(retriever)],
        ),
    )


def seeded(catalog, retriever):
    """RQ-001 cubre C-001; RQ-002 no tiene compromiso; RQ-003 toca un excluido; RQ-004 perdió C-006 al refinarse."""
    new_requirement(catalog, retriever, "Portal de autoservicio", ["C-001"])
    new_requirement(catalog, retriever, "App móvil para clientes")
    new_requirement(catalog, retriever, "Avisos por email", ["C-004"])
    new_requirement(catalog, retriever, "Reporte en PDF", ["C-006"])
    approve(
        catalog,
        Proposal(
            source_id=MEETING, fingerprint="fp-reunion", candidate_key="reporte-excel", kind=ProposalKind.REFINA,
            targets=["RQ-004"], drafts=[Draft(title="Reporte en Excel", description="d", acceptance_criteria=["a"])],
            evidence=[meeting_evidence(retriever, "Excel")],
        ),
    )
    catalog.mark_source_processed(MEETING, "fp-reunion", date(2026, 3, 20))


def ids(rows):
    return [row["id"] for row in rows]


def test_la_matriz_separa_lo_cubierto_lo_no_tratado_y_lo_que_cambia_el_alcance(world):
    _, retriever, catalog = world
    seeded(catalog, retriever)
    coverage = build_coverage(baseline(), catalog)
    assert ids(coverage.covered) == ["C-001"]
    assert ids(coverage.vendido_sin_requisito) == ["C-002", "C-003"]
    assert ids(coverage.excluidos_con_requisito) == ["C-004"]
    assert [r["id"] for r in coverage.excluidos_con_requisito[0]["requisitos"]] == ["RQ-003"]
    assert ids(coverage.cobertura_perdida) == ["C-006"]
    assert ids(coverage.condiciones) == ["C-005"]  # un supuesto no es «vendido y no tratado»
    assert ids(coverage.requisitos_sin_compromiso) == ["RQ-002", "RQ-004"]


def test_un_requisito_sin_compromiso_llega_con_su_evidencia_de_reunion(world):
    _, retriever, catalog = world
    seeded(catalog, retriever)
    mobile = build_coverage(baseline(), catalog).requisitos_sin_compromiso[0]
    assert mobile["id"] == "RQ-002" and mobile["evidencia"][0]["chunk_id"].startswith(MEETING)


def test_sin_reuniones_leidas_no_se_acusa_de_vendido_no_tratado(world):
    _, retriever, catalog = world
    coverage = build_coverage(baseline(), catalog)
    assert coverage.vendido_sin_requisito == [] and any("Ninguna reunión" in w for w in coverage.warnings)


def test_sin_requisitos_aprobados_tampoco(world):
    _, _, catalog = world
    catalog.mark_source_processed(MEETING, "fp-reunion", date(2026, 3, 20))
    coverage = build_coverage(baseline(), catalog)
    assert coverage.vendido_sin_requisito == [] and any("requisitos aprobados" in w for w in coverage.warnings)


def test_lo_que_no_esta_en_la_preventa_se_informa_aunque_no_se_pueda_comparar_lo_vendido(world):
    """Un cambio de alcance se detecta por lo que la preventa NO tiene: ese camino no lleva ningún filtro."""
    _, retriever, catalog = world
    new_requirement(catalog, retriever, "App móvil para clientes")
    coverage = build_coverage(baseline(), catalog)  # ninguna reunión marcada como leída
    assert ids(coverage.requisitos_sin_compromiso) == ["RQ-001"] and coverage.vendido_sin_requisito == []


def test_las_propuestas_sin_decidir_se_avisan(world):
    _, retriever, catalog = world
    seeded(catalog, retriever)
    catalog.propose(
        Proposal(
            source_id=MEETING, fingerprint="fp-reunion", candidate_key="pendiente", kind=ProposalKind.NUEVO,
            drafts=[Draft(title="Otra cosa", description="d", acceptance_criteria=["a"])], evidence=[meeting_evidence(retriever)],
        )
    )
    assert any("sin decidir" in w for w in build_coverage(baseline(), catalog).warnings)


# ---- tool del Auditor ----


def run_compare(retriever, catalog, base, tmp_path):
    memory = ProjectMemory(tmp_path / "memoria.sqlite", "acme")
    context = ExecutionContext(user_id="u", role=AgentRole.AUDITOR)
    kit = AuditorToolkit(retriever, Board(), memory, context, baseline=base, catalog=catalog)
    registry = build_catalog_registry(kit.implementations())
    return registry.run(ToolCall(tool_name="comparar_con_preventa", arguments={}), context=context, policy=ToolPolicy())


def test_el_auditor_usa_los_compromisos_si_existen(world, tmp_path):
    _, retriever, catalog = world
    seeded(catalog, retriever)
    result = run_compare(retriever, catalog, baseline(), tmp_path)
    report = json.loads(result.content)
    assert report["modo"] == "compromisos" and "preventa" not in report and "reuniones" not in report
    erp = next(r for r in report["vendido_sin_requisito"] if r["id"] == "C-003")
    assert erp["chunk_id"].startswith("preventa_acme") and "ERP" in erp["cita"]  # puede citarlo por chunk_id


def test_sin_compromisos_el_auditor_usa_la_preventa_completa(world, tmp_path):
    _, retriever, catalog = world
    report = json.loads(run_compare(retriever, catalog, None, tmp_path).content)
    assert "preventa" in report and "modo" not in report


# ---- el hallazgo se verifica como siempre ----


def test_un_cambio_de_alcance_se_cita_con_la_reunion_y_con_el_compromiso_y_no_se_pierde(world):
    _, retriever, catalog = world
    mobile = meeting_evidence(retriever)
    only_meeting = FindingDraft(
        kind=FindingKind.TRATADO_NO_VENDIDO,
        description="La app móvil se pide en el seguimiento y la preventa no la incluye.",
        citations=[{"chunk_id": mobile.fragment_id, "quote": "app móvil"}],
    )
    erp = next(c for c in retriever.all_chunks({"document_id": "preventa_acme"}) if "ERP" in c.text)
    both = FindingDraft(
        kind=FindingKind.CAMBIO_DE_ALCANCE,
        description="El ERP figuraba como incluido y la reunión lo da de baja del alcance.",
        citations=[{"chunk_id": erp.chunk_id, "quote": "se integra con el ERP de ACME"}, {"chunk_id": mobile.fragment_id, "quote": "app móvil"}],
    )
    result = apply_report(AuditReport(findings=[only_meeting, both]), Board(), retriever)
    assert len(result.applied) == 2 and not result.discarded


def test_una_cita_inventada_sigue_descartandose(world):
    _, retriever, _ = world
    mobile = meeting_evidence(retriever)
    fake = FindingDraft(
        kind=FindingKind.CAMBIO_DE_ALCANCE, description="Una frase que nadie dijo en la reunión.",
        citations=[{"chunk_id": mobile.fragment_id, "quote": "queremos una app para drones"}],
    )
    result = apply_report(AuditReport(findings=[fake]), Board(), retriever)
    assert not result.applied and "no verificable" in result.discarded[0][1]


# ---- qué línea base se usa ----


def test_solo_vale_la_linea_base_vigente_de_la_unica_preventa(world, tmp_path):
    library, _, _ = world
    store = BaselineStore(tmp_path / "linea_base")
    assert current_baseline(library, store) is None  # no se extrajo
    document = library.load("preventa_acme")
    store.save(baseline(fingerprint=document.fingerprint))
    assert current_baseline(library, store) is not None
    store.save(baseline(fingerprint="otra-huella"))
    assert current_baseline(library, store) is None  # la preventa cambió
