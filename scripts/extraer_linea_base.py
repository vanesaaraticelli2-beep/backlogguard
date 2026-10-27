r"""Extrae una sola vez los compromisos de la preventa (la línea base) con el modelo del Auditor.

    .venv\Scripts\python scripts\extraer_linea_base.py                 # muestra la estimación de gasto, no corre
    .venv\Scripts\python scripts\extraer_linea_base.py --confirmar     # extrae, verifica las citas y guarda
    .venv\Scripts\python scripts\extraer_linea_base.py --ver           # muestra lo ya extraído

Nunca corre sola: sin --confirmar solo estima. Necesita LIVE_MODE=1. El resultado queda en `data/linea_base/` ligado a la
huella de la preventa y se invalida si la preventa cambia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backlogguard.board import AgentRole, SourceType
from backlogguard.graph.setup import baseline_dir, user_sources_dir
from backlogguard.llm import Settings, build_provider, load_models_config
from backlogguard.llm.metering import load_pricing
from backlogguard.rag import SourceLibrary
from backlogguard.rag.compromisos import BaselineStore, ExtractionNeedsRealModel, estimate_extraction, extract_commitments

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def show(baseline) -> None:
    print(f"\n{len(baseline.commitments)} compromisos verificados, {len(baseline.discarded)} descartados · modelo {baseline.model} · huella {baseline.fingerprint}")
    for epic, rows in baseline.by_epic().items():
        print(f"\n▶ {epic}")
        for c in rows:
            print(f"   {c.id} [{c.scope}] p. {c.page}: {c.capability}")
            print(f"        «{c.quote[:140]}»")
    for d in baseline.discarded:
        print(f"   ✘ descartado (p. {d.page}): {d.capability} — {d.reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preventa", help="id de la preventa (si hay una sola, se usa esa)")
    parser.add_argument("--confirmar", action="store_true", help="confirmo el gasto y quiero extraer")
    parser.add_argument("--ver", action="store_true", help="muestra los compromisos ya extraídos")
    options = parser.parse_args()

    library = SourceLibrary(user_sources_dir(DATA))
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA] if library.root.is_dir() else []
    chosen = options.preventa or (presales[0] if len(presales) == 1 else None)
    if chosen not in presales:
        print(f"Indicá la preventa con --preventa. Disponibles: {presales or 'ninguna (importala con scripts/importar_fuentes.py)'}")
        return 1
    document, store = library.load(chosen), BaselineStore(baseline_dir(DATA))
    print(f"Preventa: {document.metadata.source_name} ({chosen}) · huella {document.fingerprint} · estado: {store.status(document)}")
    if options.ver:
        saved = store.current(document)
        show(saved) if saved else print("No hay compromisos vigentes para esta huella.")
        return 0

    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.AUDITOR)
    pricing = load_pricing()
    estimate = estimate_extraction(document.text, spec.model, pricing)
    cost = f"~US$ {estimate['cost_usd']:.2f}" if estimate["cost_usd"] is not None else "sin precio configurado"
    print(f"Modelo {spec.model}: {estimate['calls']} llamada(s), ~{estimate['input_tokens']:,} tokens de entrada y ~{estimate['output_tokens']:,} de salida, {cost} (estimación).")
    if not options.confirmar:
        print("No se ejecutó nada. Agregá --confirmar para extraer.")
        return 0
    try:
        baseline = extract_commitments(document, build_provider(spec, settings), store, confirmed=True, pricing=pricing)
    except ExtractionNeedsRealModel as exc:
        print(exc)
        return 1
    show(baseline)
    real = f"~US$ {baseline.cost_usd:.3f}" if baseline.cost_usd is not None else "sin precio"
    print(f"\nGastó {baseline.input_tokens:,} tokens de entrada y {baseline.output_tokens:,} de salida ({real}). Guardado en data/linea_base/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
