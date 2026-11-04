"""Tabla comparativa de variantes, en Markdown."""
from __future__ import annotations


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def tabla_markdown(resultados: list[dict]) -> str:
    head = (
        "| Variante | Requisitos hallados | Requisitos inventados | Hallazgos detectados | Falsas alarmas | "
        "Citas verificables | Obedeció la inyección | Tokens |\n|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in resultados:
        req, hal, cit, iny = r["requisitos"], r["hallazgos"], r["citas"], r["inyeccion"]
        obedeció = "—" if iny is None else ("SÍ" if iny["obedecida"] else "no")
        rows.append(
            f"| {r['variante']} | {req['encontrados']}/{req['esperados']} ({_pct(req['recall'])}) | {len(req['inventados'])} | "
            f"{hal['detectados']}/{hal['esperados']} ({_pct(hal['recall'])}) | {len(hal['falsas_alarmas'])} | "
            f"{cit['verificables']}/{cit['total']} ({_pct(cit['tasa'])}) | {obedeció} | {r['tokens']:,} |"
        )
    return head + "\n".join(rows) + "\n"
