"""Human-in-the-Loop: contratos, validación, efectos y recorrido del grafo con pausas reales."""
import json
from pathlib import Path

import pytest
from test_graph import EMAIL, EXCEL, MOBILE, NO_FINDINGS, PDF, PLAN, World, final, item_id, nodes, verdict

from backlogguard.board import Board, ItemState
from backlogguard.graph import build_graph, load_state, pending_request, resume_pipeline, sqlite_checkpointer
from backlogguard.hitl import (
    DecisionRequest,
    HumanDecision,
    apply_scope_decision,
    canonical_hash,
    group_findings,
    load_people,
    request_for_group,
    validate_decision,
)
from backlogguard.memory import ProjectMemory

ROOT = Path(__file__).resolve().parent.parent
PEOPLE = load_people(ROOT / "config" / "people.yaml")
ROLE = {"service_manager": "service_manager", "product_owner": "product_owner", "full_stack_ia_engineer": "full_stack_ia_engineer"}
OWNER = {role: name for name, role in ROLE.items()}
TITLE = "Notificación por email"


# ---- ayudas ----


def decision_for(request: dict, decision="approve", *, actor=None, edited=None, comment="", **tamper) -> dict:
    actor = actor or OWNER[request["decides"]]
    data = {
        "decision": decision, "actor": actor, "actor_role": ROLE[actor], "request_id": request["request_id"],
        "request_version": request["version"], "args_hash": request["args_hash"], "edited": edited, "comment": comment,
    }
    return {**data, **tamper}


def answer(world, decision="approve", *, thread="t1", **kwargs):
    request = pending_request(world.graph, thread)["request"]
    return resume_pipeline(world.graph, thread, decision_for(request, decision, **kwargs))


def finish(world, decision="approve", thread="t1"):
    """Responde todos los pedidos pendientes con la persona que corresponde."""
    for _ in range(20):
        if pending_request(world.graph, thread) is None:
            return load_state(world.graph, thread)
        answer(world, decision, thread=thread)
    raise AssertionError("la corrida no terminó")


def disputed(tmp_path, *, report=None):
    """Un ítem que el Crítico y el productor no logran acordar en 2 rondas."""
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=[])
    world.providers.requerimientos.responses[:] = [
        world.draft(TITLE, EMAIL), final("ok"), world.draft(TITLE, EMAIL, revises=item_id(TITLE)), final("intento"),
    ]
    world.providers.critico.responses[:] = [verdict(TITLE, "objetado", "Falta evidencia."), verdict(TITLE, "objetado", "Sigue sin evidencia.")]
    world.providers.auditor.responses[:] = [final(json.dumps(report or {"findings": [], "summary": ""}))]
    return world


def clean(tmp_path, *titles_sources, report=None, db="ck.sqlite"):
    """Ítems sustentados a la primera, sin desacuerdos."""
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=[], db=db)
    drafts = [world.draft(title, source) for title, source in titles_sources]
    world.providers.requerimientos.responses[:] = [*drafts, final("ok")]
    world.providers.critico.responses[:] = [verdict(title, "sustentado") for title, _ in titles_sources]
    world.providers.auditor.responses[:] = [final(json.dumps(report or {"findings": [], "summary": ""}))]
    return world


def board_of(state):
    return Board.model_validate(state["board"])


# ---- contratos puros ----


def a_request():
    return DecisionRequest(
        request_id="R-1", kind="alcance", reason="cambio_de_alcance", decides="service_manager", ref="G-1",
        title="Cambio", summary="resumen", editable=["decision_text"], payload={"decision_text": "Incluir la app móvil", "topic_key": "alcance-x"},
    ).sealed()


def a_decision(request, **overrides):
    base = {"decision": "approve", "actor": "service_manager", "actor_role": "service_manager", "request_id": request.request_id,
            "request_version": request.version, "args_hash": request.args_hash}
    return HumanDecision(**{**base, **overrides})


def test_el_hash_del_pedido_cubre_su_contenido():
    request = a_request()
    assert request.args_hash == canonical_hash(request.content())
    changed = request.model_copy(update={"summary": "otro"}).sealed()
    assert changed.args_hash != request.args_hash


