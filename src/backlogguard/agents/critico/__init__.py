"""Agente Crítico: revisa un ítem con sus tools y devuelve un veredicto validado."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backlogguard.agents.decider import LLMDecider
from backlogguard.agents.loop import run_basic_agent
from backlogguard.board import AgentRole, Board
from backlogguard.llm.errors import InvalidProviderResponseError
from backlogguard.llm.providers import LLMProvider
from backlogguard.llm.resilience import generate_with_resilience_sync
from backlogguard.rag.retrieval import InMemoryRetriever, QdrantRetriever
from backlogguard.tools import ExecutionContext, ToolPolicy, build_catalog_registry
from backlogguard.tools.critico import CriticToolkit

INSTRUCTIONS_PATH = Path(__file__).with_name("agent.md")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


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
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("la respuesta no contiene un objeto JSON")
    verdict = CriticVerdict.model_validate_json(cleaned[start : end + 1])
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

    answer, tokens = outcome["answer"], decider.tokens_used
    try:
        verdict = parse_verdict(answer, item_id)
    except (ValueError, ValidationError) as exc:
        repair = generate_with_resilience_sync(
            provider,
            f"Tu respuesta anterior no cumplió el formato: {exc}\n\nRespuesta anterior:\n{json.dumps(answer, ensure_ascii=False)}\n\n"
            f'Respondé solo con el JSON {{"item_id": "{item_id}", "verdict": "sustentado"|"objetado", '
            '"objections": [...], "reasoning": "..."}',
            system=instructions,
        )
        tokens += repair.result.input_tokens + repair.result.output_tokens
        try:
            verdict = parse_verdict(repair.result.text, item_id)
        except (ValueError, ValidationError) as second:
            raise InvalidProviderResponseError(f"el Crítico no devolvió un veredicto válido: {second}") from second
    return CriticReview(verdict=verdict, stop_reason=outcome["stop_reason"], tokens=tokens)
