"""Arma las dependencias de una corrida a partir de la configuración del proyecto.

Lo comparten los scripts y la pantalla, para que todos abran el mismo backlog simulado, la misma memoria
y el mismo archivo de checkpoints dentro de `data/`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from backlogguard.board import SourceType
from backlogguard.catalog import Catalog
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


USER_SOURCES = "fuentes"


def user_sources_dir(data_dir: Path) -> Path:
    return data_dir / USER_SOURCES


def baseline_dir(data_dir: Path) -> Path:
    """Compromisos extraídos de la preventa (línea base), uno por preventa y ligados a su huella."""
    return data_dir / "linea_base"


def has_user_sources(directory: Path) -> bool:
    """¿Hay fuentes propias utilizables? Hace falta al menos una preventa y una reunión o minuta."""
    if not directory.is_dir():
        return False
    kinds = {metadata.source_type for _, metadata in SourceLibrary(directory).describe()}
    return SourceType.PREVENTA in kinds and bool(kinds & {SourceType.REUNION, SourceType.MINUTA})


def build_run_deps(
    root: Path,
    settings: Settings,
    *,
    data_dir: Path | None = None,
    providers: Providers | None = None,
    replay: Path | None = None,
    sources_dir: Path | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> RunDeps:
    data = data_dir or root / "data"
    data.mkdir(parents=True, exist_ok=True)
    if providers is None and replay is not None:  # modo demo: se repiten las respuestas de una corrida grabada
        providers = replay_providers(Recording.load(replay))
    budget = load_budget(root / "config" / "budgets.yaml")
    return RunDeps(
        providers=providers or build_providers(load_models_config(root / "config" / "models.yaml"), settings),
        library=SourceLibrary(sources_dir or root / "evals" / "fixtures"),
        retriever=InMemoryRetriever(DeterministicLexicalEmbeddings()),
        memory=ProjectMemory(data / "memoria.sqlite", settings.azdo_project.lower()),
        policy=load_policy_config(root / "config" / "policy.yaml"),
        budget=budget,
        backlog=SimulatedBacklog(data / "backlog_simulado.json"),
        ledger=PublicationLedger(data / "publicaciones.sqlite"),
        project=settings.azdo_project,
        people=load_people(root / "config" / "people.yaml"),
        catalog=Catalog(data / "catalogo.sqlite"),
        on_event=on_event,
    )


def open_graph(deps: RunDeps, data_dir: Path):
    """Compila el grafo con el checkpointer de `data/corridas.sqlite` (una corrida = un `thread_id`)."""
    return build_graph(deps, sqlite_checkpointer(data_dir / "corridas.sqlite"))
