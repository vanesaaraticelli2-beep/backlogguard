"""Graba una corrida real para poder reproducirla después sin modelos, sin red y sin costo.

Corre el sistema completo con los modelos de config/models.yaml (LIVE_MODE=1), aprueba cada pedido como la
persona que corresponde y guarda las respuestas de cada modelo en `evals/recordings/demo_acme.json`.
La pantalla (`streamlit run src/backlogguard/ui/app.py`) la reproduce con LIVE_MODE=0.

    $env:LIVE_MODE = "1"; .venv\\Scripts\\python scripts\\grabar_demo.py

Usa un backlog simulado propio y temporal con los mismos work items de ejemplo que la pantalla, así que no
toca `data/`. Gasta tokens reales (unos US$1).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from backlogguard.graph import build_providers, load_state, pending_request, resume_pipeline, run_pipeline
from backlogguard.graph.live import format_event
from backlogguard.graph.setup import build_run_deps, open_graph
from backlogguard.llm import Settings, load_models_config
from backlogguard.llm.recording import Recording, recording_providers
from backlogguard.ui.controller import DEFAULT_OBJECTIVE

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evals" / "recordings" / "demo_acme.json"


def main() -> int:
    settings = Settings.from_env(ROOT / ".env")
    if not settings.live_mode:
        print("Grabar necesita modelos reales: activá LIVE_MODE=1 (y las claves en .env).")
        return 1
    recording = Recording(objective=DEFAULT_OBJECTIVE)
    providers = recording_providers(build_providers(load_models_config(ROOT / "config" / "models.yaml"), settings), recording)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        data = Path(tmp)
        deps = build_run_deps(ROOT, settings, data_dir=data, providers=providers, on_event=lambda e: (line := format_event(e)) and print(line, flush=True))
        deps.backlog.seed_demo()
        graph = open_graph(deps, data)
        thread_id = "grabacion"
        run_pipeline(graph, DEFAULT_OBJECTIVE, thread_id)
        while (payload := pending_request(graph, thread_id)) is not None:
            request = payload["request"]
            person = deps.people.with_role(request["decides"])[0]
            print(f"\n[decisión] {person.display} aprueba «{request['title'][:70]}»")
            resume_pipeline(graph, thread_id, {
                "decision": "approve", "actor": person.name, "actor_role": person.role, "request_id": request["request_id"],
                "request_version": request["version"], "args_hash": request["args_hash"], "comment": "Aprobado durante la grabación.",
            })
        state = load_state(graph, thread_id)
        graph.checkpointer.conn.close()
    recording.save(OUTPUT)
    counts = {role: len(texts) for role, texts in recording.responses.items()}
    print(f"\nEstado final: {state['status']} · tokens={state['tokens']}")
    print(f"Grabación guardada en {OUTPUT.relative_to(ROOT)}: respuestas por agente {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
