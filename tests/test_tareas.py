"""Tareas entre agentes: el tope de una corrección por ítem y el registro que alimenta la solapa."""
from test_graph import EMAIL, PLAN, NO_FINDINGS, World, final, item_id, verdict
from test_requerimientos import call, draft_args, email_chunk, make_registry, make_toolkit, objected_item

from backlogguard.board import ItemState, Objection, AgentRole
from backlogguard.graph.tasks import TaskLog, describe_outcome, summarize_tasks
from backlogguard.llm.metering import Meter, MeteredProvider, Usage, estimate_cost
from backlogguard.llm import FakeProvider


def test_un_item_se_corrige_con_exito_una_sola_vez_por_tarea():
    toolkit, retriever, board = make_toolkit()
    registry, policy, item = objected_item(toolkit, retriever, board)
    item.transition_to(ItemState.OBJETADO)
    item.add_objection(Objection(id="O1", raised_by=AgentRole.CRITICO, text="Falta el plazo.", round=1))
    args = draft_args(email_chunk(retriever), title="Email de cambio de estado en menos de un minuto", revises=item.id)
    assert call(registry, policy, "redactar_historia", **args).ok
    second = call(registry, policy, "redactar_historia", **{**args, "title": "Email de cambio de estado, otra versión"})
    assert not second.ok and second.metadata["error_type"] == "ya_corregido" and "terminá" in second.content
    assert board.items[item.id].title == "Email de cambio de estado en menos de un minuto"


def test_un_intento_fallido_no_gasta_la_correccion():
    toolkit, retriever, board = make_toolkit()
    registry, policy, item = objected_item(toolkit, retriever, board)
    item.transition_to(ItemState.OBJETADO)
    item.add_objection(Objection(id="O1", raised_by=AgentRole.CRITICO, text="Falta el plazo.", round=1))
    broken = draft_args(email_chunk(retriever), revises=item.id, acceptance_criteria=["sin forma de Gherkin"])
    assert not call(registry, policy, "redactar_historia", **broken).ok
    assert item.id not in toolkit.corrected
    good = draft_args(email_chunk(retriever), title="Email en menos de un minuto", revises=item.id)
    assert call(registry, policy, "redactar_historia", **good).ok and item.id in toolkit.corrected


def test_el_registro_numera_las_tareas_a_continuacion_de_las_existentes():
    log = TaskLog(existing=3)
    first = log.add("critico", "requerimientos", "corregir", ref="HU-1", usage=Usage(60, 40, 1), corrections=1)
    second = log.add("requerimientos", "critico", "revisar", ref="HU-1", round=2, usage=Usage(250, 50, 2))
    assert (first["id"], second["id"]) == ("T-004", "T-005")
    assert log.tasks[0]["detail"] == "" and second["round"] == 2
    assert (first["input_tokens"], first["output_tokens"], first["tokens"], second["llm_calls"]) == (60, 40, 100, 2)


def test_describe_outcome_cuenta_pasos_correcciones_y_rechazos():
    def observation(ok, revises=None, error=None):
        return {
            "event": "observation", "tool": "redactar_historia", "arguments": {"revises": revises} if revises else {},
            "observation": {"ok": ok, "metadata": {"error_type": error} if error else {}},
        }

    trace = [
        {"event": "decision"}, observation(True, "HU-1"),
        {"event": "decision"}, observation(False, "HU-1", "ya_corregido"),
        {"event": "decision"},
    ]
    assert describe_outcome({"trace": trace}) == {"steps": 3, "corrections": 1, "rejected": 1}


def test_los_totales_se_reparten_por_agente_y_por_par():
    def task(origin, target, kind, model, tin, tout, **extra):
        return {"origin": origin, "target": target, "kind": kind, "status": "hecha", "model": model, "input_tokens": tin,
                "output_tokens": tout, "tokens": tin + tout, "llm_calls": 1, "corrections": 0, "rejected": 0, **extra}

    tasks = [
        task("supervisor", "requerimientos", "redactar", "claude-sonnet-5-5", 500_000, 100_000),
        task("requerimientos", "critico", "revisar", "claude-opus-5-5", 200_000, 100_000),
        task("critico", "requerimientos", "corregir", "claude-sonnet-5-5", 80_000, 20_000, corrections=1, rejected=2),
        task("critico", "persona", "decidir", "", 0, 0, status="escalada"),
    ]
    totals = summarize_tasks(tasks)
    assert (totals["tasks"], totals["tokens"], totals["corrections"], totals["corrections_ok"], totals["rejected"]) == (4, 1_000_000, 1, 1, 2)
    assert (totals["input_tokens"], totals["output_tokens"]) == (780_000, 220_000)
    first = totals["by_agent"][0]
    assert (first["agente"], first["tareas"], first["tokens"], first["parte"]) == ("Requerimientos", 2, 700_000, 0.7)
    assert first["costo"] == 2.36  # 2,00 de redactar + 0,36 de corregir, a precios de Sonnet
    assert abs(totals["cost"] - 5.16) < 1e-9  # + 2,80 del Crítico a precios de Opus
    assert totals["unpriced_models"] == []


def test_un_modelo_sin_precio_se_avisa_y_no_se_inventa_su_costo():
    tasks = [{"origin": "a", "target": "b", "kind": "revisar", "status": "hecha", "model": "modelo-nuevo", "input_tokens": 10,
              "output_tokens": 5, "tokens": 15, "corrections": 0, "rejected": 0}]
    totals = summarize_tasks(tasks, pricing={"claude-opus-5-5": (4.0, 20.0)})
    assert totals["unpriced_models"] == ["modelo-nuevo"] and totals["cost"] == 0.0
    assert estimate_cost("replay:claude-opus-5-5", 1_000_000, 0, {"claude-opus-5-5": (4.0, 20.0)}) == 4.0


def test_el_medidor_reparte_lo_gastado_entre_dos_marcas():
    meter = Meter()
    provider = MeteredProvider(FakeProvider(delay_seconds=0, responses=["a", "b", "c"]), meter)
    provider.generate("hola")
    mark = meter.mark()
    provider.generate("otra llamada")
    provider.generate("y otra")
    used = meter.since(mark)
    assert used.calls == 2 and used.input_tokens > 0 and used.output_tokens > 0 and meter.calls == 3


def test_la_corrida_registra_quien_le_paso_que_a_quien(tmp_path):
    title = "Notificación por email"
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=NO_FINDINGS)
    world.providers.requerimientos.responses[:] = [
        world.draft(title, EMAIL), final("ok"),
        world.draft(title, EMAIL, revises=item_id(title)), final("corregido"),
    ]
    world.providers.critico.responses[:] = [verdict(title, "objetado", "Falta el plazo de envío."), verdict(title, "sustentado")]
    tasks = world.run()["tasks"]
    flow = [(t["origin"], t["target"], t["kind"]) for t in tasks]
    assert flow[:6] == [
        ("persona", "supervisor", "planificar"),
        ("supervisor", "requerimientos", "redactar"),
        ("requerimientos", "critico", "revisar"),
        ("critico", "requerimientos", "corregir"),
        ("requerimientos", "critico", "revisar"),
        ("supervisor", "auditor", "auditar"),
    ]
    assert [t["id"] for t in tasks] == [f"T-{n:03d}" for n in range(1, len(tasks) + 1)]
    fix = tasks[3]
    assert fix["ref"] == item_id(title) and fix["round"] == 1 and fix["corrections"] == 1 and "plazo" in fix["detail"]
    assert tasks[2]["detail"].startswith("objetado") and tasks[4]["detail"] == "sustentado"
    assert all(t["tokens"] >= 0 for t in tasks)
