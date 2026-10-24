import time

import pytest
from pydantic import BaseModel, ConfigDict

from backlogguard.board import AgentRole
from backlogguard.tools import (
    ExecutionContext,
    RetryableToolError,
    Tool,
    ToolCall,
    ToolPolicy,
    ToolRegistry,
    ToolResult,
)


class EchoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


def echo(args: dict) -> ToolResult:
    return ToolResult(ok=True, content=args["text"])


def make_registry(**tool_kwargs) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool("echo", "Devuelve el texto.", "read", echo, args_model=EchoArgs, **tool_kwargs)
    )
    return registry


def test_caso_feliz_agrega_metadata():
    result = make_registry().run(ToolCall(tool_name="echo", arguments={"text": "hola"}))
    assert result.ok and result.content == "hola"
    assert result.metadata["tool"] == "echo" and result.metadata["attempt"] == 1


def test_tool_desconocida():
    result = make_registry().run(ToolCall(tool_name="nada"))
    assert result.metadata["error_type"] == "unknown_tool"


def test_nombre_duplicado():
    registry = make_registry()
    with pytest.raises(ValueError):
        registry.register(Tool("echo", "otra", "read", echo))


def test_kind_bloqueado_sin_policy():
    registry = ToolRegistry()
    registry.register(Tool("escribir", "Escribe.", "write", echo))
    result = registry.run(ToolCall(tool_name="escribir"))
    assert result.metadata["error_type"] == "forbidden_tool"


def test_argumentos_invalidos():
    result = make_registry().run(ToolCall(tool_name="echo", arguments={"texto": "x"}))
    assert result.metadata["error_type"] == "validation_error"


def test_salida_invalida():
    registry = ToolRegistry()
    registry.register(Tool("mala", "Salida rota.", "read", lambda args: {"x": 1}))
    result = registry.run(ToolCall(tool_name="mala"))
    assert result.metadata["error_type"] == "output_validation_error"


def test_timeout_no_reintenta():
    registry = ToolRegistry()
    registry.register(
        Tool("lenta", "Tarda.", "read", lambda args: time.sleep(0.5), timeout_s=0.05, retries=2)
    )
    result = registry.run(ToolCall(tool_name="lenta"))
    assert result.metadata["error_type"] == "timeout" and result.metadata["attempt"] == 1


def test_retry_solo_con_error_transitorio():
    calls = {"n": 0}

    def flaky(args: dict) -> ToolResult:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableToolError("caído")
        return ToolResult(ok=True, content="ok")

    registry = ToolRegistry()
    registry.register(Tool("flaky", "Falla dos veces.", "read", flaky, retries=2, backoff_s=0))
    assert registry.run(ToolCall(tool_name="flaky")).ok
    assert calls["n"] == 3


def test_error_comun_no_se_reintenta():
    calls = {"n": 0}

    def roto(args: dict) -> ToolResult:
        calls["n"] += 1
        raise ValueError("bug")

    registry = ToolRegistry()
    registry.register(Tool("roto", "Falla.", "read", roto, retries=2, backoff_s=0))
    result = registry.run(ToolCall(tool_name="roto"))
    assert result.metadata["retryable"] is False and calls["n"] == 1


def test_retries_agotados():
    def siempre(args: dict) -> ToolResult:
        raise RetryableToolError("caído")

    registry = ToolRegistry()
    registry.register(Tool("siempre", "Siempre cae.", "read", siempre, retries=1, backoff_s=0))
    assert registry.run(ToolCall(tool_name="siempre")).metadata["error_type"] == "retry_exhausted"


def test_tool_no_idempotente_con_retries_se_rechaza():
    with pytest.raises(ValueError):
        Tool("x", "x", "write", echo, retries=1, idempotent=False)


def test_orden_availability_antes_que_validation():
    registry = make_registry(visible_roles={AgentRole.CRITICO})
    context = ExecutionContext(user_id="u", role=AgentRole.AUDITOR)
    result = registry.run(
        ToolCall(tool_name="echo", arguments={"basura": 1}), context=context, policy=ToolPolicy()
    )
    assert result.metadata["error_type"] == "unavailable_tool"


def test_orden_validation_antes_que_authorization():
    registry = make_registry(authorize=lambda ctx, args: "denegado")
    context = ExecutionContext(user_id="u", role=AgentRole.CRITICO)
    policy = ToolPolicy()
    invalid = registry.run(
        ToolCall(tool_name="echo", arguments={"basura": 1}), context=context, policy=policy
    )
    assert invalid.metadata["error_type"] == "validation_error"
    valid = registry.run(
        ToolCall(tool_name="echo", arguments={"text": "a"}), context=context, policy=policy
    )
    assert valid.metadata["error_type"] == "authorization_error"


def test_context_y_policy_van_juntos():
    with pytest.raises(ValueError):
        make_registry().run(
            ToolCall(tool_name="echo"), context=ExecutionContext(user_id="u", role=AgentRole.CRITICO)
        )
