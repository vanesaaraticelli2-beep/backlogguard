"""Elige la implementación de `BacklogGateway` según la configuración (`AZDO_MODE`)."""
from __future__ import annotations

import secrets
from pathlib import Path

from backlogguard.integrations.azure_devops import AzureDevOpsBacklog
from backlogguard.integrations.gateway import BacklogError, BacklogGateway
from backlogguard.integrations.mcp import MCPBacklog, build_azure_mcp_server
from backlogguard.integrations.simulated import SimulatedBacklog
from backlogguard.llm.settings import Settings


def build_rest_backlog(settings: Settings) -> AzureDevOpsBacklog:
    """Create the private REST adapter used behind the Azure DevOps MCP server."""
    if not settings.azdo_org_url.strip():
        raise BacklogError("AZDO_ORG_URL es obligatorio cuando AZDO_MODE=real.")
    if not settings.azdo_token_value():
        raise BacklogError("AZDO_TOKEN es obligatorio cuando AZDO_MODE=real.")
    return AzureDevOpsBacklog(settings)


def build_backlog(settings: Settings, simulated_path: str | Path | None = None) -> BacklogGateway:
    if settings.azdo_mode == "simulated":
        return SimulatedBacklog(simulated_path)
    if settings.azdo_mcp_endpoint:
        return MCPBacklog(
            endpoint=settings.azdo_mcp_endpoint,
            timeout_seconds=settings.request_timeout_seconds,
        )

    rest_backlog = build_rest_backlog(settings)
    write_token = secrets.token_urlsafe(32)
    server = build_azure_mcp_server(
        rest_backlog,
        allow_writes=True,
        approval_token=write_token,
    )
    return MCPBacklog(
        server=server,
        timeout_seconds=settings.request_timeout_seconds,
        write_authorization_token=write_token,
    )