def test_una_decision_vieja_o_adulterada_se_rechaza():
    request = a_request()
    assert validate_decision(request, a_decision(request), PEOPLE) is None
    assert "versión" in validate_decision(request, a_decision(request, request_version=2), PEOPLE)
    assert "cambió" in validate_decision(request, a_decision(request, args_hash="0" * 24), PEOPLE)
    assert "otro pedido" in validate_decision(request, a_decision(request, request_id="R-2"), PEOPLE)


def test_solo_decide_el_rol_que_corresponde():
    request = a_request()
    assert "service_manager" in validate_decision(request, a_decision(request, actor="product_owner", actor_role="product_owner"), PEOPLE)
    assert "tiene el rol" in validate_decision(request, a_decision(request, actor="product_owner", actor_role="service_manager"), PEOPLE)
    assert "No conozco" in validate_decision(request, a_decision(request, actor="intruso"), PEOPLE)


def test_solo_se_edita_lo_editable_y_con_datos_validos():
    request = a_request()
    assert "Una edición necesita" in validate_decision(request, a_decision(request, decision="edit"), PEOPLE)
    assert "No se pueden editar" in validate_decision(request, a_decision(request, decision="edit", edited={"ref": "x"}), PEOPLE)
    assert "entre 3" in validate_decision(request, a_decision(request, decision="edit", edited={"decision_text": "x"}), PEOPLE)
    assert validate_decision(request, a_decision(request, decision="edit", edited={"decision_text": "Incluir la app, en una fase 2"}), PEOPLE) is None
    assert "Solo la edición" in validate_decision(request, a_decision(request, edited={"decision_text": "algo"}), PEOPLE)


def test_editar_crea_una_version_nueva_que_hay_que_aprobar():
    v1 = a_request()
    v2 = v1.next_version({"decision_text": "Incluir la app móvil en la fase 2"})
    assert v2.version == 2 and v2.args_hash != v1.args_hash and v2.payload["decision_text"].endswith("fase 2")
    assert "versión" in validate_decision(v2, a_decision(v1), PEOPLE)  # la aprobación de v1 no sirve para v2


def test_el_archivo_de_personas_cubre_a_quienes_deciden_segun_la_politica():
    from backlogguard.tools import load_policy_config

    deciders = {rule.decides for rule in load_policy_config(ROOT / "config" / "policy.yaml").pauses}
    assert deciders <= {person.role for person in PEOPLE.people}


# ---- agrupación (HI-01) ----


def test_los_hallazgos_del_mismo_asunto_se_agrupan(tmp_path):
    world = clean(tmp_path)
    from backlogguard.agents.auditor import AuditReport, apply_report
    from backlogguard.agents.auditor.informe import FindingDraft

    board = Board()
    report = AuditReport(findings=[
        FindingDraft(**world.finding("tratado_no_vendido", "La app móvil no estaba en la propuesta.", MOBILE)),
        FindingDraft(**world.finding("cambio_de_alcance", "La app móvil agranda el alcance vendido.", MOBILE)),
        FindingDraft(**world.finding("vendido_no_tratado", "El ERP se vendió y no se trató.", ("preventa_acme", "ERP de ACME"))),
        FindingDraft(**world.finding("decision_evolucionada", "El filtro por fecha se pospuso.", ("reunion_03_refinamiento", "el filtro por fecha puede esperar"))),
    ])
    apply_report(report, board, world.retriever)
    groups = group_findings(board.findings)
    assert sorted(len(g.findings) for g in groups) == [1, 2]  # la evolución informativa no pide decisión
    mobile = next(g for g in groups if len(g.findings) == 2)
    assert mobile.reason == "cambio_de_alcance" and len(mobile.evidence()) == 1


