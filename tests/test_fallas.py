from backlogguard.graph.budgets import RunBudget, over_budget
from backlogguard.graph.failures import account_blocked, explain_llm_failure

LIMIT = ("InvalidRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': "
         "'You have reached your specified API usage limits. You will regain access on 2026-12-01 at 00:00 UTC.'}}")


def test_el_limite_de_gasto_se_explica_con_la_fecha_y_que_hacer():
    text = explain_llm_failure(LIMIT)
    assert "límite de gasto" in text and "2026-12-01" in text and "Settings → Limits" in text
    assert account_blocked(LIMIT) and account_blocked("credit balance is too low") and not account_blocked("503 servicio no disponible")


def test_con_la_cuenta_bloqueada_el_presupuesto_corta_la_corrida():
    assert over_budget({"errors": [{"node": "review", "error": LIMIT}]}, RunBudget()) == "cuenta"
    assert over_budget({"errors": [{"node": "review", "error": "el Crítico no llegó a un veredicto"}]}, RunBudget()) is None
