"""Corre el Agente de Requerimientos sobre el corpus sintético de `evals/fixtures`.

Con LIVE_MODE=0 usa el proveedor falso (no produce ítems útiles: solo valida el cableado).
Con LIVE_MODE=1 usa el modelo de config/models.yaml para este rol.

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_requerimientos.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from backlogguard.agents.requerimientos import run_requerimientos
from backlogguard.board import AgentRole, Board
from backlogguard.llm import Settings, build_provider, load_models_config
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary

ROOT = Path(__file__).resolve().parents[1]
GOAL = (
    "Armá el backlog del portal de autoservicio de ACME. Indexá las fuentes reunion_01_kickoff, "
    "reunion_02_seguimiento y reunion_03_refinamiento; la preventa_acme no la uses para redactar. "
    "Creá una historia por cada requerimiento que pidió el cliente."
)


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    spec = load_models_config(ROOT / "config" / "models.yaml").for_role(AgentRole.REQUERIMIENTOS)
    board = Board()
    outcome = run_requerimientos(
        GOAL,
        provider=build_provider(spec, settings),
        library=SourceLibrary(ROOT / "evals" / "fixtures"),
        retriever=InMemoryRetriever(DeterministicLexicalEmbeddings()),
        board=board,
        max_seconds=600.0,
    )
    print(f"modelo={spec.model} live={settings.live_mode} stop={outcome['stop_reason']} tokens={outcome['tokens']}")
    for event in outcome["trace"]:
        if event["event"] == "observation":
            print(f"  paso {event['step']}: {event['tool']} -> ok={event['observation']['ok']}")
        elif event["event"] == "llm_error":
            print(f"  paso {event['step']}: {event['error']}")
    for item in board.items.values():
        print(f"- {item.id} [{item.state.value}] {item.title} ({len(item.citations)} citas)")
        for citation in item.citations:
            print(f"    «{citation.quote}» — {citation.source_name}, {citation.speaker}")
    print("respuesta final:", json.dumps(outcome["answer"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