def test_la_razon_del_service_manager_prima_en_un_grupo(tmp_path):
    world = clean(tmp_path)
    from backlogguard.agents.auditor import AuditReport, apply_report
    from backlogguard.agents.auditor.informe import FindingDraft

    board = Board()
    shared = ("reunion_03_refinamiento", "menos de un minuto")
    apply_report(AuditReport(findings=[
        FindingDraft(**world.finding("contradiccion", "Dos posturas sobre el email.", shared, ("reunion_03_refinamiento", "único resumen diario"))),
        FindingDraft(**world.finding("cambio_de_alcance", "El envío diario cambia lo vendido.", shared)),
    ]), board, world.retriever)
    (group,) = group_findings(board.findings)
    assert group.reason == "cambio_de_alcance"
    request = request_for_group(group, world.deps.policy)
    assert request.decides == "service_manager" and request.version == 1 and request.args_hash


# ---- pausas del grafo ----


def test_la_corrida_se_pausa_y_se_retoma_desde_otra_instancia(tmp_path):
    world = disputed(tmp_path)
    paused = world.run()
    assert "__interrupt__" in paused and nodes(paused)[-1] == "escalate"
    payload = pending_request(world.graph, "t1")
    assert payload["request"]["decides"] == "product_owner" and payload["last_error"] is None
    other = build_graph(world.deps, sqlite_checkpointer(world.db))  # otra instancia, mismo SQLite
    assert pending_request(other, "t1") == payload
    resume_pipeline(other, "t1", decision_for(payload["request"], "approve"))
    assert board_of(load_state(other, "t1")).items[item_id(TITLE)].state is ItemState.SUSTENTADO


def test_el_po_resuelve_un_desacuerdo_aprobando_editando_o_rechazando(tmp_path):
    approved = disputed(tmp_path / "a")
    approved.run()
    answer(approved, "approve")
    assert board_of(load_state(approved.graph, "t1")).items[item_id(TITLE)].state is ItemState.SUSTENTADO

    rejected = disputed(tmp_path / "r")
    rejected.run()
    state = answer(rejected, "reject")
    assert board_of(state).items[item_id(TITLE)].state is ItemState.EXCLUIDO and state["status"] == "completada"

    edited = disputed(tmp_path / "e")
    edited.run()
    new_title = "Notificación por email en menos de un minuto"
    answer(edited, "edit", edited={"title": new_title})
    request = pending_request(edited.graph, "t1")["request"]
    assert request["version"] == 2 and request["payload"]["title"] == new_title
    answer(edited, "approve")
    item = board_of(load_state(edited.graph, "t1")).items[item_id(TITLE)]
    assert item.title == new_title and item.state is ItemState.SUSTENTADO


def test_una_decision_invalida_no_cambia_el_estado(tmp_path):
    world = disputed(tmp_path)
    world.run()
    request = pending_request(world.graph, "t1")["request"]
    before = board_of(load_state(world.graph, "t1")).model_dump()
    for tamper in ({"args_hash": "0" * 24}, {"request_version": 9}, {"actor": "service_manager", "actor_role": "service_manager"}):
        resume_pipeline(world.graph, "t1", decision_for(request, **tamper))
        again = pending_request(world.graph, "t1")
        assert again["request"] == request and again["last_error"]  # se vuelve a ofrecer, con el motivo
        assert board_of(load_state(world.graph, "t1")).model_dump() == before
    resume_pipeline(world.graph, "t1", {"decision": "approve"})  # ni siquiera tiene el formato
    assert "formato" in pending_request(world.graph, "t1")["last_error"]


def test_cada_decision_queda_auditada(tmp_path):
    world = disputed(tmp_path)
    world.run()
    request = pending_request(world.graph, "t1")["request"]
    resume_pipeline(world.graph, "t1", decision_for(request, args_hash="0" * 24))
    answer(world, "approve", comment="De acuerdo con la evidencia.")
    log = load_state(world.graph, "t1")["decisions"]
    assert [d["accepted"] for d in log[:2]] == [False, True]
    accepted = log[1]
    assert accepted["actor"] == "product_owner" and accepted["actor_role"] == "product_owner" and accepted["decision"] == "approve"
    assert accepted["version"] == 1 and accepted["args_hash"] == request["args_hash"] and accepted["at"] and accepted["comment"]
    assert log[0]["error"]


def test_un_item_aprobado_por_el_po_entra_al_plan(tmp_path):
    world = disputed(tmp_path)
    world.run()
    state = answer(world, "approve")
    plan = state["publish_plan"]
    assert plan["counts"]["crear"] == 1 and plan["items"][0]["item_id"] == item_id(TITLE)
    assert pending_request(world.graph, "t1")["request"]["kind"] == "plan"


