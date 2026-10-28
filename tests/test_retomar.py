"""Retomar una corrida pausada después de reiniciar la aplicación."""
from pathlib import Path

import pytest

from backlogguard.llm import Settings
from backlogguard.ui.controller import RunController
from backlogguard.ui.runtime import DEFAULT_RECORDING

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not DEFAULT_RECORDING.exists(), reason="todavía no hay una corrida grabada")


def decision_for(request: dict) -> dict:
    actor = {"service_manager": "service_manager", "product_owner": "product_owner", "full_stack_ia_engineer": "full_stack_ia_engineer"}[request["decides"]]
    return {
        "decision": "approve", "actor": actor, "actor_role": request["decides"], "request_id": request["request_id"],
        "request_version": request["version"], "args_hash": request["args_hash"],
    }


def test_una_corrida_pausada_se_retoma_despues_de_reiniciar_y_se_puede_decidir(tmp_path):
    data = tmp_path / "datos"
    before = RunController(ROOT, Settings(live_mode=False), data, DEFAULT_RECORDING)
    paused = before.start()
    assert before.wait(60) and before.pending() is not None
    request = before.pending()["request"]
    before.close()

    after = RunController(ROOT, Settings(live_mode=False), data, DEFAULT_RECORDING)  # la aplicación se reinició: no hay corrida abierta
    assert after.pending() is None and [r["thread_id"] for r in after.list_runs() if r["waiting"]] == [paused]
    after.open_run(paused)  # abrirla sola la deja de solo lectura
    assert after.read_only
    with pytest.raises(RuntimeError, match="solo lectura"):
        after.decide(decision_for(request))
    after.resume_run(paused)
    assert not after.read_only and after.thread_id == paused and after.pending() is not None
    after.decide(decision_for(after.pending()["request"]))
    assert after.wait(60)
    after.close()


def test_solo_se_retoma_una_corrida_que_espera_una_decision(tmp_path):
    controller = RunController(ROOT, Settings(live_mode=False), tmp_path / "datos")
    with pytest.raises(KeyError, match="no existe o no está esperando"):
        controller.resume_run("corrida-que-no-existe")
    controller.close()
