"""Tarjeta «Modelos y costos» del menú izquierdo, probada con AppTest y una corrida reproducida."""
import yaml
from test_ui import screen  # noqa: F401  (fixture)

from backlogguard.board import AgentRole


def warnings(at):
    return " | ".join(w.value for w in at.sidebar.warning)


def test_la_tarjeta_muestra_un_selector_por_agente(screen):  # noqa: F811
    at, _ = screen
    for role in AgentRole:
        assert at.sidebar.selectbox(key=f"modelo-{role.value}").value
    assert at.sidebar.button(key="aplicar-modelos").disabled  # sin cambios no hay nada que aplicar


def test_el_critico_con_el_modelo_del_productor_no_se_puede_aplicar(screen):  # noqa: F811
    at, _ = screen
    productor = at.sidebar.selectbox(key="modelo-requerimientos").value
    at.sidebar.selectbox(key="modelo-critico").select(productor).run()
    assert "independencia" in warnings(at)
    assert at.sidebar.button(key="aplicar-modelos").disabled


def test_aplicar_guarda_la_eleccion_en_los_datos_del_proyecto(screen):  # noqa: F811
    at, controller = screen
    at.sidebar.selectbox(key="modelo-critico").select("claude-haiku-5-5").run()
    assert not warnings(at)
    at.sidebar.button(key="aplicar-modelos").click().run()
    saved = yaml.safe_load((controller.data_dir / "models.yaml").read_text(encoding="utf-8"))
    assert saved["agents"]["critico"]["model"] == "claude-haiku-5-5"
    assert controller.models().for_role(AgentRole.CRITICO).model == "claude-haiku-5-5"
    assert at.sidebar.button(key="aplicar-modelos").disabled
