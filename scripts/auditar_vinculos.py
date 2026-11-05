r"""Verifica los vínculos de los requisitos (y propuestas pendientes) con los compromisos de la preventa y propone corregirlos.

    .venv\Scripts\python scripts\auditar_vinculos.py                 # muestra cuántos pares se verificarían y el gasto estimado
    .venv\Scripts\python scripts\auditar_vinculos.py --confirmar     # verifica con el modelo y guarda el informe (no cambia nada)
    .venv\Scripts\python scripts\auditar_vinculos.py --aplicar       # aplica las correcciones del último informe (no vuelve a llamar al modelo)

Usa la carpeta de datos de BACKLOGGUARD_DATA (por defecto `data/`). Solo cambia a qué compromisos está ligado cada requisito:
el texto de los requisitos no se toca. Necesita LIVE_MODE=1 para verificar.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from backlogguard.board import AgentRole, SourceType
from backlogguard.catalog import Catalog
from backlogguard.catalog import links as audit_links
from backlogguard.catalog.ingest import LINK_BATCH
from backlogguard.graph.setup import baseline_dir, user_sources_dir
from backlogguard.llm import Settings, build_provider, load_models_config
from backlogguard.llm.metering import Meter, MeteredProvider, estimate_cost, load_pricing
from backlogguard.rag import SourceLibrary
from backlogguard.rag.compromisos import BaselineStore, is_real

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("BACKLOGGUARD_DATA") or ROOT / "data").resolve()
SAVED = ROOT / "evals" / "real" / "auditoria_vinculos.json"
REPORT = ROOT / "evals" / "real" / "auditoria_vinculos.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--confirmar", action="store_true", help="confirmo el gasto y quiero verificar con el modelo")
    parser.add_argument("--aplicar", action="store_true", help="aplica las correcciones del último informe")
    parser.add_argument("--conservar", help="con --aplicar: vínculos que el modelo juzgó «distinto» y se conservan, como RQ-002:C-262,RQ-003:C-262")
    parser.add_argument("--descartar", help="con --aplicar: vínculos que el modelo juzgó «mismo» y se descartan, como RQ-004:C-014")
    parser.add_argument("--solo", choices=["requisitos", "propuestas"], help="limita a los requisitos aprobados o a las propuestas pendientes")
    options = parser.parse_args()

    catalog = Catalog(DATA / "catalogo.sqlite")
    if options.aplicar:
        if not SAVED.exists():
            print("No hay un informe previo: corré primero con --confirmar.")
            return 1
        try:
            reviewed = audit_links.override(
                audit_links.load(SAVED), keep=audit_links.parse_pairs(options.conservar), drop=audit_links.parse_pairs(options.descartar)
            )
        except ValueError as exc:
            print(exc)
            return 1
        done = audit_links.apply(catalog, reviewed)
        for target, ids in done.items():
            print(f"  {target}: queda ligado a {ids or 'ningún compromiso (no fue vendido)'}")
        print(f"\nCorregidos {len(done)}. El texto de los requisitos no cambió.")
        return 0

    library = SourceLibrary(user_sources_dir(DATA))
    presales = [i for i, m in library.describe() if m.source_type is SourceType.PREVENTA] if library.root.is_dir() else []
    baseline = BaselineStore(baseline_dir(DATA)).current(library.load(presales[0])) if len(presales) == 1 else None
    if baseline is None:
        print("Hace falta una preventa con sus compromisos extraídos y vigentes.")
        return 1
    pairs = audit_links.collect(catalog, baseline, requirements=options.solo != "propuestas", proposals=options.solo != "requisitos")
    todo = [p for _, p in pairs if p is not None]
    calls = -(-len(todo) // LINK_BATCH)
    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.AUDITOR)
    est_in, est_out = len(todo) * 220 + calls * 500, len(todo) * 70
    cost = estimate_cost(spec.model, est_in, est_out, load_pricing())
    print(f"{len(pairs)} vínculos ({len(todo)} a verificar con {spec.model}): ~{calls} llamada(s), ~{est_in:,} tokens de entrada y ~{est_out:,} de salida"
          + (f", ~US$ {cost:.2f}" if cost is not None else "") + ".")
    if not options.confirmar:
        print("Para verificar, agregá --confirmar.")
        return 0
    if not settings.live_mode:
        print("Verificar necesita modelos reales: LIVE_MODE=1.")
        return 1
    provider = build_provider(spec, settings)
    if not is_real(provider):
        print("El modelo no es real.")
        return 1
    meter = Meter()
    links = audit_links.audit(MeteredProvider(provider, meter), pairs)
    audit_links.save(links, SAVED)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(audit_links.report(links), encoding="utf-8")
    real = estimate_cost(spec.model, meter.input_tokens, meter.output_tokens, load_pricing())
    print(f"Listo: {meter.calls} llamada(s), {meter.input_tokens:,} → {meter.output_tokens:,} tokens" + (f", ~US$ {real:.3f}" if real is not None else "") + ".")
    print(audit_links.report(links))
    print(f"Informe en {REPORT}. Para aplicar las correcciones: --aplicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
