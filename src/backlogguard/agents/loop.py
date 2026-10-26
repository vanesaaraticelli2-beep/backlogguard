"""Ciclo de agente Decide → Act → Observe (clase 9 del curso).

`AgentDecision`, `sanitize_for_trace` y `run_basic_agent` siguen el curso.
Adaptaciones: tope de tokens (`max_tokens` + `tokens_used`, `stop_reason`
`token_budget`, que el curso no tiene) y un error del LLM que se agota corta el
ciclo con `unrecoverable_error` en lugar de propagarse.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from backlogguard.llm.errors import LLMError
from backlogguard.tools.models import ToolCall


class AgentDecision(BaseModel):
    """Decisión estructurada del modelo."""

    action: Literal["tool", "final"]
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    final_answer: str | None = None


SENSITIVE_MARKERS = {
    "api_key", "apikey", "secret", "token", "password", "credential"
}


def sanitize_for_trace(value):
    """Enmascara claves sensibles dentro de dicts/listas antes de persistir trazas."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in SENSITIVE_MARKERS):
                cleaned[key] = "***REDACTED***"
            else:
                cleaned[key] = sanitize_for_trace(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_for_trace(item) for item in value]
    return value


def run_basic_agent(
    user_message,
    registry,
    decide_next,
    max_steps=4,
    max_seconds=10.0,
    allowed_kinds=None,
    *,
    context=None,
    policy=None,
    max_tool_calls=None,
    max_tokens: int | None = None,
    tokens_used: Callable[[], int] | None = None,
    on_event: Callable[[dict], None] | None = None,
    initial_calls: list[tuple[str, dict]] | None = None,
):
    """Ejecuta Decide → Act → Observe y devuelve respuesta, traza y stop reason.

    `decide_next` recibe el mensaje original y las Observations acumuladas.
    Toda Tool se ejecuta a través del Registry para conservar los controles del runtime.
    `max_tokens` se compara con `tokens_used()` antes de cada decisión nueva.
    `on_event` (opcional) recibe cada entrada de la traza apenas ocurre, para seguir al agente en vivo.
    `initial_calls` (fuera del curso) son tools que corre el código antes de la primera decisión: pasan por el
    Registry con la misma política, quedan en la traza marcadas `precalculada` y llegan al modelo como observaciones.
    """
    if max_tokens is not None and tokens_used is None:
        raise ValueError("max_tokens requiere tokens_used")

    observations = []
    trace = []
    started = time.perf_counter()
    tool_calls = 0

    def record(entry: dict) -> None:
        trace.append(entry)
        if on_event is not None:
            on_event(entry)

    def stop(answer: str, reason: str) -> dict:
        return {
            "answer": answer,
            "trace": trace,
            "observations": observations,
            "stop_reason": reason,
        }

    for name, arguments in initial_calls or []:
        result = registry.run(
            ToolCall(tool_name=name, arguments=arguments), allowed_kinds=allowed_kinds, context=context, policy=policy
        )
        observations.append(result)
        record({
            "run_id": getattr(context, "run_id", None),
            "step": 0,
            "event": "observation",
            "tool": name,
            "arguments": sanitize_for_trace(arguments),
            "observation": sanitize_for_trace(result.model_dump()),
            "precalculada": True,
        })

    for step in range(1, max_steps + 1):
        if time.perf_counter() - started > max_seconds:
            return stop("Se alcanzó el límite de tiempo.", "timeout")

        if max_tokens is not None and tokens_used() >= max_tokens:
            return stop("Se alcanzó el presupuesto de tokens.", "token_budget")

        try:
            decision = decide_next(user_message, observations)
        except LLMError as exc:
            record({
                "run_id": getattr(context, "run_id", None),
                "step": step,
                "event": "llm_error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            return stop(f"Falló el modelo: {exc}", "unrecoverable_error")

        record({
            "run_id": getattr(context, "run_id", None),
            "step": step,
            "event": "decision",
            "decision": sanitize_for_trace(decision.model_dump()),
        })

        if decision.action == "final":
            return stop(decision.final_answer, "final_answer")

        if max_tool_calls is not None and tool_calls >= max_tool_calls:
            return stop("Se alcanzó el presupuesto de Tool Calls.", "budget")

        if not decision.tool_name:
            return stop("Decisión inválida: falta tool_name.", "unrecoverable_error")

        result = registry.run(
            ToolCall(
                tool_name=decision.tool_name,
                arguments=decision.arguments,
            ),
            allowed_kinds=allowed_kinds,
            context=context,
            policy=policy,
        )

        tool_calls += 1
        observations.append(result)

        record({
            "run_id": getattr(context, "run_id", None),
            "step": step,
            "event": "observation",
            "tool": decision.tool_name,
            "arguments": sanitize_for_trace(decision.arguments),
            "observation": sanitize_for_trace(result.model_dump()),
        })

    return stop("Se alcanzó el máximo de pasos.", "max_steps")
