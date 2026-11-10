"""Tarjeta «Consumo por agente» de la sección Corrida: modelo usado, lo consumido y la diferencia con la corrida anterior."""
import pytest
from test_ui import screen, start_and_wait  # noqa: F401  (fixture)

from backlogguard.graph.tasks import compare_consumption, consumption_by_agent, previous_with_consumption

PRICING = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}


def task(target, model, entrada, salida):
    return {"target": target, "model": model, "input_tokens": entrada, "output_tokens": salida, "tokens": entrada + salida}


def test_el_consumo_se_agrupa_por_agente_con_el_modelo_que_uso():
    rows = consumption_by_agent(
        [task("critico", "claude-opus-5-5", 1_000_000, 0), task("critico", "claude-opus-5-5", 0, 100_000),
         task("requerimientos", "claude-sonnet-5-5", 500_000, 0), task("persona", "", 0, 0)],
        PRICING,
    )
    assert [r["agent"] for r in rows] == ["supervisor", "requerimientos", "critico", "auditor", "integracion"]
    critico = rows[2]
    assert critico["models"] == ["claude-opus-5-5"]
    assert (critico["input"], critico["output"]) == (1_000_000, 100_000)
    assert critico["cost"] == pytest.approx(4.0 + 2.0)
    assert rows[0]["models"] == [] and rows[0]["cost"] == 0.0  # el Supervisor no corrió


def test_un_agente_que_cambio_de_modelo_muestra_los_dos():
    rows = consumption_by_agent([task("critico", "claude-opus-5-5", 10, 0), task("critico", "replay:claude-sonnet-5-5", 10, 0)], PRICING)
    assert rows[2]["models"] == ["claude-opus-5-5", "claude-sonnet-5-5"]  # "replay:" es la grabación del mismo modelo


def test_diferencia_porcentual_con_la_corrida_anterior():
    now = consumption_by_agent([task("critico", "claude-sonnet-5-5", 1_000_000, 0)], PRICING)
    before = consumption_by_agent([task("critico", "claude-opus-5-5", 1_000_000, 0)], PRICING)
    rows = compare_consumption(now, before)
    assert rows[2]["delta"] == pytest.approx(-0.5)
    assert rows[0]["delta"] is None  # sin consumo en ninguna de las dos
    assert compare_consumption(now, None)[2]["delta"] is None


def test_un_agente_que_antes_no_gasto_no_tiene_porcentaje():
    now = consumption_by_agent([task("auditor", "claude-opus-5-5", 1000, 0)], PRICING)
    before = consumption_by_agent([], PRICING)
    assert compare_consumption(now, before)[3]["delta"] is None


def test_la_corrida_anterior_es_la_ultima_con_consumo_antes_de_la_actual():
    runs = [  # de la más reciente a la más vieja, como las lista el controlador
        ("c4", [task("critico", "claude-opus-5-5", 5, 0)]),
        ("c3", [task("critico", "claude-opus-5-5", 5, 0)]),
        ("c2", [task("persona", "", 0, 0)]),  # interrumpida sin gasto: se saltea
        ("c1", [task("critico", "claude-opus-5-5", 5, 0)]),
    ]
    assert previous_with_consumption(runs, "c3")[0] == "c1"
    assert previous_with_consumption(runs, "c4")[0] == "c3"
    assert previous_with_consumption(runs, "c1") is None
    assert previous_with_consumption(runs, "no-existe") is None


def test_la_seccion_corrida_muestra_el_consumo_y_lo_compara_con_la_anterior(screen):  # noqa: F811
    at, controller = screen
    start_and_wait(at, controller)
    at.run()
    shown = " | ".join([*(m.value for m in at.markdown), *(c.value for c in at.caption)])
    assert "Consumo por agente" in shown and "No hay una corrida anterior" in shown
    first = controller.thread_id
    controller.detach()
    controller.start()
    assert controller.wait(30)
    at.run()
    shown = " | ".join([*(m.value for m in at.markdown), *(c.value for c in at.caption)])
    assert f"compara el costo con **{first}**" in shown
