"""La corrida parte del catálogo: redacta lo aprobado, publica «crear o actualizar» por requisito y no repite lo ya publicado."""
import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest
from test_catalogo import approve_and_apply, draft
from test_graph import EMAIL, GHERKIN, NO_FINDINGS, PDF, PLAN, STORY, World, final, tool

from backlogguard.board import BacklogItem, Board, ItemKind, SourceType
from backlogguard.catalog import Catalog, Draft, Evidence, Proposal, ProposalKind, RequirementStatus
from backlogguard.graph import build_graph, pending_request, resume_pipeline, sqlite_checkpointer
from backlogguard.graph.drafting import MAX_REQUIREMENTS_PER_RUN, goal_for, pick
from backlogguard.hitl import load_people
from backlogguard.integrations.plan import idempotency_key
from backlogguard.tools.requerimientos import DraftArgs, RequirementsToolkit

PEOPLE = load_people(Path(__file__).resolve().parent.parent / "config" / "people.yaml")
TITLE = "Notificación por email del nuevo estado"
RID = "RQ-001"
ITEM = "HU-RQ-001"


def evidence_of(world, source, fingerprint="fp"):
    document_id, fragment = source
    chunk = world.chunk(document_id, fragment)
    meta = chunk.metadata
    return Evidence(
        fragment_id=chunk.chunk_id, quote=fragment, source_name=meta["source_name"], source_type=SourceType(meta["source_type"]),
        source_date=date.fromisoformat(str(meta["source_date"])), speaker=meta.get("speaker"), source_id=document_id, source_fingerprint=fingerprint,
    )


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path, supervisor=list(PLAN), producer=[], critic=[], auditor=NO_FINDINGS)
    catalog = Catalog(tmp_path / "catalogo.sqlite")
    w.deps = dataclasses.replace(w.deps, catalog=catalog)
    w.graph = build_graph(w.deps, sqlite_checkpointer(tmp_path / "ck2.sqlite"))
    w.catalog = catalog
    return w


def approve_requirement(world, title=TITLE, source=EMAIL, key="c1"):
    proposal = Proposal(
        source_id=source[0], fingerprint="fp", candidate_key=key, kind=ProposalKind.NUEVO, drafts=[Draft(title=title, description="d", commitment_ids=["C-001"])],
        evidence=[evidence_of(world, source)],
    )
    return approve_and_apply(world.catalog, world.catalog.propose(proposal)).affected[0]


def write(requirement_id=RID, title=TITLE):
    return tool("redactar_historia", kind="historia", title=title, description=STORY, acceptance_criteria=[GHERKIN], requirement_id=requirement_id)


def verdict_of(item_id, kind="sustentado", *objections):
    return final(json.dumps({"item_id": item_id, "verdict": kind, "objections": list(objections), "reasoning": "x"}))


def approve_plan(world, thread="t1"):
    request = pending_request(world.graph, thread)["request"]
    person = PEOPLE.with_role(request["decides"])[0]
    decision = {
        "decision": "approve", "actor": person.name, "actor_role": person.role, "request_id": request["request_id"],
        "request_version": request["version"], "args_hash": request["args_hash"], "edited": None, "comment": "",
    }
    return resume_pipeline(world.graph, thread, decision)


def run_once(world, thread, *, producer, critic):
    world.providers.supervisor.responses[:] = list(PLAN)
    world.providers.requerimientos.responses[:] = producer
    world.providers.critico.responses[:] = critic
    world.providers.auditor.responses[:] = list(NO_FINDINGS)
    return world.run(thread)


def test_la_historia_nace_del_requisito_aprobado_con_su_identidad_y_sus_citas(world):
    approve_requirement(world)
    state = run_once(world, "t1", producer=[write(), final("Listo.")], critic=[verdict_of(ITEM)])
    item = Board.model_validate(state["board"]).items[ITEM]
    assert (item.requirement_id, item.requirement_version) == (RID, 1)
    assert [c.quote for c in item.citations] == [EMAIL[1]]  # la cita verificada del catálogo, sin que el modelo la repita
    prompt = world.providers.requerimientos.prompts[0]
    assert RID in prompt and TITLE in prompt and "C-001" in prompt
    assert any("Requisitos aprobados por redactar: 1" in t["detail"] for t in state["tasks"])


