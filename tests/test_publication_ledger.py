from pathlib import Path

from backlogguard.graph.setup import publication_ledger_path


def test_publicaciones_reales_y_simuladas_usan_registros_separados(tmp_path: Path):
    assert publication_ledger_path(tmp_path, "simulated") == tmp_path / "publicaciones.sqlite"
    assert publication_ledger_path(tmp_path, "real") == tmp_path / "publicaciones_azure.sqlite"
