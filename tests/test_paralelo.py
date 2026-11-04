"""Revisión del Crítico en paralelo (clase 12: fan-out con Send, ramas independientes, fan-in en un nodo)."""
import json
import re
import threading
import time
from dataclasses import replace

from test_critico import add_item, citation_for
from test_graph import EMAIL, EXCEL, MOBILE, NO_FINDINGS, PDF, PLAN, World, final, item_id, nodes
from test_hitl import answer

from backlogguard.board import Board, ItemState
from backlogguard.graph import RunBudget, build_graph, sqlite_checkpointer
from backlogguard.graph.nodes import make_nodes
from backlogguard.graph.tasks import renumber
from backlogguard.llm.errors import TransientProviderError
from backlogguard.llm.providers import GenerationResult

ITEMS = [
    ("Notificación por email", EMAIL),
    ("Reporte mensual en Excel", EXCEL),
    ("App móvil de consulta", MOBILE),
    ("Exportar el reporte a PDF", PDF),
]


class ContentCritic:
    """Crítico que responde según el ítem del pedido y no por guion: en paralelo el orden de las llamadas no está garantizado."""

    model = "fake-critic"

    def __init__(self, delay=0.0, fail_on=()):
        self.delay, self.fail_on, self.prompts = delay, set(fail_on), []
        self.active = self.peak = 0  # revisiones en curso a la vez y el máximo que se vio
        self._lock = threading.Lock()

    def generate(self, prompt, *, system=None, temperature=0.2):
        self.prompts.append(prompt)
        target = re.search(r"Revisá el ítem (\S+) del tablero", prompt).group(1)
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delay)
        finally:
            with self._lock:
                self.active -= 1
        if target in self.fail_on:
            raise TransientProviderError("503 simulado")
        text = final(json.dumps({"item_id": target, "verdict": "sustentado", "objections": [], "reasoning": "x"}))
        return GenerationResult(text=text, model=self.model, provider="fake", latency_ms=0.0, input_tokens=len(prompt.split()), output_tokens=len(text.split()))

    async def agenerate(self, prompt, *, system=None, temperature=0.2):
        return self.generate(prompt, system=system, temperature=temperature)


def build(tmp_path, critic, *, parallel, items=ITEMS, **budget):
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=NO_FINDINGS, budget=RunBudget(max_parallel_reviews=parallel, **budget))
    world.providers.requerimientos.responses[:] = [*(world.draft(title, source) for title, source in items), final("listo")]
    world.deps = replace(world.deps, providers=replace(world.providers, critico=critic))
    world.graph = build_graph(world.deps, sqlite_checkpointer(tmp_path / "paralelo.sqlite"))
    return world


def test_las_revisiones_de_una_ola_corren_a_la_vez_y_en_fila_de_a_una(tmp_path):
    (tmp_path / "fila").mkdir()
    (tmp_path / "olas").mkdir()
    in_line, in_waves = ContentCritic(delay=0.2), ContentCritic(delay=0.2)
    build(tmp_path / "fila", in_line, parallel=1).run()
    build(tmp_path / "olas", in_waves, parallel=3).run()
    assert in_line.peak == 1 and in_waves.peak == 3  # tope de la ola: nunca más de N a la vez


def test_en_paralelo_el_resultado_es_el_mismo_que_en_fila(tmp_path):
    (tmp_path / "fila").mkdir()
    (tmp_path / "olas").mkdir()
    line = build(tmp_path / "fila", ContentCritic(), parallel=1)
    waves = build(tmp_path / "olas", ContentCritic(), parallel=3)
    a, b = line.run(), waves.run()
    board_a, board_b = Board.model_validate(a["board"]), Board.model_validate(b["board"])
    assert {k: v.state for k, v in board_a.items.items()} == {k: v.state for k, v in board_b.items.items()}
    assert all(item.state is ItemState.SUSTENTADO for item in board_b.items.values()) and len(board_b.items) == 4
    assert {k: v["outcome"] for k, v in a["reviewed"].items()} == {k: v["outcome"] for k, v in b["reviewed"].items()}
    assert a["tokens"] == b["tokens"] and b["status"] == a["status"] == "plan_pendiente_de_aprobacion"
    ids = [t["id"] for t in b["tasks"]]
    assert len(ids) == len(set(ids)) and ids == [f"T-{n:03d}" for n in range(1, len(ids) + 1)]  # sin repetidos, en orden
    reviewed_order = [t["ref"] for t in b["tasks"] if t["kind"] == "revisar"]
    assert reviewed_order == [item_id(title) for title, _ in ITEMS]  # el orden de la ola, no el de llegada


def test_las_olas_son_de_a_n_y_se_revisa_cada_item_una_vez(tmp_path):
    world = build(tmp_path, ContentCritic(), parallel=3)
    state = world.run()
    waves = [e["wave"] for e in state["trace"] if e["node"] == "triage"]
    assert [len(w) for w in waves] == [3, 1] and sum(waves, []) == [item_id(t) for t, _ in ITEMS]
    assert nodes(state).count("review") == 4 and len(world.deps.providers.critico.prompts) == 4


