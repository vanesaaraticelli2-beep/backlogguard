"""Pantalla de Streamlit, probada con el probador integrado (AppTest) y una corrida reproducida."""
import json
from pathlib import Path

import pytest
from test_demo import record_run

from backlogguard.llm import Settings
from backlogguard.ui import runtime
from backlogguard.ui.controller import RunController

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
APP = Path(runtime.__file__).with_name("app.py")
ROOT = runtime.ROOT


@pytest.fixture
def screen(tmp_path, monkeypatch):
    """Pantalla lista, con una corrida grabada para reproducir (sin modelos reales)."""
    recording, _ = record_run(tmp_path)
    recording_path = tmp_path / "demo.json"
    recording.save(recording_path)
    data = tmp_path / "datos"
    monkeypatch.setenv("LIVE_MODE", "0")
    monkeypatch.setenv("BACKLOGGUARD_DATA", str(data))
    monkeypatch.setenv("BACKLOGGUARD_RECORDING", str(recording_path))
    at = streamlit_testing.AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    controller = runtime.get_controller(str(data), str(recording_path), False)
    return at, controller


def pick(at, name):
    at.sidebar.selectbox(key="persona").select(name).run()


def texts(at):
    return " | ".join([*(m.value for m in at.markdown), *(i.value for i in at.info), *(s.value for s in at.subheader), *(c.value for c in at.caption)])


def start_and_wait(at, controller):
    at.button(key="iniciar").click().run()
    assert controller.wait(30)
    at.run()


def test_la_pantalla_arranca_en_modo_demo_con_las_personas(screen):
    at, controller = screen
    assert not at.exception and controller.mode == "demo"
    assert len(at.sidebar.selectbox(key="persona").options) == 3 and "Sergio" in at.sidebar.selectbox(key="persona").options[0]
    assert at.button(key="iniciar").disabled is False


def test_cada_persona_ve_solo_sus_pedidos(screen):
    at, controller = screen
    start_and_wait(at, controller)
    pick(at, "sergio")  # el primer pedido lo decide el product owner
    assert "No tenés pedidos pendientes" in texts(at) and not at.get("form_submit_button") and not [b for b in at.button if b.key == "aprobar"]
    pick(at, "laura")
    assert [b for b in at.button if b.key == "aprobar"] and "Desacuerdo sin consenso" in texts(at)


def test_el_pedido_muestra_la_evidencia_y_las_acciones(screen):
    at, controller = screen
    start_and_wait(at, controller)
    pick(at, "laura")
    keys = {b.key for b in at.button}
    assert {"aprobar", "editar", "rechazar"} <= keys
    body = texts(at)
    assert "Evidencia" in body and "recibir un email" in body and "Reunión de kickoff" in body and "Laura (PO)" in body
    assert any(t.key and t.key.endswith("-titulo") for t in at.text_input)  # los campos editables existen


def test_decidir_en_la_pantalla_reanuda_la_corrida(screen):
    at, controller = screen
    start_and_wait(at, controller)
    pick(at, "laura")
    pending = controller.pending()["request"]
    at.button(key="aprobar").click().run()
    assert controller.wait(30)
    at.run()
    following = controller.pending()["request"]
    assert following["request_id"] != pending["request_id"]  # el pedido anterior desapareció
    pick(at, "vanesa")
    assert following["kind"] in ("alcance", "plan")


def test_el_recorrido_completo_desde_la_pantalla(screen):
    at, controller = screen
    start_and_wait(at, controller)
    answered = []
    for _ in range(10):
        request = controller.pending()
        if request is None:
            break
        request = request["request"]
        decider = {"service_manager": "sergio", "product_owner": "laura", "full_stack_ia_engineer": "vanesa"}[request["decides"]]
        pick(at, decider)
        at.button(key="aprobar").click().run()
        assert controller.wait(30)
        at.run()
        answered.append(request["kind"])
    assert answered == ["item", "alcance", "alcance", "alcance", "plan"]
    state = controller.state()
    assert state["status"] == "publicada" and state["summary"]
    assert "plan publicado en el backlog" in texts(at) or any("plan publicado" in str(m.value) for m in at.success)
    assert [w.title for w in controller.deps.backlog.search() if any(t.startswith("bg-item:") for t in w.tags)]
    assert "Registro de decisiones" in texts(at)


def test_la_pantalla_muestra_la_actividad_y_el_tablero(screen):
    at, controller = screen
    start_and_wait(at, controller)
    activity = "\n".join(controller.activity())
    assert "▶ Requerimientos redacta" in activity and "Crítico termina" in activity
    assert any("Notificación por email" in str(df.value) for df in at.dataframe)  # el tablero lo muestra


def test_el_backlog_simulado_se_ve_antes_y_despues(screen):
    at, controller = screen
    start_and_wait(at, controller)
    assert [w["title"] for w in controller.backlog_before] == ["Ingreso al portal con SSO corporativo", "Pantalla de ayuda y preguntas frecuentes"]
    for _ in range(10):
        request = controller.pending()
        if request is None:
            break
        decider = {"service_manager": "sergio", "product_owner": "laura", "full_stack_ia_engineer": "vanesa"}[request["request"]["decides"]]
        pick(at, decider)
        at.button(key="aprobar").click().run()
        assert controller.wait(30)
        at.run()
    after = [w.title for w in controller.deps.backlog.search()]
    assert len(after) == len(controller.backlog_before) + 1 and "Notificación por email" in after


def test_el_controlador_rechaza_decidir_sin_pausa_y_dos_corridas_a_la_vez(tmp_path):
    controller = RunController(ROOT, Settings(live_mode=False), tmp_path / "datos")
    with pytest.raises(RuntimeError):
        controller.decide({"decision": "approve"})
    assert controller.pending() is None and controller.state() == {} and controller.mode == "simulado"
