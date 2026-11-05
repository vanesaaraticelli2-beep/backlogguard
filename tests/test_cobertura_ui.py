from streamlit.testing.v1 import AppTest

STATE = {
    "board": {"items": {}, "findings": [], "messages": []},
    "coverage_scope": [{"id": "RQ-001", "title": "Uno"}, {"id": "RQ-002", "title": "Dos"}],
    "not_drafted": {"RQ-002": "La corrida se cortó antes de redactarlo: se agotó el tiempo de la corrida."},
}


def page():
    import json
    import os

    from backlogguard.ui.coverage_view import coverage_line, coverage_section

    state = json.loads(os.environ["BG_TEST_STATE"])
    coverage_section(state)
    import streamlit as st

    st.write(f"LINEA: {coverage_line(state)}")


def test_la_cobertura_dice_que_requisitos_quedaron_sin_historia_y_por_que(monkeypatch):
    import json

    monkeypatch.setenv("BG_TEST_STATE", json.dumps(STATE))
    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "0 de 2 requisitos con historia" in text and "RQ-002" in text and "se agotó el tiempo" in text


def test_sin_requisitos_de_la_corrida_no_muestra_nada(monkeypatch):
    import json

    monkeypatch.setenv("BG_TEST_STATE", json.dumps({"board": {"items": {}, "findings": [], "messages": []}}))
    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.exception and [m.value for m in at.markdown] == ["LINEA: None"]