def test_si_una_rama_falla_las_demas_siguen_y_el_error_queda_visible(tmp_path):
    broken = item_id(ITEMS[1][0])
    world = build(tmp_path, ContentCritic(fail_on={broken}), parallel=3)
    state = world.run()
    board = Board.model_validate(state["board"])
    assert state["reviewed"][broken]["outcome"] == "error"
    assert [k for k, v in state["reviewed"].items() if v["outcome"] == "sustentado"] == [item_id(t) for t, _ in ITEMS if item_id(t) != broken]
    assert board.items[broken].state is ItemState.BORRADOR
    assert [e["ref"] for e in state["errors"]] == [broken] and "review" in {e["node"] for e in state["errors"]}


def test_el_tope_de_items_se_respeta_por_olas(tmp_path):
    world = build(tmp_path, ContentCritic(), parallel=2, max_items_to_review=3)
    state = world.run()
    board = Board.model_validate(state["board"])
    assert len(state["reviewed"]) == 3 and state["stop_reason"] == "items"
    assert sum(1 for item in board.items.values() if item.state is ItemState.BORRADOR) == 1  # lo que no se revisó queda pendiente


def test_el_triage_excluye_duplicados_sin_modelos_y_arma_la_ola(tmp_path):
    world = build(tmp_path, ContentCritic(), parallel=2)
    board = Board()
    citation = citation_for(world.retriever, "reunion_01_kickoff", "email nuevo estado")
    first = add_item(board, citation, item_id="HU-1", title="Aviso por email al cambiar el estado")
    add_item(board, citation, item_id="HU-2", title="Notificación por email del cambio de estado", description=first.description)
    other = citation_for(world.retriever, "reunion_02_seguimiento", "lo queremos en Excel")
    for n in (3, 4, 5):
        add_item(board, other, item_id=f"HU-{n}", title=f"Reporte {n} distinto")
    state = {"board": board.model_dump(mode="json"), "pending": ["HU-1", "HU-2", "HU-3", "HU-4", "HU-5"], "reviewed": {}, "tokens": 0}
    update = make_nodes(world.deps)["triage"](state)
    assert update["wave"] == ["HU-1", "HU-3"] and update["pending"] == ["HU-4", "HU-5"]
    assert update["reviewed"]["HU-2"]["outcome"] == "excluido_duplicado"
    assert Board.model_validate(update["board"]).items["HU-2"].state is ItemState.EXCLUIDO
    assert world.deps.providers.critico.prompts == []  # no se llamó a ningún modelo


def test_los_eventos_en_vivo_dicen_de_que_item_son(tmp_path):
    events = []
    world = build(tmp_path, ContentCritic(), parallel=3)
    world.deps = replace(world.deps, on_event=events.append)
    world.graph = build_graph(world.deps, sqlite_checkpointer(tmp_path / "paralelo.sqlite"))
    world.run()
    tagged = {e["item"] for e in events if e.get("agent") == "critico" and e.get("item")}
    assert tagged == {item_id(t) for t, _ in ITEMS[:3]} | {item_id(ITEMS[3][0])}


def test_un_plan_se_puede_aprobar_despues_de_revisar_en_paralelo(tmp_path):
    world = build(tmp_path, ContentCritic(), parallel=3)
    paused = world.run()
    assert paused["status"] == "plan_pendiente_de_aprobacion"
    state = answer(world, "approve")
    assert state["status"] == "publicada" and world.backlog.writes == 4


def test_renumber_sigue_a_las_tareas_existentes():
    tasks = [{"id": "T-001", "seq": 1, "kind": "revisar"}, {"id": "T-002", "seq": 2, "kind": "revisar"}]
    assert [t["id"] for t in renumber(tasks, 5)] == ["T-006", "T-007"] and tasks[0]["id"] == "T-001"  # no pisa las originales


def test_los_resultados_de_las_ramas_se_vacian_al_juntarlos(tmp_path):
    state = build(tmp_path, ContentCritic(), parallel=3).run()
    assert state.get("review_results", []) == [] and state.get("wave", []) == []  # cada ola empieza de cero


def test_la_auditoria_reabre_una_sola_vez_tambien_en_paralelo(tmp_path):
    old, new = "Reporte mensual en PDF", "Reporte mensual en Excel"
    world = World(tmp_path, supervisor=PLAN, producer=[], critic=[], auditor=[], budget=RunBudget(max_parallel_reviews=3))
    world.providers.requerimientos.responses[:] = [
        world.draft(old, PDF), final("ok"),
        world.draft(new, EXCEL, revises=item_id(old)), final("corregido por el Auditor"),
    ]
    report = {
        "findings": [world.finding("decision_evolucionada", "El reporte pasó de PDF a Excel y el ítem quedó viejo.", PDF, EXCEL, item=item_id(old))],
        "summary": "",
    }
    world.providers.auditor.responses[:] = [final(json.dumps(report))]
    critic = ContentCritic()
    world.deps = replace(world.deps, providers=replace(world.providers, critico=critic))
    world.graph = build_graph(world.deps, sqlite_checkpointer(tmp_path / "reabre.sqlite"))
    state = world.run()
    board = Board.model_validate(state["board"])
    assert [n for n in nodes(state) if n != "triage"] == ["plan", "produce", "review", "audit", "review", "escalate", "integrate"]
    assert len(critic.prompts) == 2 and state["audit_passes"] == 1
    assert board.items[item_id(old)].title == new and board.items[item_id(old)].state is ItemState.SUSTENTADO