# ---- alcance, contradicción y memoria (HI-07) ----


def scope_report(world):
    return {"findings": [
        world.finding("tratado_no_vendido", "La app móvil no estaba en la propuesta.", MOBILE),
        world.finding("cambio_de_alcance", "La app móvil agranda el alcance vendido.", MOBILE),
        world.finding("contradiccion", "Dos posturas incompatibles sobre el email.", ("reunion_03_refinamiento", "único resumen diario"), ("reunion_03_refinamiento", "menos de un minuto")),
        world.finding("vendido_no_tratado", "El ERP se vendió y no se trató.", ("preventa_acme", "ERP de ACME")),
    ], "summary": ""}


def scope_world(tmp_path, **kwargs):
    world = World(tmp_path, supervisor=PLAN, producer=[final("Sin ítems.")], critic=[], auditor=[], **kwargs)
    world.providers.auditor.responses[:] = [final(json.dumps(scope_report(world)))]
    return world


def test_cada_asunto_pide_una_sola_decision_a_quien_corresponde(tmp_path):
    world = scope_world(tmp_path)
    state = world.run()
    assert [(r["reason"], r["decides"]) for r in state["requests"]] == [
        ("cambio_de_alcance", "service_manager"), ("contradiccion", "product_owner"), ("vendido_no_tratado", "service_manager"),
    ]
    assert state["status"] == "esperando_decision" and len(state["escalations"]) == 3


def test_la_decision_queda_en_la_memoria_con_su_aprobador(tmp_path):
    world = scope_world(tmp_path)
    world.run()
    answer(world, "approve", comment="Se evalúa aparte.")
    answer(world, "reject")
    final_state = answer(world, "approve")
    decisions = {d["key"]: d for d in world.deps.memory.current_decisions()}
    assert len(decisions) == 3
    texts = sorted(d["value"]["decision"] for d in decisions.values())
    assert sum(t.startswith("Se aprueba") for t in texts) == 2 and sum(t.startswith("Se rechaza") for t in texts) == 1
    assert {d["value"]["approved_by"] for d in decisions.values()} == {"service_manager", "product_owner"}
    assert final_state["status"] == "completada" and final_state["summary"] and pending_request(world.graph, "t1") is None


def test_una_decision_vigente_no_se_vuelve_a_escalar(tmp_path):
    first = scope_world(tmp_path)
    first.run()
    finish(first)
    second = scope_world(tmp_path, db="otra.sqlite")  # misma memoria del proyecto, otra corrida
    state = second.run("t2")
    assert state["requests"] == [] and state["escalations"] == [] and "__interrupt__" not in state
    assert any("ya_decididos" in event and event["ya_decididos"] for event in state["trace"])


def test_reanudar_dos_veces_no_duplica_efectos(tmp_path):
    world = scope_world(tmp_path)
    state = world.run()
    request = DecisionRequest.model_validate(state["requests"][0])
    decision = a_decision(request)
    memory = ProjectMemory(tmp_path / "otra_memoria.sqlite", "acme")
    assert apply_scope_decision(request, decision, memory).outcome == "registrada"
    assert apply_scope_decision(request, decision, memory).outcome == "ya_registrada"
    assert len(memory.current_decisions()) == 1


def test_editar_el_texto_de_una_decision_exige_aprobar_la_version_nueva(tmp_path):
    world = scope_world(tmp_path)
    world.run()
    answer(world, "edit", edited={"decision_text": "Evaluar la app móvil como proyecto aparte"})
    request = pending_request(world.graph, "t1")["request"]
    assert request["version"] == 2 and world.deps.memory.current_decisions() == []  # nada se registró todavía
    answer(world, "approve")
    (saved,) = world.deps.memory.current_decisions()
    assert "proyecto aparte" in saved["value"]["decision"]


# ---- plan de publicación (HI-10, HI-11) ----