def test_el_modelo_no_puede_atribuir_una_historia_a_un_requisito_que_no_existe_o_no_esta_activo(world):
    toolkit = RequirementsToolkit(world.deps.library, world.retriever, Board(), world.catalog)
    args = {"kind": "historia", "title": TITLE, "description": STORY, "acceptance_criteria": [GHERKIN], "citations": []}
    assert toolkit.redactar_historia({**args, "requirement_id": "RQ-009"}).metadata["error_type"] == "unknown_requirement"
    rid = approve_requirement(world)
    ok = toolkit.redactar_historia({**args, "requirement_id": rid})
    assert ok.ok and ok.metadata["item_id"] == ITEM
    assert toolkit.redactar_historia({**args, "requirement_id": rid}).metadata["error_type"] == "duplicate_item"
    world.catalog.propose(Proposal(
        source_id="reunion_02_seguimiento", fingerprint="fp", candidate_key="x", kind=ProposalKind.CONTRADICE, targets=[rid], drafts=[draft("Otra cosa distinta")],
        evidence=[evidence_of(world, EXCEL_SOURCE)],
    ))
    approve = world.catalog.decide("P-002", approve=True, by="service_manager")
    world.catalog.apply(approve.id)
    assert world.catalog.requirement(rid).status is RequirementStatus.ACTIVO  # reemplaza el contenido: sigue activo
    without_catalog = RequirementsToolkit(world.deps.library, world.retriever, Board())
    assert without_catalog.redactar_historia({**args, "requirement_id": rid}).metadata["error_type"] == "sin_catalogo"


EXCEL_SOURCE = ("reunion_02_seguimiento", "lo queremos en Excel")


def test_sin_requisito_ni_cita_la_tool_sigue_exigiendo_una_cita():
    with pytest.raises(ValueError, match="al menos una cita"):
        DraftArgs(kind="historia", title=TITLE, description=STORY, acceptance_criteria=[GHERKIN])
    assert DraftArgs(kind="historia", title=TITLE, requirement_id=RID, acceptance_criteria=[GHERKIN]).citations == []


def test_aprobar_el_plan_publica_y_anota_en_el_catalogo_que_version_quedo_publicada(world):
    approve_requirement(world)
    run_once(world, "t1", producer=[write(), final("Listo.")], critic=[verdict_of(ITEM)])
    assert world.catalog.publication(RID) is None and world.backlog.writes == 0
    state = approve_plan(world)
    assert state["status"] == "publicada"
    remote = world.backlog.search(tag=f"bg-item:{ITEM}")[0]
    published = world.catalog.publication(RID)
    assert (published["version"], published["remote_id"], published["needs_update"]) == (1, remote.id, False)
    assert published["key"] == world.catalog.publication_key(RID)


def test_una_segunda_corrida_no_redacta_ni_gasta_ni_publica_lo_que_ya_esta_publicado(world):
    approve_requirement(world)
    run_once(world, "t1", producer=[write(), final("Listo.")], critic=[verdict_of(ITEM)])
    approve_plan(world)
    writes, producer_calls, critic_calls = world.backlog.writes, len(world.providers.requerimientos.prompts), len(world.providers.critico.prompts)
    state = run_once(world, "t2", producer=[], critic=[])
    assert len(world.providers.requerimientos.prompts) == producer_calls and len(world.providers.critico.prompts) == critic_calls
    assert [e["node"] for e in state["trace"]] == ["plan", "produce", "escalate", "integrate", "summarize"]
    assert state["status"] == "completada" and world.backlog.writes == writes and state["board"]["items"] == {}
    assert any("por redactar: 0" in t["detail"] for t in state["tasks"])


