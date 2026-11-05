import base64

from streamlit.testing.v1 import AppTest

from backlogguard.ui.working import RUNNER_URI, runner_html, working


def test_runner_is_an_animated_svg():
    svg = base64.b64decode(RUNNER_URI.split(",", 1)[1]).decode()
    assert svg.startswith("<svg") and "@keyframes" in svg and "animation" in svg


def test_runner_html_escapes_text():
    assert "&lt;b&gt;" in runner_html("<b>x</b>") and RUNNER_URI in runner_html("trabajando")


def test_working_shows_and_clears():
    def app():
        import streamlit as st

        from backlogguard.ui.working import working

        with working("Procesando…"):
            st.write("dentro")
        st.write("fuera")

    at = AppTest.from_function(app).run()
    assert not at.exception
    assert [m.value for m in at.markdown] == ["dentro", "fuera"]