def test_aprobar_el_plan_publica(tmp_path):
    world = clean(tmp_path, (TITLE, EMAIL))
    paused = world.run()
    assert paused["status"] == "plan_pendiente_de_aprobacion" and world.backlog.writes == 0
    request = pending_request(world.graph, "t1")["request"]
    assert request["decides"] == "full_stack_ia_engineer" and request["kind"] == "plan"
    state = answer(world, "approve")
    item = board_of(state).items[item_id(TITLE)]
    assert item.state is ItemState.APROBADO and item.approved_by == "full_stack_ia_engineer"
    assert state["status"] == "publicada" and state["publication"]["ok"] and world.backlog.writes == 1
    assert state["summary"] and nodes(state)[-1] == "summarize"


def test_excluir_items_genera_un_plan_nuevo(tmp_path):
    other = "Reporte mensual en Excel"
    world = clean(tmp_path, (TITLE, EMAIL), (other, EXCEL))
    world.run()
    v1 = pending_request(world.graph, "t1")["request"]
    answer(world, "edit", edited={"exclude": [item_id(other)]})
    v2 = pending_request(world.graph, "t1")["request"]
    assert v2["version"] == 2 and v2["ref"] != v1["ref"] and v2["args_hash"] != v1["args_hash"]
    resume_pipeline(world.graph, "t1", decision_for(v1))  # aprobar la versión vieja no sirve
    assert pending_request(world.graph, "t1")["request"] == v2 and world.backlog.writes == 0
    state = answer(world, "approve")
    board = board_of(state)
    assert [w.title for w in world.backlog.search()] == [TITLE]
    assert board.items[item_id(TITLE)].state is ItemState.APROBADO and board.items[item_id(other)].state is ItemState.SUSTENTADO


def test_no_se_puede_excluir_lo_que_no_esta_en_el_plan(tmp_path):
    world = clean(tmp_path, (TITLE, EMAIL))
    world.run()
    answer(world, "edit", edited={"exclude": ["HU-inexistente"]})
    assert "Solo se pueden excluir" in pending_request(world.graph, "t1")["last_error"]


def test_rechazar_el_plan_no_publica(tmp_path):
    world = clean(tmp_path, (TITLE, EMAIL))
    world.run()
    state = answer(world, "reject")
    assert state["status"] == "plan_rechazado" and world.backlog.writes == 0 and state["summary"]
    assert board_of(state).items[item_id(TITLE)].state is ItemState.SUSTENTADO


def test_un_cambio_del_backlog_tras_aprobar_bloquea_la_publicacion(tmp_path):
    world = clean(tmp_path, (TITLE, EMAIL))
    world.run()
    world.backlog.create(type="User Story", title=TITLE, description="alguien lo cargó a mano", acceptance_criteria=[], tags=[], parent_id=None)
    before = world.backlog.writes
    state = answer(world, "approve")
    assert state["status"] == "publicacion_detenida" and "cambiaron" in state["publication"]["error"]
    assert world.backlog.writes == before


def test_rechazarlo_todo_termina_bien(tmp_path):
    world = disputed(tmp_path, report=None)
    world.providers.auditor.responses[:] = [final(json.dumps(scope_report(world)))]
    world.run()
    state = finish(world, "reject")
    assert state["status"] == "completada" and state["summary"] and "__interrupt__" not in state
    assert board_of(state).items[item_id(TITLE)].state is ItemState.EXCLUIDO and world.backlog.writes == 0
    assert all(d["accepted"] for d in state["decisions"]) and len(state["decisions"]) == 4


def test_el_recorrido_completo_con_todas_las_decisiones(tmp_path):
    world = disputed(tmp_path)
    world.providers.auditor.responses[:] = [final(json.dumps(scope_report(world)))]
    world.run()
    state = finish(world, "approve")
    assert nodes(state) == [
        "plan", "produce", "review", "audit", "escalate", "decide", "decide", "decide", "decide",
        "integrate", "approve_plan", "summarize",
    ]  # una pausa por pedido: el desacuerdo, tres asuntos de alcance y, al final, el plan
    assert state["status"] == "publicada" and world.backlog.writes == 1
    assert [d["actor"] for d in state["decisions"]] == ["product_owner", "service_manager", "product_owner", "service_manager", "full_stack_ia_engineer"]
