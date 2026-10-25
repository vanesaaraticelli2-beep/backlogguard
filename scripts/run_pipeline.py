"""Corre el sistema completo y deja ver a los agentes trabajar en vivo.

Recorre: Supervisor → Requerimientos → Crítico → Auditor → pedidos de decisión → plan de publicación.
La corrida SE PAUSA cuando necesita a una persona (como hará la pantalla); se retoma con
`scripts/decidir.py`. El backlog de Azure DevOps es simulado y persiste en `data/` entre corridas.

    # corrida con modelos reales (gasta tokens; ver config/models.yaml)
    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\run_pipeline.py --reset --seed

Opciones:
  --reset   vacía el backlog simulado, su registro de publicaciones y la memoria de decisiones.
  --seed    carga work items "manuales" de ejemplo (sirven para ver un posible duplicado).
  --auto    decide todo aprobando, como la persona que corresponde a cada pedido (para una demo sin interacción).
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from backlogguard.board import Board
from backlogguard.graph import load_state, pending_request, resume_pipeline, run_pipeline
from backlogguard.graph.live import format_event
from backlogguard.graph.setup import build_run_deps, open_graph
from backlogguard.llm import Settings

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OBJECTIVE = "Armá el backlog a partir de las reuniones y auditalo contra la preventa."


def show_backlog(backlog, title: str) -> None:
    items = backlog.search()
    print(f"\n{title}: {len(items)} work items")
    for work_item in items:
        parent = f" (hijo de #{work_item.parent_id})" if work_item.parent_id else ""
        origin = "BacklogGuard" if any(t.startswith("bg-item:") for t in work_item.tags) else "manual"
        print(f"  #{work_item.id} [{work_item.type}] {work_item.title}{parent} · v{work_item.rev} · {origin}")


def show_request(request: dict) -> None:
    print(f"\n⏸  PEDIDO {request['request_id']} v{request['version']} — decide: {request['decides']}")
    print(f"   {request['title']}")
    for line in request["summary"].splitlines():
        print(f"   {line}")
    for evidence in request["evidence"]:
        print(f"   · «{evidence['quote']}» — {evidence['source_name']}, {evidence['source_date']}, {evidence['speaker']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--auto", action="store_true")
    options = parser.parse_args()

    settings = Settings.from_env(ROOT / ".env")
    deps = build_run_deps(ROOT, settings, on_event=lambda event: (line := format_event(event)) and print(line, flush=True))
    if options.reset:
        deps.backlog.reset()
        for name in ("publicaciones.sqlite", "memoria.sqlite"):
            (DATA / name).unlink(missing_ok=True)
        deps = build_run_deps(ROOT, settings, on_event=deps.on_event)
    if options.seed and not deps.backlog.search():
        deps.backlog.seed_demo()
    graph = open_graph(deps, DATA)

    thread_id = f"corrida-{uuid.uuid4().hex[:8]}"
    print(f"live={settings.live_mode} proyecto={settings.azdo_project} corrida={thread_id}")
    show_backlog(deps.backlog, "Backlog simulado antes")
    state = run_pipeline(graph, OBJECTIVE, thread_id)

    while (payload := pending_request(graph, thread_id)) is not None:
        show_request(payload["request"])
        if not options.auto:
            print(f"\nLa corrida espera una decisión. Retomala con:\n  .venv\\Scripts\\python scripts\\decidir.py {thread_id}")
            break
        request = payload["request"]
        person = deps.people.with_role(request["decides"])[0]
        print(f"   [auto] {person.display} aprueba")
        state = resume_pipeline(graph, thread_id, {
            "decision": "approve", "actor": person.name, "actor_role": person.role, "request_id": request["request_id"],
            "request_version": request["version"], "args_hash": request["args_hash"], "comment": "Aprobado en la demo automática.",
        })

    state = load_state(graph, thread_id)
    board = Board.model_validate(state["board"])
    print("\n" + "=" * 70)
    print(f"ESTADO: {state['status']} · tokens={state['tokens']} · corte={state.get('stop_reason')}")
    for item in board.items.values():
        print(f"- {item.id} [{item.state.value}] {item.title}")
    for error in state["errors"]:
        print(f"x error en {error['node']} ({error['ref']}): {error['error'][:140]}")
    for record in state.get("decisions", []):
        mark = "✔" if record["accepted"] else "✘"
        print(f"{mark} {record['actor']} ({record['actor_role']}) {record['decision']} {record['request_id']} v{record['version']}")
    if state.get("publication"):
        for result in state["publication"]["results"]:
            print(f"  {result['outcome']:12} {result['item_id']} → #{result['remote_id']}")
    if state.get("summary"):
        print("\nResumen del Supervisor:\n" + state["summary"])
    show_backlog(deps.backlog, "Backlog simulado después")
    graph.checkpointer.conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