def test_una_version_nueva_del_requisito_actualiza_el_mismo_work_item_y_no_crea_otro(world):
    rid = approve_requirement(world)
    run_once(world, "t1", producer=[write(), final("Listo.")], critic=[verdict_of(ITEM)])
    approve_plan(world)
    first_remote = world.catalog.publication(rid)["remote_id"]
    refine = Proposal(
        source_id="reunion_01_kickoff", fingerprint="fp2", candidate_key="r1", kind=ProposalKind.REFINA, targets=[rid],
        drafts=[Draft(title=TITLE, description="Ahora también por SMS", commitment_ids=["C-001"])], evidence=[evidence_of(world, PDF, "fp2")],
    )
    approve_and_apply(world.catalog, world.catalog.propose(refine))
    assert world.catalog.publication(rid)["needs_update"] is True
    state = run_once(world, "t2", producer=[write(), final("Listo.")], critic=[verdict_of(ITEM)])
    assert state["publish_plan"]["counts"] == {"crear": 0, "actualizar": 1, "vincular": 0, "omitir": 0}
    assert Board.model_validate(state["board"]).items[ITEM].requirement_version == 2
    approve_plan(world, "t2")
    assert [w.id for w in world.backlog.search(tag=f"bg-item:{ITEM}")] == [first_remote]  # el mismo work item, no un duplicado
    published = world.catalog.publication(rid)
    assert (published["version"], published["remote_id"], published["needs_update"]) == (2, first_remote, False)


PREVENTA = ("preventa_acme", "Se entrega un reporte mensual de pedidos exportable en PDF.")


def test_la_evidencia_de_la_preventa_guardada_con_el_id_del_compromiso_se_resuelve_a_un_fragmento_real_al_redactar(world):
    """Antes se heredaba «C-067» como fragmento: el Crítico no podía verificarla y objetaba la historia."""
    legacy = evidence_of(world, PREVENTA).model_copy(update={"fragment_id": "C-067", "page": None})
    unresolvable = legacy.model_copy(update={"fragment_id": "C-068", "quote": "Una frase que no figura en la preventa."})
    meeting = evidence_of(world, EMAIL)
    proposal = Proposal(source_id="reunion_01_kickoff", fingerprint="fp", candidate_key="k", kind=ProposalKind.NUEVO, drafts=[Draft(title=TITLE)], evidence=[meeting, legacy, unresolvable])
    rid = approve_and_apply(world.catalog, world.catalog.propose(proposal)).affected[0]
    board = Board()
    toolkit = RequirementsToolkit(world.deps.library, world.retriever, board, world.catalog)
    args = {"kind": "historia", "title": TITLE, "description": STORY, "acceptance_criteria": [GHERKIN], "citations": [], "requirement_id": rid}
    assert toolkit.redactar_historia(args).ok
    citations = board.items[ITEM].citations
    assert sorted(c.quote for c in citations) == sorted([EMAIL[1], PREVENTA[1]])  # la que no se puede ubicar no se hereda
    assert all(world.retriever.get(c.fragment_id) is not None for c in citations) and "C-067" not in {c.fragment_id for c in citations}


def test_la_clave_de_publicacion_es_del_requisito_y_su_version_no_de_como_quedo_redactada():
    def item(title, version):
        return BacklogItem(id=ITEM, kind=ItemKind.HISTORIA, title=title, description=title, requirement_id=RID, requirement_version=version)

    assert idempotency_key("P", item("Un título", 1)) == idempotency_key("P", item("Otro título reescrito", 1))
    assert idempotency_key("P", item("Un título", 1)) != idempotency_key("P", item("Un título", 2))


def test_cada_corrida_toma_un_tope_de_requisitos_y_el_resto_queda_para_la_siguiente(world):
    approve_requirement(world)
    pending = world.catalog.to_publish() * (MAX_REQUIREMENTS_PER_RUN + 3)
    picked, later = pick(pending)
    assert len(picked) == MAX_REQUIREMENTS_PER_RUN and later == 3
    assert "RQ-001 (versión 1)" in goal_for(picked[:1]) and "Se dijo" in goal_for(picked[:1])


def test_solo_se_listan_para_publicar_los_requisitos_activos_sin_publicar_o_con_version_nueva(world):
    first = approve_requirement(world)
    second = approve_requirement(world, "Reporte mensual en PDF", PDF, key="c2")
    assert [r.id for r in world.catalog.to_publish()] == [first, second]
    world.catalog.mark_published(first, 101)
    assert [r.id for r in world.catalog.to_publish()] == [second]
    approve_and_apply(world.catalog, world.catalog.propose(Proposal(
        source_id="reunion_01_kickoff", fingerprint="fp3", candidate_key="r", kind=ProposalKind.REFINA, targets=[first], drafts=[draft("Versión dos del requisito")],
        evidence=[evidence_of(world, EMAIL, "fp3")],
    )))
    assert [r.id for r in world.catalog.to_publish()] == [first, second]
