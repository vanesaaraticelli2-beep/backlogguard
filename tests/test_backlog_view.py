"""Vista del backlog simulado: jerarquía, cambios de la corrida, filtros y la pantalla real con el probador de Streamlit."""
import json
from datetime import date

from streamlit.testing.v1 import AppTest

from backlogguard.board import BacklogItem, Board, Citation, SourceType
from backlogguard.ui import backlog_view

GHERKIN = "Dado un cliente Cuando ocurre algo Entonces ve el resultado"


def work_item(id, type, title, parent=None, tags=(), rev=1, state="New", **extra):
    return {"id": id, "type": type, "title": title, "parent_id": parent, "tags": list(tags), "rev": rev, "state": state,
            "description": extra.get("description", ""), "acceptance_criteria": extra.get("criteria", [])}


AFTER = [
    work_item(103, "Task", "Armar el pipeline", parent=102, tags=["bg-item:TA-1"]),
    work_item(102, "User Story", "Alta de alianza", parent=101, tags=["bg-item:HU-1", "bg-key:abc"], description="Como gestor quiero crear alianzas para operar", criteria=[GHERKIN]),
    work_item(101, "Epic", "Alianzas", tags=["bg-item:EP-1"]),
    work_item(100, "User Story", "Reporte cargado a mano"),
    work_item(104, "User Story", "Baja de alianza", parent=101, tags=["bg-item:HU-2"], rev=2),
]
BEFORE = [work_item(100, "User Story", "Reporte cargado a mano"), work_item(104, "User Story", "Baja de alianza", parent=101, tags=["bg-item:HU-2"], rev=1)]


def test_el_arbol_pone_a_cada_padre_antes_que_sus_hijos():
    nodes = backlog_view.build_nodes(AFTER, BEFORE)
    assert [(n.id, n.depth) for n in nodes] == [(101, 0), (102, 1), (103, 2), (104, 1), (100, 0)]  # las épicas primero, cada hijo bajo su padre


def test_marca_nuevo_actualizado_y_sin_cambios():
    by_id = {n.id: n.change for n in backlog_view.build_nodes(AFTER, BEFORE)}
    assert by_id == {100: "sin cambios", 101: "nuevo", 102: "nuevo", 103: "nuevo", 104: "actualizado"}
    assert {n.change for n in backlog_view.build_nodes(AFTER, None)} == {""}  # sin estado anterior no se compara


def test_distingue_lo_de_backlogguard_de_lo_cargado_a_mano():
    nodes = backlog_view.build_nodes(AFTER, BEFORE)
    assert {n.id: n.origin for n in nodes}[100] == "manual" and {n.id: n.origin for n in nodes}[102] == "BacklogGuard"
    assert backlog_view.counts(nodes) == {"total": 5, "nuevos": 3, "actualizados": 1, "manuales": 1}


def test_el_filtro_de_cambios_conserva_los_padres():
    nodes = backlog_view.build_nodes(AFTER, BEFORE)
    assert [n.id for n in backlog_view.apply_filter(nodes, "Nuevos y actualizados")] == [101, 102, 103, 104]
    assert [n.id for n in backlog_view.apply_filter(nodes, "Cargados a mano")] == [100]
    assert len(backlog_view.apply_filter(nodes, "Todos")) == 5


def test_un_padre_que_no_existe_deja_al_ítem_como_raiz():
    (node,) = backlog_view.build_nodes([work_item(7, "Task", "Huérfana", parent=999)], None)
    assert node.depth == 0
    assert backlog_view.rows([node])[0]["Padre"] == "#999"


def test_las_filas_muestran_la_jerarquia_y_el_padre_por_titulo():
    rows = backlog_view.rows(backlog_view.build_nodes(AFTER, BEFORE))
    story = next(r for r in rows if r["#"] == 102)
    assert story["Título"].startswith("    ↳ ") and story["Padre"] == "#101 Alianzas" and story["Cambio"] == "🟢 Nuevo"


def test_la_ficha_incluye_descripcion_criterios_y_el_origen_manual():
    nodes = {n.id: n for n in backlog_view.build_nodes(AFTER, BEFORE)}
    text = backlog_view.detail_markdown(nodes[102])
    assert "Como gestor quiero crear alianzas" in text and "Criterios de aceptación" in text and "Dado un cliente" in text
    assert "Cargado a mano" in backlog_view.detail_markdown(nodes[100])


def test_la_ficha_y_la_fila_incluyen_el_enlace_azure_si_existe():
    item = {**work_item(107, "Product Backlog Item", "Una historia"), "url": "https://tp-itba.visualstudio.com/TP-ITBA/_workitems/edit/107"}
    (node,) = backlog_view.build_nodes([item], None)
    assert backlog_view.rows([node])[0]["Azure DevOps"] == item["url"]
    assert f"[Abrir en Azure DevOps]({item['url']})" in backlog_view.detail_markdown(node)


# ---- la pantalla ----


def page():
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace

    from backlogguard.board import Board
    from backlogguard.integrations import SimulatedBacklog
    from backlogguard.ui.app import tab_backlog

    data = Path(os.environ["BG_TEST_DATA"])
    state = json.loads((data / "estado.json").read_text(encoding="utf-8"))
    controller = SimpleNamespace(
        running=False, read_only=False, deps=SimpleNamespace(backlog=SimulatedBacklog(data / "backlog.json")),
        backlog_before=state["before"], state=lambda: state,
    )
    tab_backlog(controller)


def test_la_pantalla_muestra_el_aviso_la_tabla_y_la_evidencia_del_item(tmp_path, monkeypatch):
    citation = Citation(fragment_id="f1", quote="Necesitamos crear alianzas.", source_name="Reunión 1", source_type=SourceType.REUNION, source_date=date(2026, 10, 20), speaker="Laura")
    board = Board()
    board.add_item(BacklogItem(id="EP-1", kind="epica", title="Alianzas", description="Épica", acceptance_criteria=[], citations=[citation]))
    board.add_item(BacklogItem(id="HU-1", kind="historia", title="Alta de alianza", description="Como gestor quiero crear alianzas para operar", acceptance_criteria=[GHERKIN], citations=[citation], parent_id="EP-1", requirement_id="RQ-001", requirement_version=2))
    (tmp_path / "estado.json").write_text(json.dumps({"board": board.model_dump(mode="json"), "before": BEFORE}), encoding="utf-8")
    (tmp_path / "backlog.json").write_text(json.dumps({"next_id": 200, "items": [{**w, "description": w["description"], "acceptance_criteria": w["acceptance_criteria"]} for w in AFTER]}), encoding="utf-8")
    monkeypatch.setenv("BG_TEST_DATA", str(tmp_path))
    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.exception
    assert "SIMULADO" in " ".join(i.value for i in at.info)
    assert [m.value for m in at.metric] == ["5", "3", "1", "1"]
    at.selectbox(key="backlog_detalle").select("#102 · User Story · Alta de alianza").run()
    text = " ".join(m.value for m in at.markdown)
    assert "Requisito:** RQ-001 v2" in text and "Necesitamos crear alianzas." in text
