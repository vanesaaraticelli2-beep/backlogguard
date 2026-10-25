"""Agente Crítico: revisa un ítem con sus tools y devuelve un veredicto validado."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.agents.structured import extract_json, parse_with_repair
from backlogguard.board import AgentRole, Board
from backlogguard.llm.errors import InvalidProviderResponseError
from backlogguard.llm.providers import LLMProvider
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools import ExecutionContext, ToolPolicy, build_catalog_registry
from backlogguard.tools.critico import CriticToolkit

INSTRUCTIONS_PATH = Path(__file__).with_name("agent.md")


class CriticVerdict(BaseModel):
    """Salida del Crítico. Un ítem objetado necesita al menos una objeción concreta."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1)
    verdict: Literal["sustentado", "objetado"]
    objections: list[str] = Field(default_factory=list)
    reasoning: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> CriticVerdict:
        if self.verdict == "objetado" and not any(o.strip() for o in self.objections):
            raise ValueError("un veredicto objetado necesita al menos una objeción")
        if self.verdict == "sustentado" and self.objections:
            raise ValueError("un veredicto sustentado no lleva objeciones")
        return self


@dataclass(frozen=True)
class CriticReview:
    verdict: CriticVerdict
    stop_reason: str
    tokens: int


def parse_verdict(text: str, item_id: str) -> CriticVerdict:
    verdict = CriticVerdict.model_validate_json(extract_json(text))
    if verdict.item_id != item_id:
        raise ValueError(f"el veredicto es del ítem {verdict.item_id}, no de {item_id}")
    return verdict


def review_item(
    item_id: str,
    *,
    provider: LLMProvider,
    retriever: InMemoryRetriever | QdrantRetriever,
    board: Board,
    run_id: str = "run-local",
    max_steps: int = 8,
    max_seconds: float = 180.0,
    max_tool_calls: int = 6,
    max_tokens: int = 40_000,
) -> CriticReview:
    """Corre al Crítico sobre un ítem. Un JSON inválido se repara una vez (patrón de la clase 2)."""
    registry = build_catalog_registry(CriticToolkit(retriever, board).implementations())
    context = ExecutionContext(user_id="factory", role=AgentRole.CRITICO, run_id=run_id)
    policy = ToolPolicy()
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    decider = LLMDecider(
        provider, AgentRole.CRITICO.value, registry, context, policy, instructions=instructions
    )
    outcome = run_basic_agent(
        f"Revisá el ítem {item_id} del tablero.",
        registry,
        decider,
        max_steps=max_steps,
        max_seconds=max_seconds,
        max_tool_calls=max_tool_calls,
        max_tokens=max_tokens,
        tokens_used=lambda: decider.tokens_used,
        context=context,
        policy=policy,
    )
    if outcome["stop_reason"] != "final_answer":
        raise InvalidProviderResponseError(f"el Crítico no llegó a un veredicto ({outcome['stop_reason']})")

    verdict, repair_tokens = parse_with_repair(
        outcome["answer"],
        lambda text: parse_verdict(text, item_id),
        provider=provider,
        system=instructions,
        expected_format=(
            f'{{"item_id": "{item_id}", "verdict": "sustentado"|"objetado", "objections": [...], "reasoning": "..."}}'
        ),
        subject="el Crítico",
    )
    tokens = decider.tokens_used + repair_tokens
    return CriticReview(verdict=verdict, stop_reason=outcome["stop_reason"], tokens=tokens)
