"""Dependencias de una corrida: un proveedor por agente, fuentes, índice, memoria y política."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backlogguard.board import AgentRole
from backlogguard.graph.budgets import RunBudget
from backlogguard.hitl import PeopleConfig
from backlogguard.integrations import BacklogGateway, PublicationLedger
from backlogguard.llm.model_config import ModelsConfig
from backlogguard.llm.providers import LLMProvider, build_provider
from backlogguard.llm.settings import Settings
from backlogguard.memory import ProjectMemory
from backlogguard.rag import SourceLibrary, build_chunks
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools.policy_config import PolicyConfig


@dataclass(frozen=True)
class Providers:
    supervisor: LLMProvider
    requerimientos: LLMProvider
    critico: LLMProvider
    auditor: LLMProvider
    integracion: LLMProvider


def build_providers(models: ModelsConfig, settings: Settings) -> Providers:
    """Un proveedor por agente, según `config/models.yaml` (Fake si LIVE_MODE=0)."""
    return Providers(
        supervisor=build_provider(models.for_role(AgentRole.SUPERVISOR), settings),
        requerimientos=build_provider(models.for_role(AgentRole.REQUERIMIENTOS), settings),
        critico=build_provider(models.for_role(AgentRole.CRITICO), settings),
        auditor=build_provider(models.for_role(AgentRole.AUDITOR), settings),
        integracion=build_provider(models.for_role(AgentRole.INTEGRACION), settings),
    )


@dataclass(frozen=True)
class RunDeps:
    providers: Providers
    library: SourceLibrary
    retriever: InMemoryRetriever | QdrantRetriever
    memory: ProjectMemory
    policy: PolicyConfig
    budget: RunBudget
    backlog: BacklogGateway
    ledger: PublicationLedger
    project: str = "ACME"
    people: PeopleConfig | None = None
    on_event: Callable[[dict], None] | None = None


def index_library(library: SourceLibrary, retriever: InMemoryRetriever | QdrantRetriever) -> int:
    """Indexa todas las fuentes. Es idempotente: se repite al reanudar en otro proceso."""
    total = 0
    for document_id, metadata in library.describe():
        chunks = build_chunks(document_id, library.load(document_id).text, metadata.model_dump(mode="json"))
        retriever.index(chunks)
        total += len(chunks)
    return total
