"""Modo demo: grabar una corrida y reproducirla da el mismo resultado, sin modelos."""
import json

from test_graph import PLAN, World, final, item_id
from test_hitl import TITLE, board_of, disputed, finish, scope_report

from backlogguard.graph import RunDeps, build_graph, load_state, run_pipeline, sqlite_checkpointer
from backlogguard.integrations import PublicationLedger, SimulatedBacklog
from backlogguard.llm.recording import Recording, RecordingProvider, recording_providers, replay_providers
from backlogguard.memory import ProjectMemory


def record_run(tmp_path) -> tuple[Recording, dict]:
    """Corre una corrida guionada con proveedores que graban y devuelve (grabación, estado final)."""
    world = disputed(tmp_path / "grabar")
    world.providers.auditor.responses[:] = [final(json.dumps(scope_report(world)))]
    recording = Recording(objective="demo")
    world.deps = RunDeps(**{**world.deps.__dict__, "providers": recording_providers(world.providers, recording)})
    world.graph = build_graph(world.deps, sqlite_checkpointer(world.db))
    run_pipeline(world.graph, "demo", "t1")
    return recording, finish(world)


def fresh_deps(world: World, tmp_path, recording: Recording) -> RunDeps:
    return RunDeps(
        **{
            **world.deps.__dict__,
            "providers": replay_providers(recording),
            "backlog": SimulatedBacklog(),
            "ledger": PublicationLedger(tmp_path / "pub.sqlite"),
            "memory": ProjectMemory(tmp_path / "mem.sqlite", "acme"),
        }
    )


def test_grabar_y_reproducir_da_el_mismo_resultado(tmp_path):
    recording, original = record_run(tmp_path)
    assert all(recording.responses[role] for role in ("supervisor", "requerimientos", "critico", "auditor", "integracion"))
    assert recording.models["critico"].startswith("fake")

    path = tmp_path / "demo.json"
    recording.save(path)  # va y vuelve por el archivo
    loaded = Recording.load(path)
    assert loaded.responses == recording.responses

    replay_world = World(tmp_path / "reproducir", supervisor=[], producer=[], critic=[], auditor=[])
    replay_world.deps = fresh_deps(replay_world, tmp_path / "reproducir", loaded)
    replay_world.graph = build_graph(replay_world.deps, sqlite_checkpointer(tmp_path / "reproducir" / "ck.sqlite"))
    run_pipeline(replay_world.graph, "demo", "t1")
    replayed = finish(replay_world)

    assert replayed["status"] == original["status"] == "publicada"
    assert board_of(replayed).model_dump() == board_of(original).model_dump()
    assert [(r["item_id"], r["outcome"]) for r in replayed["publication"]["results"]] == [
        (r["item_id"], r["outcome"]) for r in original["publication"]["results"]
    ]
    assert replayed["summary"] == original["summary"]
    assert replay_world.deps.backlog.search()[0].title == TITLE and item_id(TITLE) in board_of(replayed).items


def test_la_reproduccion_no_usa_los_proveedores_reales(tmp_path):
    recording = Recording(responses={"supervisor": ["uno"], "requerimientos": [], "critico": [], "auditor": [], "integracion": []})
    providers = replay_providers(recording)
    assert providers.supervisor.generate("hola").text == "uno"
    assert providers.supervisor.model.startswith("replay:")


def test_el_proveedor_grabador_anota_solo_lo_que_responde(tmp_path):
    from backlogguard.llm import FakeProvider

    recording = Recording()
    provider = RecordingProvider(FakeProvider(delay_seconds=0, responses=["a", "b"]), "critico", recording)
    provider.generate("x")
    provider.generate("y")
    assert recording.responses["critico"] == ["a", "b"] and recording.responses["auditor"] == []


