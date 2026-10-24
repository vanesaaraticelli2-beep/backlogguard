from datetime import date

import pytest

from backlogguard.board import (
    BacklogItem,
    BoardCheckpointStore,
    BoardRunState,
    Citation,
    ItemKind,
    ItemState,
    SourceType,
    StaleCheckpointError,
)


def make_state(run_id="run-1") -> BoardRunState:
    state = BoardRunState(run_id=run_id)
    item = BacklogItem(
        id="H-1",
        kind=ItemKind.HISTORIA,
        title="Exportar reporte",
        citations=[
            Citation(
                fragment_id="m1-003",
                quote="Exportar a Excel.",
                source_name="Kickoff",
                source_type=SourceType.REUNION,
                source_date=date(2026, 10, 5),
            )
        ],
    )
    item.transition_to(ItemState.SUSTENTADO)
    state.board.add_item(item)
    return state


def test_guardar_y_cargar_conserva_el_tablero(tmp_path):
    store = BoardCheckpointStore(tmp_path / "ck.json")
    saved = store.save(make_state())
    loaded = BoardCheckpointStore(tmp_path / "ck.json").load("run-1")
    assert saved.checkpoint_version == 1 == loaded.checkpoint_version
    assert loaded.board.items["H-1"].state is ItemState.SUSTENTADO
    assert loaded.board.items["H-1"].citations[0].source_date == date(2026, 10, 5)


def test_la_version_avanza_en_cada_guardado(tmp_path):
    store = BoardCheckpointStore(tmp_path / "ck.json")
    first = store.save(make_state())
    second = store.save(first)
    assert second.checkpoint_version == 2


def test_snapshot_viejo_se_rechaza(tmp_path):
    store = BoardCheckpointStore(tmp_path / "ck.json")
    first = store.save(make_state())
    store.save(first)
    with pytest.raises(StaleCheckpointError):
        store.save(first)


def test_run_inexistente(tmp_path):
    with pytest.raises(KeyError):
        BoardCheckpointStore(tmp_path / "ck.json").load("nada")


def test_corridas_independientes(tmp_path):
    store = BoardCheckpointStore(tmp_path / "ck.json")
    store.save(make_state("a"))
    store.save(make_state("b"))
    assert store.load("a").run_id == "a" and store.load("b").run_id == "b"
