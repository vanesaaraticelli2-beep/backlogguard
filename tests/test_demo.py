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
    roles = {"service_manager": "sergio", "product_owner": "laura", "full_stack_ia_engineer": "vanesa"}
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
