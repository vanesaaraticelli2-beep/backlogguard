"""ToolRegistry: availability, validation, authorization, timeout y retry (clase 9 del curso)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from time import perf_counter, sleep

from pydantic import ValidationError

from backlogguard.tools.models import (
    ExecutionContext,
    RetryableToolError,
    ToolCall,
    ToolKind,
    ToolResult,
)
from backlogguard.tools.policy import ToolPolicy
from backlogguard.tools.tool import Tool


class ToolRegistry:
    """Registry con availability, validation, authorization, timeout y retry."""

    DEFAULT_ALLOWED_KINDS: set[ToolKind] = {"read", "compute", "local_write"}

    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registra una Tool sin permitir nombres duplicados."""
        if tool.name in self.tools:
            raise ValueError(f"Tool duplicada: {tool.name}")
        self.tools[tool.name] = tool

    def available_tools(
        self,
        allowed_kinds: set[str] | None = None,
        *,
        context: ExecutionContext | None = None,
        policy: ToolPolicy | None = None,
    ) -> list[Tool]:
        """Devuelve las Tools visibles por lista de kinds o por Policy."""
        if (context is None) != (policy is None):
            raise ValueError("context y policy deben proporcionarse juntos.")

        if context is not None and policy is not None:
            return policy.allowed_tools(self, context)

        allowed = (
            self.DEFAULT_ALLOWED_KINDS
            if allowed_kinds is None
            else allowed_kinds
        )
        return [tool for tool in self.tools.values() if tool.kind in allowed]

    def function_declarations(
        self,
        allowed_kinds: set[str] | None = None,
        *,
        context: ExecutionContext | None = None,
        policy: ToolPolicy | None = None,
    ) -> list[dict]:
        """Convierte las Tools visibles en declaraciones para el modelo."""
        return [
            tool.function_declaration()
            for tool in self.available_tools(
                allowed_kinds,
                context=context,
                policy=policy,
            )
        ]

    def run(
        self,
        call: ToolCall,
        allowed_kinds: set[str] | None = None,
        *,
        context: ExecutionContext | None = None,
        policy: ToolPolicy | None = None,
    ) -> ToolResult:
        """Ejecuta un Tool Call atravesando todas las capas del runtime.

        Orden de controles:
            Registry → Availability → Validation → Authorization → Execution.
        """
        if (context is None) != (policy is None):
            raise ValueError("context y policy deben proporcionarse juntos.")

        # 1. Registry: ¿existe?
        tool = self.tools.get(call.tool_name)
        if tool is None:
            return ToolResult(
                ok=False,
                content=f"Tool desconocida: {call.tool_name}",
                metadata={"error_type": "unknown_tool"},
            )

        # 2. Availability: ¿se expone en este contexto?
        if context is not None and policy is not None:
            visible = {
                item.name
                for item in policy.allowed_tools(self, context)
            }
            if tool.name not in visible:
                return ToolResult(
                    ok=False,
                    content=f"Tool no disponible en este contexto: {tool.name}",
                    metadata={
                        "error_type": "unavailable_tool",
                        "role": context.role,
                        "kind": tool.kind,
                    },
                )
        else:
            allowed = (
                self.DEFAULT_ALLOWED_KINDS
                if allowed_kinds is None
                else allowed_kinds
            )
            if tool.kind not in allowed:
                return ToolResult(
                    ok=False,
                    content=f"Tool bloqueada por política: {tool.name}",
                    metadata={
                        "error_type": "forbidden_tool",
                        "kind": tool.kind,
                    },
                )

        # 3. Validation: ¿los argumentos tienen forma válida?
        try:
            args = (
                tool.args_model.model_validate(call.arguments).model_dump()
                if tool.args_model
                else dict(call.arguments)
            )
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                content="Argumentos inválidos",
                metadata={
                    "error_type": "validation_error",
                    "details": exc.errors(include_url=False),
                },
            )

        # 4. Authorization: ¿esta llamada concreta está permitida?
        if context is not None and policy is not None:
            denial = policy.authorize(context, tool, args)
            if denial:
                return ToolResult(
                    ok=False,
                    content=denial,
                    metadata={
                        "error_type": "authorization_error",
                        "tool": tool.name,
                    },
                )

        # 5. Execution. Solo `RetryableToolError` habilita un nuevo intento.
        last_retryable_error: RetryableToolError | None = None

        for attempt in range(1, tool.retries + 2):
            if attempt > 1:
                sleep(tool.backoff_s * (2 ** (attempt - 2)))

            executor = ThreadPoolExecutor(max_workers=1)
            started = perf_counter()

            try:
                future = executor.submit(tool.fn, args)
                raw_result = future.result(timeout=tool.timeout_s)
                elapsed_ms = (perf_counter() - started) * 1000

                # El output contract también se valida: un handler que devuelve
                # otra forma no debe contaminar el resto del loop.
                try:
                    result = ToolResult.model_validate(raw_result)
                except ValidationError as exc:
                    return ToolResult(
                        ok=False,
                        content=f"Salida inválida de {tool.name}",
                        metadata={
                            "error_type": "output_validation_error",
                            "tool": tool.name,
                            "details": exc.errors(include_url=False),
                        },
                    )

                result.metadata = {
                    **result.metadata,
                    "tool": tool.name,
                    "kind": tool.kind,
                    "attempt": attempt,
                    "latency_ms": round(elapsed_ms, 2),
                    "idempotent": tool.idempotent,
                }
                return result

            except FuturesTimeout:
                # Cancelar la espera no garantiza detener el thread: un timeout
                # nunca se reintenta automáticamente.
                future.cancel()
                return ToolResult(
                    ok=False,
                    content=f"Timeout ejecutando {tool.name}",
                    metadata={
                        "error_type": "timeout",
                        "tool": tool.name,
                        "timeout_s": tool.timeout_s,
                        "attempt": attempt,
                    },
                )

            except RetryableToolError as exc:
                last_retryable_error = exc
                if attempt > tool.retries:
                    break

            except Exception as exc:
                # Un error no marcado como transitorio no se repite.
                return ToolResult(
                    ok=False,
                    content=f"Error controlado: {exc}",
                    metadata={
                        "error_type": type(exc).__name__,
                        "tool": tool.name,
                        "attempt": attempt,
                        "retryable": False,
                    },
                )

            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        return ToolResult(
            ok=False,
            content=f"Se agotaron los retries: {last_retryable_error}",
            metadata={
                "error_type": "retry_exhausted",
                "exception_type": type(last_retryable_error).__name__,
                "tool": tool.name,
                "attempts": tool.retries + 1,
            },
        )
