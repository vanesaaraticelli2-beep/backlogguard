"""Elige la implementación de `BacklogGateway` según la configuración (`AZDO_MODE`)."""
from __future__ import annotations

from pathlib import Path

from backlogguard.integrations.gateway import BacklogError, BacklogGateway
from backlogguard.integrations.simulated import SimulatedBacklog
from backlogguard.llm.settings import Settings


def build_backlog(settings: Settings, simulated_path: str | Path | None = None) -> BacklogGateway:
    if settings.azdo_mode == "simulated":
        return SimulatedBacklog(simulated_path)
    raise BacklogError(
        "AZDO_MODE=real todavía no está disponible: el cliente MCP de Azure DevOps se incorpora "
        "después de las clases de noviembre. Usá AZDO_MODE=simulated."
    )
