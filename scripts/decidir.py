"""Decide el pedido en el que está pausada una corrida (aprobar, editar o rechazar).

    # ver qué espera la corrida
    .venv\\Scripts\\python scripts\\decidir.py corrida-1a2b3c4d

    # decidir como la persona que corresponde (o indicá --como)
    .venv\\Scripts\\python scripts\\decidir.py corrida-1a2b3c4d --accion approve --comentario "De acuerdo"
    .venv\\Scripts\\python scripts\\decidir.py corrida-1a2b3c4d --accion edit --editar decision_text="Evaluar la app aparte"
    .venv\\Scripts\\python scripts\\decidir.py corrida-1a2b3c4d --accion edit --editar exclude=HU-1,HU-2

La decisión lleva la versión y el hash del pedido que se muestra: si el contenido cambió, se rechaza.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backlogguard.graph import load_state, pending_request, resume_pipeline
from backlogguard.graph.live import format_event
from backlogguard.graph.setup import build_run_deps, open_graph
from backlogguard.llm import Settings

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def parse_edits(pairs: list[str]) -> dict:
    edited: dict = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key == "exclude":
            edited[key] = [part for part in value.split(",") if part]
        elif key == "acceptance_criteria":
            edited[key] = [part.strip() for part in value.split("|") if part.strip()]
        else:
            edited[key] = value
    return edited


def show(payload: dict) -> None:
    request = payload["request"]
    print(f"PEDIDO {request['request_id']} v{request['version']} (hash {request['args_hash']}) — decide: {request['decides']}")
    print(request["title"])
    print(request["summary"])
    for evidence in request["evidence"]:
        print(f"  · «{evidence['quote']}» — {evidence['source_name']}, {evidence['source_date']}, {evidence['speaker']}")
    print(f"Editable: {request['editable']}  ·  contenido actual: {json.dumps(request['payload'], ensure_ascii=False)[:300]}")
    if payload.get("last_error"):
        print(f"\n⚠ La última decisión se rechazó: {payload['last_error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corrida")
    parser.add_argument("--accion", choices=["approve", "edit", "reject"])
    parser.add_argument("--como", help="rol con el que decidís (por defecto, el rol que decide el pedido)")
    parser.add_argument("--comentario", default="")
    parser.add_argument("--editar", action="append", default=[], metavar="CAMPO=VALOR")
    options = parser.parse_args()

    settings = Settings.from_env(ROOT / ".env")
    deps = build_run_deps(ROOT, settings, on_event=lambda event: (line := format_event(event)) and print(line, flush=True))
    graph = open_graph(deps, DATA)
    payload = pending_request(graph, options.corrida)
    if payload is None:
        state = load_state(graph, options.corrida)
        print(f"La corrida no espera ninguna decisión (estado: {state.get('status', 'desconocida')}).")
        return 0
    show(payload)
    if options.accion is None:
        return 0

    request = payload["request"]
    person = deps.people.get(options.como) if options.como else (deps.people.with_role(request["decides"]) or [None])[0]
    if person is None:
        print(f"No hay una persona para decidir como '{options.como or request['decides']}'.")
        return 1
    print(f"\n{person.display} decide: {options.accion}")
    resume_pipeline(graph, options.corrida, {
        "decision": options.accion, "actor": person.name, "actor_role": person.role, "request_id": request["request_id"],
        "request_version": request["version"], "args_hash": request["args_hash"],
        "edited": parse_edits(options.editar) or None, "comment": options.comentario,
    })
    following = pending_request(graph, options.corrida)
    print("\n" + "-" * 60)
    if following is None:
        state = load_state(graph, options.corrida)
        print(f"Corrida terminada: {state['status']}")
        if state.get("summary"):
            print(state["summary"])
    else:
        show(following)
    graph.checkpointer.conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
