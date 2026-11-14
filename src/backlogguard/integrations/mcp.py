"""MCP server and defensive client for the Azure DevOps backlog gateway."""
from __future__ import annotations

import asyncio
import json
import secrets
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from mcp import Client
from mcp.server import MCPServer

from backlogguard.integrations.gateway import (
    BacklogAuthenticationError,
    BacklogError,
    BacklogNotFoundError,
    BacklogPermissionError,
    BacklogRateLimitError,
    BacklogTimeout,
    ConflictError,
    WorkItem,
)

_ERROR_TYPES: dict[str, type[BacklogError]] = {
    error.__name__: error
    for error in (
        BacklogAuthenticationError,
        BacklogNotFoundError,
        BacklogPermissionError,
        BacklogRateLimitError,
        BacklogTimeout,
        ConflictError,
        BacklogError,
    )
}


def build_azure_mcp_server(
    backlog: Any,
    *,
    allow_writes: bool = False,
    approval_token: str | None = None,
) -> MCPServer:
    """Expose the gateway as MCP Tools, plus a safe Resource and Prompt."""
    if allow_writes and not approval_token:
        raise ValueError("El servidor MCP de escritura requiere un token de autorización interno.")
    server = MCPServer(
        "backlogguard-azure-devops",
        instructions="Acceso al backlog Azure DevOps de BacklogGuard. Las escrituras requieren el flujo de aprobación de la aplicación.",
    )

    def invoke(operation):
        try:
            return {"ok": True, "data": operation()}
        except BacklogError as exc:
            return {
                "ok": False,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

    def check_write_permission(supplied_token: str | None) -> None:
        if not allow_writes or not supplied_token or not secrets.compare_digest(
            supplied_token, approval_token or ""
        ):
            raise BacklogPermissionError(
                "La escritura MCP requiere autorización de la aplicación."
            )

    @server.tool()
    def test_connection() -> dict[str, Any]:
        """Prueba la autenticación y descubre proyecto y tipos de work item."""
        return invoke(backlog.test_connection)

    @server.tool()
    def list_projects() -> dict[str, Any]:
        """Lista los proyectos accesibles con las credenciales configuradas."""
        return invoke(backlog.list_projects)

    @server.tool()
    def resolve_work_item_type(requested_type: str) -> dict[str, Any]:
        """Resuelve un tipo lógico al tipo disponible en el proceso Azure."""
        return invoke(lambda: backlog.resolve_work_item_type(requested_type))

    @server.tool()
    def list_work_item_states(work_item_type: str) -> dict[str, Any]:
        """Lista estados y categorías permitidos por el proceso Azure para un tipo."""
        return invoke(lambda: backlog.list_work_item_states(work_item_type))

    @server.tool()
    def reload() -> dict[str, Any]:
        """Actualiza el snapshot local desde el backlog configurado."""
        return invoke(lambda: (backlog.reload(), True)[1])

    @server.tool()
    def search_work_items(text: str | None = None, tag: str | None = None) -> dict[str, Any]:
        """Busca work items por texto o etiqueta."""
        return invoke(
            lambda: [
                item.model_dump(mode="json")
                for item in backlog.search(text=text, tag=tag)
            ]
        )

    @server.tool()
    def get_work_item(work_item_id: int) -> dict[str, Any]:
        """Lee un work item por su identificador."""
        return invoke(
            lambda: (
                item.model_dump(mode="json")
                if (item := backlog.get(work_item_id)) is not None
                else None
            )
        )

    @server.tool()
    def get_work_item_children(work_item_id: int) -> dict[str, Any]:
        """Lista los hijos directos de un work item para proteger jerarquías activas."""
        return invoke(
            lambda: [
                item.model_dump(mode="json")
                for item in backlog.get_children(work_item_id)
            ]
        )

    @server.tool()
    def create_work_item(
        type: str,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
        parent_id: int | None,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Crea un work item únicamente con autorización interna de la aplicación."""
        def create() -> dict[str, Any]:
            check_write_permission(approval_token)
            return backlog.create(
                type=type,
                title=title,
                description=description,
                acceptance_criteria=acceptance_criteria,
                tags=tags,
                parent_id=parent_id,
            ).model_dump(mode="json")

        return invoke(create)

    @server.tool()
    def update_work_item(
        work_item_id: int,
        expected_rev: int,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Actualiza un work item únicamente con autorización interna de la aplicación."""
        def update() -> dict[str, Any]:
            check_write_permission(approval_token)
            return backlog.update(
                work_item_id,
                expected_rev=expected_rev,
                title=title,
                description=description,
                acceptance_criteria=acceptance_criteria,
                tags=tags,
            ).model_dump(mode="json")

        return invoke(update)

    @server.tool()
    def link_parent(
        work_item_id: int,
        parent_id: int,
        expected_rev: int,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Vincula un work item únicamente con autorización interna de la aplicación."""
        def link() -> dict[str, Any]:
            check_write_permission(approval_token)
            return backlog.link_parent(
                work_item_id, parent_id, expected_rev=expected_rev
            ).model_dump(mode="json")

        return invoke(link)

    @server.tool()
    def transition_work_item_state(
        work_item_id: int,
        expected_rev: int,
        state: str,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Cambia el estado de un work item solo con autorización interna."""
        def transition() -> dict[str, Any]:
            check_write_permission(approval_token)
            return backlog.transition_state(
                work_item_id,
                expected_rev=expected_rev,
                state=state,
            ).model_dump(mode="json")

        return invoke(transition)

    @server.resource("backlogguard://azure/configuration")
    def configuration() -> str:
        """Describe la conexión activa sin exponer credenciales."""
        return json.dumps(
            {
                "organization": getattr(backlog, "organization_url", None),
                "project": getattr(backlog, "project", None),
                "authentication": "backend secret",
                "writes_enabled": allow_writes,
            },
            ensure_ascii=False,
        )

    @server.prompt()
    def prepare_backlog_plan(plan_summary: str) -> str:
        """Guía para revisar un plan antes de ejecutar cualquier escritura."""
        return (
            "Revisá este plan de publicación sin ejecutarlo: "
            f"{plan_summary}. Las escrituras solo se realizan mediante la aplicación "
            "después de una aprobación humana explícita."
        )

    return server


class MCPBacklog:
    """Synchronous `BacklogGateway` facade over an in-process or HTTP MCP client."""

    def __init__(
        self,
        *,
        server: MCPServer | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 180.0,
        write_authorization_token: str | None = None,
    ):
        if (server is None) == (endpoint is None):
            raise ValueError("Se debe indicar exactamente un servidor MCP o endpoint.")
        self._target = server if server is not None else endpoint
        self._timeout_seconds = timeout_seconds
        self._write_authorization_token = write_authorization_token
        self._write_authorized: ContextVar[bool] = ContextVar(
            f"mcp_backlog_write_authorized_{id(self)}", default=False
        )

    @contextmanager
    def authorize_writes(self):
        """Temporarily permit writes only inside the application's approved-plan flow."""
        if not self._write_authorization_token:
            raise BacklogPermissionError("Este cliente MCP no tiene permisos de escritura.")
        authorization = self._write_authorized.set(True)
        try:
            yield
        finally:
            self._write_authorized.reset(authorization)

    def _run(self, coroutine):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coroutine)
            try:
                return future.result(timeout=self._timeout_seconds + 1)
            except FuturesTimeout as exc:
                future.cancel()
                raise BacklogTimeout("Se agotó el tiempo de espera del cliente MCP.") from exc

    async def _call_async(self, tool: str, arguments: dict[str, Any]) -> Any:
        async def invoke():
            async with Client(self._target) as client:
                return await client.call_tool(tool, arguments)

        try:
            result = await asyncio.wait_for(invoke(), timeout=self._timeout_seconds)
        except TimeoutError as exc:
            raise BacklogTimeout(f"Timeout llamando la tool MCP {tool}.") from exc
        except BacklogError:
            raise
        except Exception as exc:
            raise BacklogError(f"No se pudo completar la llamada MCP {tool}.") from exc

        if result.is_error or result.structured_content is None:
            raise BacklogError(f"La tool MCP {tool} devolvió una respuesta inválida.")
        payload = result.structured_content
        if not isinstance(payload, dict):
            raise BacklogError(f"La tool MCP {tool} no respetó el contrato de respuesta.")
        if set(payload) == {"result"}:
            payload = payload["result"]
        if not isinstance(payload, dict) or "ok" not in payload:
            raise BacklogError(f"La tool MCP {tool} no respetó el contrato de respuesta.")
        if not payload["ok"]:
            error_type = _ERROR_TYPES.get(payload.get("error_type"), BacklogError)
            raise error_type(payload.get("message", f"Falló la tool MCP {tool}."))
        return payload.get("data")

    def _call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        args = dict(arguments or {})
        if tool in {
            "create_work_item",
            "update_work_item",
            "link_parent",
            "transition_work_item_state",
        }:
            if not self._write_authorized.get():
                raise BacklogPermissionError(
                    "Las escrituras MCP solo se permiten durante la ejecución de un plan aprobado."
                )
            args["approval_token"] = self._write_authorization_token
        return self._run(
            self._call_async(tool, args)
        )

    def resolve_work_item_type(self, requested_type: str) -> str:
        return self._call("resolve_work_item_type", {"requested_type": requested_type})

    def list_work_item_states(self, work_item_type: str) -> list[dict[str, str]]:
        return self._call(
            "list_work_item_states", {"work_item_type": work_item_type}
        )

    def reload(self) -> None:
        self._call("reload")

    def search(self, *, text: str | None = None, tag: str | None = None) -> list[WorkItem]:
        data = self._call("search_work_items", {"text": text, "tag": tag})
        return [WorkItem.model_validate(item) for item in data]

    def get(self, work_item_id: int) -> WorkItem | None:
        data = self._call("get_work_item", {"work_item_id": work_item_id})
        return WorkItem.model_validate(data) if data is not None else None

    def get_children(self, work_item_id: int) -> list[WorkItem]:
        data = self._call("get_work_item_children", {"work_item_id": work_item_id})
        return [WorkItem.model_validate(item) for item in data]

    def create(
        self,
        *,
        type: str,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
        parent_id: int | None,
    ) -> WorkItem:
        data = self._call(
            "create_work_item",
            {
                "type": type,
                "title": title,
                "description": description,
                "acceptance_criteria": acceptance_criteria,
                "tags": tags,
                "parent_id": parent_id,
            },
        )
        return WorkItem.model_validate(data)

    def update(
        self,
        work_item_id: int,
        *,
        expected_rev: int,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
    ) -> WorkItem:
        data = self._call(
            "update_work_item",
            {
                "work_item_id": work_item_id,
                "expected_rev": expected_rev,
                "title": title,
                "description": description,
                "acceptance_criteria": acceptance_criteria,
                "tags": tags,
            },
        )
        return WorkItem.model_validate(data)

    def link_parent(self, work_item_id: int, parent_id: int, *, expected_rev: int) -> WorkItem:
        data = self._call(
            "link_parent",
            {
                "work_item_id": work_item_id,
                "parent_id": parent_id,
                "expected_rev": expected_rev,
            },
        )
        return WorkItem.model_validate(data)

    def transition_state(
        self, work_item_id: int, *, expected_rev: int, state: str
    ) -> WorkItem:
        data = self._call(
            "transition_work_item_state",
            {
                "work_item_id": work_item_id,
                "expected_rev": expected_rev,
                "state": state,
            },
        )
        return WorkItem.model_validate(data)

    def test_connection(self) -> dict[str, Any]:
        return self._call("test_connection")

    def list_projects(self) -> list[dict[str, str]]:
        return self._call("list_projects")
