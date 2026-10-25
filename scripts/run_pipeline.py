"""Corre el sistema completo y deja ver a los agentes trabajar en vivo.

Recorre: Supervisor → Requerimientos → Crítico → Auditor → escalaciones → plan de publicación.
El backlog de Azure DevOps es simulado y persiste en `data/` entre corridas.

    # corrida con modelos reales (gasta tokens; ver config/models.yaml)
    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_pipeline.py --reset --seed

Opciones:
  --reset         vacía el backlog simulado y su registro de publicaciones antes de empezar.
  --seed          carga work items "manuales" de ejemplo (sirven para ver un posible duplicado).
  --aprobar NOMBRE  simula la aprobación humana: pasa los ítems a aprobados y publica el plan.
                  (La pausa real con pantalla llega con el Human-in-the-Loop.)
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from backlogguard.agents.integracion import execute_approved_plan
from backlogguard.board import Board, ItemState
from backlogguard.graph import RunDeps, build_graph, build_providers, load_budget, run_pipeline, sqlite_checkpointer
from backlogguard.graph.live import format_event
from backlogguard.integrations import PublicationLedger, PublishService, SimulatedBacklog
from backlogguard.llm import Settings, load_models_config
from backlogguard.memory import ProjectMemory
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary
from backlogguard.tools import load_policy_config

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OBJECTIVE = "Armá el backlog del portal de autoservicio de ACME a partir de las reuniones y auditalo contra la preventa."


def show_backlog(backlog: SimulatedBacklog, title: str) -> None:
    items = backlog.search()
    print(f"\n{title}: {len(items)} work items")
    for work_item in items:
        parent = f" (hijo de #{work_item.parent_id})" if work_item.parent_id else ""
        origin = "BacklogGuard" if any(t.startswith("bg-item:") for t in work_item.tags) else "manual"
        print(f"  #{work_item.id} [{work_item.type}] {work_item.title}{parent} · v{work_item.rev} · {origin}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--aprobar", metavar="NOMBRE")
    options = parser.parse_args()

    settings = Settings.from_env(ROOT / ".env")
    models = load_models_config(ROOT / "config" / "models.yaml")
    DATA.mkdir(exist_ok=True)
    backlog = SimulatedBacklog(DATA / "backlog_simulado.json")
    if options.reset:
        backlog.reset()
        (DATA / "publicaciones.sqlite").unlink(missing_ok=True)
    if options.seed and not backlog.search():
        backlog.seed_demo()

    deps = RunDeps(
        providers=build_providers(models, settings),
        library=SourceLibrary(ROOT / "evals" / "fixtures"),
        retriever=InMemoryRetriever(DeterministicLexicalEmbeddings()),
        memory=ProjectMemory(DATA / "memoria.sqlite", settings.azdo_project.lower()),
        policy=load_policy_config(ROOT / "config" / "policy.yaml"),
        budget=load_budget(ROOT / "config" / "budgets.yaml"),
        backlog=backlog,
        ledger=PublicationLedger(DATA / "publicaciones.sqlite"),
        project=settings.azdo_project,
        on_event=lambda event: (line := format_event(event)) and print(line, flush=True),
    )
    graph = build_graph(deps, sqlite_checkpointer(DATA / "corridas.sqlite"))
    thread_id = f"corrida-{uuid.uuid4().hex[:8]}"
    print(f"live={settings.live_mode} proyecto={settings.azdo_project} corrida={thread_id}")
    show_backlog(backlog, "Backlog simulado antes")
    state = run_pipeline(graph, OBJECTIVE, thread_id)

    board = Board.model_validate(state["board"])
    print("\n" + "=" * 70)
    print(f"ESTADO: {state['status']} · tokens={state['tokens']} · corte={state.get('stop_reason')}")
    for item in board.items.values():
        outcome = state["reviewed"].get(item.id, {})
        print(f"- {item.id} [{item.state.value}] {item.title} (rondas: {outcome.get('rounds', '-')})")
    for escalation in state["escalations"]:
        print(f"! escalación → {escalation['decides']}: {escalation['reason']} ({escalation['ref']})")
    for error in state["errors"]:
        print(f"x error en {error['node']} ({error['ref']}): {error['error'][:140]}")
    plan = state.get("publish_plan")
    if plan:
        print(f"\nPLAN DE PUBLICACIÓN {plan['hash']} (pendiente de aprobación): {plan['counts']}")
        for entry in plan["items"]:
            print(f"  {entry['action'].upper():10} {entry['title']}  — {entry['reason']}")
    print("\nResumen del Supervisor:\n" + state.get("summary", ""))

    if options.aprobar and plan and plan["has_changes"]:
        print(f"\n[simulación] {options.aprobar} aprueba el plan {plan['hash']}")
        for item in board.items.values():
            if item.state is ItemState.SUSTENTADO:
                item.transition_to(ItemState.APROBADO, actor=options.aprobar)
        service = PublishService(board, backlog, deps.ledger, deps.project)
        report = execute_approved_plan(plan["hash"], service=service, approved_by=options.aprobar, run_id=thread_id)
        for result in report.results:
            print(f"  {result.outcome:12} {result.item_id} → #{result.remote_id} {result.detail}")
        print("Publicación OK" if report.ok else f"Publicación detenida: {report.error}")
    show_backlog(backlog, "Backlog simulado después")
    graph.checkpointer.conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
