"""Arma las dependencias de una corrida a partir de la configuración del proyecto.

Lo comparten los scripts y la pantalla, para que todos abran el mismo backlog simulado, la misma memoria
y el mismo archivo de checkpoints dentro de `data/`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from backlogguard.graph.budgets import load_budget
from backlogguard.graph.builder import build_graph, sqlite_checkpointer
from backlogguard.graph.deps import Providers, RunDeps, build_providers
from backlogguard.hitl import load_people
from backlogguard.integrations import PublicationLedger, SimulatedBacklog
from backlogguard.llm import Settings, load_models_config
from backlogguard.llm.recording import Recording, replay_providers
from backlogguard.memory import ProjectMemory
from backlogguard.rag import DeterministicLexicalEmbeddings, InMemoryRetriever, SourceLibrary
from backlogguard.tools import load_policy_config


def build_run_deps(
    root: Path,
    settings: Settings,
    *,
    data_dir: Path | None = None,
    providers: Providers | None = None,
    replay: Path | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> RunDeps:
    data = data_dir or root / "data"
    data.mkdir(parents=True, exist_ok=True)
    if providers is None and replay is not None:  # modo demo: se repiten las respuestas de una corrida grabada
        providers = replay_providers(Recording.load(replay))
    return RunDeps(
        providers=providers or build_providers(load_models_config(root / "config" / "models.yaml"), settings),
        library=SourceLibrary(root / "evals" / "fixtures"),
        retriever=InMemoryRetriever(DeterministicLexicalEmbeddings()),
        memory=ProjectMemory(data / "memoria.sqlite", settings.azdo_project.lower()),
        policy=load_policy_config(root / "config" / "policy.yaml"),
        budget=load_budget(root / "config" / "budgets.yaml"),
        backlog=SimulatedBacklog(data / "backlog_simulado.json"),
        ledger=PublicationLedger(data / "publicaciones.sqlite"),
        project=settings.azdo_project,
        people=load_people(root / "config" / "people.yaml"),
        on_event=on_event,
    )


def open_graph(deps: RunDeps, data_dir: Path):
    """Compila el grafo con el checkpointer de `data/corridas.sqlite` (una corrida = un `thread_id`)."""
    return build_graph(deps, sqlite_checkpointer(data_dir / "corridas.sqlite"))
