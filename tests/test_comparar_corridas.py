from backlogguard.evaluation.corridas import metrics, table

PRICING = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}


def task(kind, ref=None, round=None, detail="", model="claude-sonnet-5-5", inp=1_000_000, out=0):
    return {"kind": kind, "ref": ref, "round": round, "detail": detail, "model": model, "input_tokens": inp, "output_tokens": out}


STATE = {
    "board": {"items": {"HU-RQ-001": {"requirement_id": "RQ-001"}, "HU-RQ-002": {"requirement_id": "RQ-002"}}},
    "tasks": [
        task("redactar"),  # US$ 2 por la tanda de dos historias
        task("revisar", "HU-RQ-001", 1, "objetado: falta un escenario", "claude-opus-5-5"),  # US$ 4
        task("corregir", "HU-RQ-001"),  # US$ 2
        task("revisar", "HU-RQ-001", 2, "objetado: sigue faltando", "claude-opus-5-5"),  # US$ 4
        task("revisar", "HU-RQ-002", 1, "sustentado", "claude-opus-5-5"),  # US$ 4
        task("decidir", inp=0),
    ],
}


def test_metricas_de_una_corrida():
    row = metrics("a", STATE, PRICING)
    assert (row["historias"], row["objetadas_ronda_1"], row["revisadas_ronda_1"], row["sin_consenso"], row["correcciones"]) == (2, 1, 2, 1, 1)
    assert row["tasa_objecion_ronda_1"] == 0.5 and row["costo_usd"] == 16.0 and row["costo_por_historia"] == 8.0


def test_filtrar_por_requisitos_prorratea_la_redaccion():
    row = metrics("a", STATE, PRICING, {"RQ-002"})
    assert row["historias"] == 1 and row["sin_consenso"] == 0 and row["costo_usd"] == 1.0 + 4.0 and row["prorrateado"]


def test_la_tabla_muestra_una_fila_por_corrida():
    text = table([metrics("antes", STATE, PRICING), metrics("después", STATE, PRICING, {"RQ-001"})])
    assert "| antes | 2 | 1 de 2 (50%) | 1 | 1 |" in text and "| después | 1 |" in text and "prorratea" in text


def test_costo_estimado_de_una_corrida_chica():
    from backlogguard.ui.app import run_cost_range

    low, high = run_cost_range(9)
    assert round(low, 2) == 0.99 and round(high, 2) == 2.16
