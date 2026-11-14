import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

from backlogguard.llm import Settings

ORG = "https://tp-itba.visualstudio.com/"
PROJECT = "TP-ITBA"
PAT = "no-mostrar-este-pat"


class FakeBacklog:
    def test_connection(self):
        return {"project": PROJECT, "work_item_types": ["Epic", "Product Backlog Item", "Task"]}

    def list_projects(self):
        return [{"id": "p1", "name": PROJECT}]


class Controller:
    running = False

    def __init__(self, mode="real", *, endpoint=None, token=PAT):
        from types import SimpleNamespace

        self.settings = Settings(
            azdo_mode=mode,
            azdo_org_url=ORG,
            azdo_project=PROJECT,
            azdo_mcp_endpoint=endpoint,
            azdo_token=token,
        )
        self.deps = SimpleNamespace(backlog=FakeBacklog())


def page():
    import streamlit as st

    from backlogguard.ui.app import tab_azure_connection

    tab_azure_connection(st.session_state["test_controller"])


def render(controller):
    app = streamlit_testing.AppTest.from_function(page)
    app.session_state["test_controller"] = controller
    return app.run()


def text(at):
    return " ".join(
        [
            *(element.value for element in at.markdown),
            *(element.value for element in at.info),
            *(element.value for element in at.caption),
            *(element.value for element in at.success),
        ]
    )


def test_la_pantalla_prueba_la_conexion_sin_exponer_el_pat():
    at = render(Controller())

    assert not at.exception
    assert PAT not in text(at)
    at.button(key="probar-conexion-azure").click().run()
    assert any("Conexión correcta" in element.value for element in at.success)
    assert "Product Backlog Item" in text(at)


def test_la_pantalla_lista_proyectos_sin_hacer_escrituras():
    at = render(Controller())
    at.button(key="listar-proyectos-azure").click().run()

    assert not at.exception
    assert any(PROJECT in str(table.value) for table in at.dataframe)
    assert PAT not in text(at)


def test_el_modo_simulado_no_habilita_llamadas_reales():
    at = render(Controller(mode="simulated"))

    assert not at.exception
    assert "Modo simulado" in text(at)
    assert not [button for button in at.button if button.key in {"probar-conexion-azure", "listar-proyectos-azure"}]


def test_la_conexion_http_mcp_no_requiere_un_pat_en_el_cliente():
    at = render(Controller(endpoint="https://mcp.example.com/mcp", token=None))

    assert not at.exception
    assert not at.error
    assert "gestionada por el servidor MCP" in text(at)
    at.button(key="probar-conexion-azure").click().run()
    assert any("Conexión correcta" in element.value for element in at.success)
