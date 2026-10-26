"""Corre el sistema completo con tus fuentes propias (`data/fuentes/`), igual que la pantalla, y lo muestra en vivo.

Usa el mismo controlador que la pantalla de Streamlit, así que el recorrido es idéntico: los agentes trabajan,
la corrida se pausa en cada pedido de decisión y acá cada pedido lo aprueba el rol que corresponde (`--auto`) o
queda esperando (sin `--auto`).

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\correr_con_mis_fuentes.py --auto

Gasta tokens reales (tope por corrida en config/budgets.yaml). Reinicia el backlog simulado, las decisiones y las
publicaciones antes de empezar; no toca tus fuentes.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from backlogguard.board import Board
from backlogguard.llm import Settings
from backlogguard.ui.controller import DEFAULT_OBJECTIVE, RunController

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def drain(controller: RunController, shown: int) -> int:
    lines = controller.activity(limit=100_000)
    for line in lines[shown:]:
        print(line, flush=True)
    return len(lines)


def wait_printing(controller: RunController, shown: int) -> int:
    while controller.running:
        shown = drain(controller, shown)
        time.sleep(1.0)
    return drain(controller, shown)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--objetivo", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--auto", action="store_true", help="aprueba cada pedido con el rol que corresponde")
    options = parser.parse_args()

    settings = Settings.from_env(ROOT / ".env")
    controller = RunController(ROOT, settings, DATA)
    if not controller.using_own_sources:
        print("No hay fuentes propias en data/fuentes/ (hace falta una preventa y una reunión). Usá scripts/importar_fuentes.py.")
        return 1
    if controller.mode != "real":
        print("Con fuentes propias hace falta LIVE_MODE=1.")
        return 1
    print(f"Fuentes: {[(i, m.source_type.value, m.source_date.isoformat()) for i, m in controller.deps.library.describe()]}")
    print(f"Objetivo: {options.objetivo}\nTope de tokens: {controller.deps.budget.max_tokens:,}\n")

    started = time.time()
    thread_id = controller.start(options.objetivo)
    print(f"corrida={thread_id}")
    shown = wait_printing(controller, 0)
    while (payload := controller.pending()) is not None:
        request = payload["request"]
        role = request["decides"]
        print(f"\n⏸  PEDIDO {request['request_id']} v{request['version']} — decide: {role}\n   {request['title']}")
        for line in request["summary"].splitlines():
            print(f"   {line}")
        for evidence in request["evidence"]:
            where = f", p. {evidence['page']}" if evidence.get("page") else ""
            print(f"   · «{evidence['quote'][:160]}» — {evidence['source_name']}{where}, {evidence.get('speaker') or 's/d'}")
        if not options.auto:
            print("\nLa corrida queda esperando una decisión.")
            return 0
        print(f"   [auto] {role} aprueba")
        controller.decide({
            "decision": "approve", "actor": role, "actor_role": role, "request_id": request["request_id"],
            "request_version": request["version"], "args_hash": request["args_hash"], "comment": "Aprobado en la prueba automática.",
        })
        shown = wait_printing(controller, shown)

    state = controller.state()
    board = Board.model_validate(state["board"])
    print("\n" + "=" * 78)
    print(f"ESTADO: {state['status']} · tokens={state['tokens']:,} · {time.time() - started:.0f} s · error={controller.error}")
    for item in board.items.values():
        outcome = state["reviewed"].get(item.id, {})
        print(f"- {item.id} [{item.state.value}] {item.title}  (revisión: {outcome.get('outcome', '-')}, rondas: {outcome.get('rounds', '-')})")
    print(f"\nHallazgos del Auditor: {len(board.findings)}")
    for finding in board.findings:
        print(f"  [{finding.kind.value}] → {finding.addressee.value}: {finding.description[:200]}")
    for error in state.get("errors", []):
        print(f"x error en {error['node']} ({error['ref']}): {error['error'][:200]}")
    print("\nPLAN DE PUBLICACIÓN:", state.get("publish_plan", {}).get("counts"))
    for result in (state.get("publication") or {}).get("results", []):
        print(f"  {result['outcome']:12} {result['item_id']} → #{result['remote_id']} {result['detail']}")
    print("\nRESUMEN DEL SUPERVISOR:\n" + (state.get("summary") or ""))
    print("\nBACKLOG SIMULADO (ahora):")
    for work_item in controller.deps.backlog.search():
        parent = f" (hijo de #{work_item.parent_id})" if work_item.parent_id else ""
        print(f"  #{work_item.id} [{work_item.type}] {work_item.title}{parent}")
    controller.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
