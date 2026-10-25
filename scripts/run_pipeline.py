"""Corre el grafo completo (Supervisor, productor, Crítico, Auditor) sobre el corpus sintético.

Con LIVE_MODE=0 usa proveedores falsos (solo valida el cableado). Con LIVE_MODE=1 usa los modelos de
config/models.yaml y gasta tokens reales (unos US$1 con los modelos actuales).

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_pipeline.py
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from pathlib import Path

from backlogguard.board import Board
from backlogguard.graph import (
    RunDeps,
    build_graph,
    build_providers,
    load_budget,
    run_pipeline,
    sqlite_checkpointer,
)
from backlogguard.llm import Settings, load_models_config
from backlogguard.memory import ProjectMemory
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary
from backlogguard.tools import load_policy_config

ROOT = Path(__file__).resolve().parents[1]
OBJECTIVE = "Armá el backlog del portal de autoservicio de ACME a partir de las reuniones y auditalo contra la preventa."


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    models = load_models_config(ROOT / "config" / "models.yaml")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        deps = RunDeps(
            providers=build_providers(models, settings),
            library=SourceLibrary(ROOT / "evals" / "fixtures"),
            retriever=InMemoryRetriever(DeterministicLexicalEmbeddings()),
            memory=ProjectMemory(Path(tmp) / "memoria.sqlite", "acme"),
            policy=load_policy_config(ROOT / "config" / "policy.yaml"),
            budget=load_budget(ROOT / "config" / "budgets.yaml"),
        )
        graph = build_graph(deps, sqlite_checkpointer(Path(tmp) / "corrida.sqlite"))
        thread_id = f"corrida-{uuid.uuid4().hex[:8]}"
        print(f"live={settings.live_mode} thread={thread_id}")
        state = run_pipeline(graph, OBJECTIVE, thread_id)
        graph.checkpointer.conn.close()

    board = Board.model_validate(state["board"])
    print(f"estado={state['status']} corte={state.get('stop_reason')} tokens={state['tokens']}")
    print("recorrido:", " → ".join(event["node"] for event in state["trace"]))
    plan = state.get("plan", {})
    print(f"plan: fuentes={plan.get('sources')} por_defecto={plan.get('used_default')}")
    for item in board.items.values():
        outcome = state["reviewed"].get(item.id, {})
        print(f"- {item.id} [{item.state.value}] {item.title} (revisión: {outcome.get('outcome', '-')}, rondas: {outcome.get('rounds', '-')})")
    for finding in board.findings:
        print(f"* hallazgo {finding.id} [{finding.kind.value}] → {finding.addressee.value}: {finding.description[:110]}")
    for escalation in state["escalations"]:
        print(f"! escalación {escalation['id']}: {escalation['reason']} → decide {escalation['decides']} ({escalation['ref']})")
    for error in state["errors"]:
        print(f"x error en {error['node']} ({error['ref']}): {error['error'][:140]}")
    print("resumen:", state.get("summary"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
