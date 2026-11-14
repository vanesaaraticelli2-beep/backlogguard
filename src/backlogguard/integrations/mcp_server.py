"""Run the read-only Azure DevOps MCP server over local Streamable HTTP."""
from __future__ import annotations

import os
from pathlib import Path

from backlogguard.integrations.factory import build_rest_backlog
from backlogguard.integrations.gateway import BacklogError
from backlogguard.integrations.mcp import build_azure_mcp_server
from backlogguard.llm.settings import Settings


def main() -> None:
    settings = Settings.from_env(Path.cwd() / ".env")
    if settings.azdo_mode != "real":
        raise BacklogError("El servidor MCP de Azure requiere AZDO_MODE=real.")
    backlog = build_rest_backlog(settings)
    server = build_azure_mcp_server(backlog, allow_writes=False)
    server.run(
        transport="streamable-http",
        stateless_http=True,
        json_response=True,
        host="127.0.0.1",
        port=int(os.environ.get("AZDO_MCP_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
