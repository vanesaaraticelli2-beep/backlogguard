r"""Compara al Crítico con y sin expediente precalculado, sobre los mismos ítems sembrados con errores.

Con LIVE_MODE=1 llama al modelo real del Crítico (cuesta unos centavos por ítem y modo); con LIVE_MODE=0 solo
valida el cableado. Muestra veredicto, tokens de entrada/salida, pasos y costo estimado de cada modo.

    $env:LIVE_MODE = "1"; .venvScriptspython scriptsmparar_expediente.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from run_critico import ROOT, seed

from backlogguard.agents.critico import review_item
from backlogguard.board import AgentRole
from backlogguard.llm import InvalidProviderResponseError, Settings, build_provider, load_models_config
from backlogguard.llm.metering import Meter, MeteredProvider, estimate_cost, load_pricing
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary, build_chunks


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.CRITICO)
    pricing = load_pricing()
    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    library = SourceLibrary(ROOT / "evals" / "fixtures")
    for document_id in library.list_ids():
        retriever.index(build_chunks(document_id, library.load(document_id).text, library.load(document_id).metadata.model_dump(mode="json")))
    board = seed(retriever)
    print(f"modelo={spec.model} effort={spec.effort} live={settings.live_mode}")

    verdicts: dict[str, dict[bool, str]] = {item_id: {} for item_id in board.items}
    totals = {}
    for precompute in (False, True):
        meter = Meter()
        provider = MeteredProvider(build_provider(spec, settings), meter)
        for item_id in board.items:
            before = meter.mark()
            try:
                review = review_item(item_id, provider=provider, retriever=retriever, board=board, max_seconds=300.0, precompute=precompute)
                verdicts[item_id][precompute] = review.verdict.verdict
            except InvalidProviderResponseError as exc:
                verdicts[item_id][precompute] = f"sin veredicto ({exc})"
            used = meter.since(before)
            print(f"  {'CON' if precompute else 'SIN'} expediente · {item_id:8} {verdicts[item_id][precompute]:10} "
                  f"llamadas={used.calls} entrada={used.input_tokens} salida={used.output_tokens}")
        cost = estimate_cost(spec.model, meter.input_tokens, meter.output_tokens, pricing)
        totals[precompute] = (meter.calls, meter.input_tokens, meter.output_tokens, cost)

    print("\nResumen")
    for precompute, (calls, tin, tout, cost) in totals.items():
        price = f"~US$ {cost:.3f}" if cost is not None else "sin precio"
        print(f"  {'CON' if precompute else 'SIN'} expediente: {calls} llamadas, {tin} tokens de entrada, {tout} de salida, {price}")
    same = [item_id for item_id, v in verdicts.items() if v.get(False) == v.get(True)]
    print(f"Mismo veredicto en {len(same)} de {len(verdicts)} ítems" + ("" if len(same) == len(verdicts) else f"; difieren: {sorted(set(verdicts) - set(same))}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
