r"""Lee una reunión contra el catálogo y guarda sus propuestas (continuidad entre reuniones).

    .venv\Scripts\python scripts\clasificar_reunion.py REUNION                # estima el gasto, no corre
    .venv\Scripts\python scripts\clasificar_reunion.py REUNION --confirmar    # enumera, clasifica y guarda propuestas
    .venv\Scripts\python scripts\clasificar_reunion.py --ver                  # propuestas y requisitos del catálogo

Nunca corre sola: sin --confirmar solo estima. Necesita LIVE_MODE=1. Las propuestas quedan pendientes en
`data/catalogo.sqlite`: solo «ya cubierto» suma evidencia por sí solo; lo demás lo decide una persona.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backlogguard.board import AgentRole, SourceType
from backlogguard.catalog import Catalog
from backlogguard.catalog.ingest import IngestNeedsRealModel, estimate_ingest, ingest_meeting
from backlogguard.graph.setup import baseline_dir, user_sources_dir
from backlogguard.llm import Settings, build_provider, load_models_config
from backlogguard.llm.metering import load_pricing
from backlogguard.rag import SourceLibrary
from backlogguard.rag.compromisos import BaselineStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def show_proposals(catalog: Catalog, source_id: str | None = None) -> None:
    for p in catalog.proposals(source_id=source_id):
        flags = " · FUERA DE ORDEN" if p.out_of_order else ""
        conf = f" · confianza {p.confidence:.2f}" if p.confidence is not None else ""
        target = f" → {', '.join(p.targets)}" if p.targets else ""
        title = p.drafts[0].title if p.drafts else ""
        print(f"\n{p.id} [{p.kind.value}{target}] {p.state.value}{conf}{flags}\n   {title}")
        print(f"   «{p.evidence[0].quote}» ({p.evidence[0].speaker or 'sin orador'})")
        if p.rationale:
            print(f"   motivo: {p.rationale}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reunion", nargs="?", help="id de la reunión o minuta")
    parser.add_argument("--confirmar", action="store_true", help="confirmo el gasto y quiero leer la reunión")
    parser.add_argument("--ver", action="store_true", help="muestra las propuestas y los requisitos guardados")
    options = parser.parse_args()

    catalog = Catalog(DATA / "catalogo.sqlite")
    if options.ver:
        show_proposals(catalog, options.reunion)
        print(f"\nRequisitos en el catálogo: {len(catalog.requirements())}")
        return 0

    library = SourceLibrary(user_sources_dir(DATA))
    meetings = [i for i, m in library.describe() if m.source_type in (SourceType.REUNION, SourceType.MINUTA)] if library.root.is_dir() else []
    if options.reunion not in meetings:
        print(f"Indicá la reunión. Disponibles: {meetings or 'ninguna'}")
        return 1
    document = library.load(options.reunion)
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA]
    presale = library.load(presales[0]) if len(presales) == 1 else None
    baseline = BaselineStore(baseline_dir(DATA)).current(presale) if presale else None
    print(f"Reunión: {document.metadata.source_name} ({options.reunion}) · {document.metadata.source_date} · huella {document.fingerprint} · {catalog.source_status(options.reunion, document.fingerprint)}")
    print(f"Línea base: {len(baseline.commitments) if baseline else 'sin extraer'} compromisos · requisitos en el catálogo: {len(catalog.requirements())}")

    models = load_models_config(ROOT / "config" / "models.yaml")
    enum_spec, class_spec = models.for_role(AgentRole.REQUERIMIENTOS), models.for_role(AgentRole.AUDITOR)
    pricing = load_pricing()
    estimate = estimate_ingest(document, baseline, enum_spec.model, class_spec.model, pricing)
    cost = f"~US$ {estimate['cost_usd']:.2f}" if estimate["cost_usd"] is not None else "sin precio configurado"
    print(f"Enumera {enum_spec.model} y clasifica {class_spec.model}: ~{estimate['candidates']} candidatos, ~{estimate['calls']} llamadas, ~{estimate['input_tokens']:,} tokens de entrada y ~{estimate['output_tokens']:,} de salida, {cost} (estimación).")
    if not options.confirmar:
        print("No se ejecutó nada. Agregá --confirmar para leer la reunión.")
        return 0
    settings = Settings.from_env(ROOT / ".env")
    try:
        result = ingest_meeting(
            document, catalog=catalog, enumerator=build_provider(enum_spec, settings), classifier=build_provider(class_spec, settings),
            confirmed=True, baseline=baseline, presale=presale, pricing=pricing,
        )
    except IngestNeedsRealModel as exc:
        print(exc)
        return 1
    if result.skipped:
        print("Esta reunión ya se procesó con esta huella: no se gastó nada.")
        return 0
    print(f"\n{len(result.candidates)} candidatos verificados, {len(result.rejected)} descartados, {len(result.proposals)} propuestas, {len(result.auto_applied)} «ya cubierto» aplicados{' · REUNIÓN FUERA DE ORDEN' if result.out_of_order else ''}.")
    for r in result.rejected:
        print(f"   ✘ descartado: {r.text} — {r.reason}")
    show_proposals(catalog, options.reunion)
    real = f"~US$ {result.cost_usd:.3f}" if result.cost_usd is not None else "sin precio"
    print(f"\nGastó {result.input_tokens:,} tokens de entrada y {result.output_tokens:,} de salida ({real}). Guardado en data/catalogo.sqlite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
