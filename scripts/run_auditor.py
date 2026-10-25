"""Corre al Auditor sobre el corpus sintético y un ítem desactualizado, sin pasar por el productor.

Con LIVE_MODE=0 usa el proveedor falso (solo valida el cableado). Con LIVE_MODE=1 usa el modelo de
config/models.yaml para el rol Auditor (no consume la cuota de Gemini). La memoria es temporal.

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_auditor.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from backlogguard.agents.auditor import apply_report, run_auditor
from backlogguard.agents.auditor.entrega import deliver_corrections, who_decides
from backlogguard.board import AgentRole, BacklogItem, Board, Citation
from backlogguard.llm import InvalidProviderResponseError, Settings, build_provider, load_models_config
from backlogguard.memory import ProjectMemory
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary, build_chunks
from backlogguard.tools import load_policy_config

ROOT = Path(__file__).resolve().parents[1]
GHERKIN = "Dado un cliente con sesión Cuando exporta el reporte mensual Entonces descarga el archivo del mes"


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.AUDITOR)
    provider = build_provider(spec, settings)

    retriever = InMemoryRetriever(DeterministicLexicalEmbeddings())
    library = SourceLibrary(ROOT / "evals" / "fixtures")
    for document_id in library.list_ids():
        document = library.load(document_id)
        retriever.index(build_chunks(document_id, document.text, document.metadata.model_dump(mode="json")))

    # Un ítem sustentado que quedó con la versión vieja (PDF) para que el Auditor lo detecte.
    kickoff = next(c for c in retriever.all_chunks({"document_id": "reunion_01_kickoff"}) if "reporte mensual" in c.text)
    board = Board()
    board.add_item(
        BacklogItem(
            id="HU-PDF",
            kind="historia",
            title="Reporte mensual en PDF",
            description="Como cliente quiero un reporte mensual en PDF para presentarlo en el comité.",
            acceptance_criteria=[GHERKIN],
            citations=[
                Citation(
                    fragment_id=kickoff.chunk_id,
                    quote=kickoff.text,
                    source_name=kickoff.metadata["source_name"],
                    source_type=kickoff.metadata["source_type"],
                    source_date=kickoff.metadata["source_date"],
                    speaker=kickoff.metadata["speaker"],
                )
            ],
            state="sustentado",
        )
    )

    print(f"modelo={spec.model} effort={spec.effort} live={settings.live_mode}")
    with tempfile.TemporaryDirectory() as tmp:
        memory = ProjectMemory(Path(tmp) / "memoria.sqlite", "acme")
        try:
            run = run_auditor(provider=provider, retriever=retriever, board=board, memory=memory)
        except InvalidProviderResponseError as exc:
            print(f"sin informe: {exc}")
            return 1

    result = apply_report(run.report, board, retriever)
    policy = load_policy_config(ROOT / "config" / "policy.yaml")
    print(f"tokens={run.tokens} hallazgos={len(result.applied)} descartados={len(result.discarded)}")
    for finding in result.applied:
        corrects = finding.addressee is AgentRole.REQUERIMIENTOS
        decides = "el productor corrige" if corrects else (who_decides(finding, policy) or "informativo")
        print(f"- [{finding.kind.value}] -> {finding.addressee.value} ({decides}) item={finding.item_id}")
        print(f"    {finding.description}")
        for citation in finding.citations:
            print(f"    «{citation.quote}» — {citation.source_name}, {citation.speaker}")
    for draft, reason in result.discarded:
        print(f"- DESCARTADO [{draft.kind.value}]: {reason}")
    for message in deliver_corrections(board, result.applied):
        print(f"mensaje {message.sender.value} -> {message.recipient.value}: {message.content[:200]}")
    print(f"HU-PDF queda {board.items['HU-PDF'].state.value}")
    print("resumen:", run.report.summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
