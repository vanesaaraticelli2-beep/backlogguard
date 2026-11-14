import asyncio
import socket
import threading
import time

from mcp import Client
import uvicorn
import pytest

from backlogguard.agents.integracion import execute_approved_plan
from backlogguard.integrations import (
    BacklogPermissionError,
    ExecutionReport,
    MCPBacklog,
    SimulatedBacklog,
    build_azure_mcp_server,
)
from backlogguard.integrations.factory import build_backlog
from backlogguard.llm.settings import Settings


def test_endpoint_mcp_remoto_exige_https_y_no_acepta_credenciales_en_url():
    assert Settings(azdo_mcp_endpoint="http://127.0.0.1:8000/mcp").azdo_mcp_endpoint
    assert Settings(azdo_mcp_endpoint="https://mcp.example.com/mcp").azdo_mcp_endpoint
    assert isinstance(
        build_backlog(
            Settings(
                azdo_mode="real",
                azdo_mcp_endpoint="https://mcp.example.com/mcp",
            )
        ),
        MCPBacklog,
    )
    with pytest.raises(ValueError, match="HTTPS o HTTP local"):
        Settings(azdo_mcp_endpoint="http://mcp.example.com/mcp")
    with pytest.raises(ValueError, match="HTTPS o HTTP local"):
        Settings(azdo_mcp_endpoint="https://user:secret@mcp.example.com/mcp")


def test_mcp_publica_tools_resource_y_prompt_y_cliente_en_proceso():
    server = build_azure_mcp_server(SimulatedBacklog())

    async def inspect_server():
        async with Client(server) as client:
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()
            result = await client.call_tool(
                "search_work_items", {"text": "historia", "tag": None}
            )
        return tools, resources, prompts, result

    tools, resources, prompts, result = asyncio.run(inspect_server())
    assert {tool.name for tool in tools.tools} >= {
        "test_connection",
        "search_work_items",
        "create_work_item",
    }
    assert [str(resource.uri) for resource in resources.resources] == [
        "backlogguard://azure/configuration"
    ]
    assert [prompt.name for prompt in prompts.prompts] == ["prepare_backlog_plan"]
    assert not result.is_error
    assert result.structured_content["ok"] is True


def test_gateway_mcp_en_proceso_conserva_el_contrato_y_el_plan_de_escritura():
    token = "test-only-write-token"
    backlog = MCPBacklog(
        server=build_azure_mcp_server(
            SimulatedBacklog(), allow_writes=True, approval_token=token
        ),
        write_authorization_token=token,
    )

    with pytest.raises(BacklogPermissionError):
        backlog.create(
            type="Epic",
            title="No autorizada",
            description="",
            acceptance_criteria=[],
            tags=[],
            parent_id=None,
        )
    with backlog.authorize_writes():
        created = backlog.create(
            type="Epic",
            title="Épica de prueba",
            description="",
            acceptance_criteria=[],
            tags=["mcp-test"],
            parent_id=None,
        )
        updated_state = backlog.transition_state(
            created.id,
            expected_rev=created.rev,
            state="Removed",
        )
    found = backlog.search(text="Épica")

    assert updated_state.state == "Removed"
    assert backlog.get(created.id) == updated_state
    assert found == [updated_state]


def test_solo_la_ruta_de_plan_aprobado_transmite_autorizacion_de_escritura():
    token = "test-only-write-token"
    backlog = MCPBacklog(
        server=build_azure_mcp_server(
            SimulatedBacklog(), allow_writes=True, approval_token=token
        ),
        write_authorization_token=token,
    )

    class Service:
        def __init__(self):
            self.backlog = backlog
            self.created = None

        def execute(self, plan_hash):
            self.created = self.backlog.create(
                type="Epic",
                title=plan_hash,
                description="",
                acceptance_criteria=[],
                tags=[],
                parent_id=None,
            )
            return ExecutionReport(ok=True)

    service = Service()
    report = execute_approved_plan("approved-hash", service=service, approved_by="persona")

    assert report.ok
    assert service.created is not None
    assert service.backlog.get(service.created.id) == service.created


def test_servidor_http_read_only_rechaza_escrituras():
    server = build_azure_mcp_server(SimulatedBacklog(), allow_writes=False)

    async def attempt_write():
        async with Client(server) as client:
            return await client.call_tool(
                "create_work_item",
                {
                    "type": "Epic",
                    "title": "No debe crearse",
                    "description": "",
                    "acceptance_criteria": [],
                    "tags": [],
                    "parent_id": None,
                },
            )

    result = asyncio.run(attempt_write())
    assert not result.is_error
    assert result.structured_content["ok"] is False
    assert result.structured_content["error_type"] == "BacklogPermissionError"


def test_cliente_http_streamable_mcp_conecta_al_servidor_read_only():
    server = build_azure_mcp_server(SimulatedBacklog(), allow_writes=False)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    http_server = uvicorn.Server(
        uvicorn.Config(
            server.streamable_http_app(stateless_http=True, json_response=True),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )
    thread = threading.Thread(
        target=lambda: asyncio.run(http_server.serve()),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if http_server.started:
            break
        time.sleep(0.01)
    assert http_server.started

    try:
        backlog = MCPBacklog(endpoint=f"http://127.0.0.1:{port}/mcp")
        assert backlog.search() == []
        async def attempt_http_write():
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                return await client.call_tool(
                    "create_work_item",
                    {
                        "type": "Epic",
                        "title": "No debe crearse",
                        "description": "",
                        "acceptance_criteria": [],
                        "tags": [],
                        "parent_id": None,
                    },
                )

        result = asyncio.run(attempt_http_write())
        assert result.structured_content["ok"] is False
        assert result.structured_content["error_type"] == "BacklogPermissionError"
    finally:
        http_server.should_exit = True
        thread.join(timeout=5)