def test_la_grabacion_de_la_demo_se_reproduce_de_punta_a_punta(tmp_path):
    """Si el flujo cambia y la grabación deja de coincidir, hay que volver a grabarla con scripts/grabar_demo.py."""
    import pytest

    from backlogguard.llm import Settings
    from backlogguard.ui.controller import RunController
    from backlogguard.ui.runtime import DEFAULT_RECORDING, ROOT

    if not DEFAULT_RECORDING.exists():
        pytest.skip("todavía no hay una corrida grabada")
    controller = RunController(ROOT, Settings(live_mode=False), tmp_path / "datos", DEFAULT_RECORDING)
    controller.start()
    assert controller.wait(60)
    roles = {"service_manager": "service_manager", "product_owner": "product_owner", "full_stack_ia_engineer": "full_stack_ia_engineer"}
    for _ in range(12):
        payload = controller.pending()
        if payload is None:
            break
        request = payload["request"]
        controller.decide({
            "decision": "approve", "actor": roles[request["decides"]], "actor_role": request["decides"],
            "request_id": request["request_id"], "request_version": request["version"], "args_hash": request["args_hash"],
        })
        assert controller.wait(60)
    state = controller.state()
    assert controller.error is None and state["status"] == "publicada" and state["summary"]
    assert state["publication"]["ok"] and any(r["outcome"] == "publicado" for r in state["publication"]["results"])
    assert len(controller.deps.backlog.search()) > len(controller.backlog_before)
    controller.close()


# ---- corridas guardadas (abrir una corrida anterior, solo lectura) ----


def finish_with_roles(controller):
    for _ in range(12):
        payload = controller.pending()
        if payload is None:
            break
        request = payload["request"]
        controller.decide({
            "decision": "approve", "actor": request["decides"], "actor_role": request["decides"],
            "request_id": request["request_id"], "request_version": request["version"], "args_hash": request["args_hash"],
        })
        assert controller.wait(60)


def test_una_corrida_guardada_se_abre_desde_otro_proceso_en_solo_lectura(tmp_path):
    import pytest

    from backlogguard.llm import Settings
    from backlogguard.ui.controller import RunController
    from backlogguard.ui.runtime import ROOT

    recording, _ = record_run(tmp_path)
    recording.save(tmp_path / "demo.json")
    data = tmp_path / "datos"
    viewer = RunController(ROOT, Settings(live_mode=False), data)  # «otro proceso»: se abrió antes de que la corrida terminara
    assert viewer.list_runs() == [] and viewer.deps.backlog.search() == []

    runner = RunController(ROOT, Settings(live_mode=False), data, tmp_path / "demo.json")
    thread_id = runner.start()
    assert runner.wait(60)
    finish_with_roles(runner)
    assert runner.state()["status"] == "publicada"

    (saved,) = viewer.list_runs()
    assert saved["thread_id"] == thread_id and saved["status"] == "publicada" and saved["items"] >= 1 and not saved["waiting"]
    viewer.open_run(thread_id)
    state = viewer.state()
    assert viewer.read_only and state["summary"] and state["decisions"] and viewer.pending() is None
    assert viewer.deps.backlog.search()  # vuelve a leer lo que publicó el otro proceso
    lines = viewer.activity()
    assert any("Requerimientos redacta" in line for line in lines) and any("Se aprueba el plan" in line for line in lines)
    with pytest.raises(RuntimeError, match="solo lectura"):
        viewer.decide({"decision": "approve"})
    with pytest.raises(KeyError):
        viewer.open_run("corrida-que-no-existe")
    runner.close()


def test_iniciar_una_corrida_nueva_sale_del_modo_de_solo_lectura(tmp_path):
    from backlogguard.llm import Settings
    from backlogguard.ui.controller import RunController
    from backlogguard.ui.runtime import ROOT

    controller = RunController(ROOT, Settings(live_mode=False), tmp_path / "datos")
    first = controller.start()
    assert controller.wait(60)
    controller.open_run(first)
    assert controller.read_only
    second = controller.start()
    assert controller.wait(60)
    assert not controller.read_only and second != first and {r["thread_id"] for r in controller.list_runs()} == {first, second}
    controller.close()


def test_el_backlog_simulado_vuelve_a_leer_el_archivo(tmp_path):
    from backlogguard.integrations import SimulatedBacklog

    path = tmp_path / "backlog.json"
    reader, writer = SimulatedBacklog(path), SimulatedBacklog(path)
    writer.create(type="User Story", title="Algo publicado", description="", acceptance_criteria=[], tags=[], parent_id=None)
    assert reader.search() == []
    reader.reload()
    assert [w.title for w in reader.search()] == ["Algo publicado"]


def test_la_traza_guardada_se_muestra_por_etapa():
    from backlogguard.graph.live import format_trace

    lines = format_trace([{"node": "plan", "used_default": False, "sources": ["a"]}, {"node": "escalate", "requests": 3, "status": "x"}, {"node": "raro"}])
    assert lines[0].startswith("▶ Supervisor planifica") and "sources" in lines[0]
    assert "requests=3" in lines[1] and lines[2] == "▶ raro"
