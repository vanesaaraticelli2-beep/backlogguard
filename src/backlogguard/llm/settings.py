"""Configuración validada de la aplicación (clase 3 del curso).

Adaptación: dos proveedores (Anthropic y Gemini), el interruptor `LIVE_MODE`
de las clases 9 a 11 y las rutas de persistencia del Día 3.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración validada de la aplicación."""

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
        env_file_encoding="utf-8",
    )

    app_env: Literal["development", "testing", "production"] = "development"
    live_mode: bool = False
    azdo_mode: Literal["simulated", "real"] = "simulated"
    azdo_org_url: str = ""
    azdo_project: str = "ACME"
    azdo_mcp_endpoint: str | None = None
    azdo_token: SecretStr | None = None
    azdo_epic_type: str | None = None
    azdo_story_type: str | None = None
    azdo_task_type: str | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    request_timeout_seconds: float = Field(default=180.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=8)
    retry_base_delay_seconds: float = Field(default=0.25, ge=0)

    backlogguard_db_path: Path = Path("data/backlogguard.sqlite")
    backlogguard_checkpoint_path: Path = Path("data/checkpoints.json")

    @field_validator("azdo_project", mode="before")
    @classmethod
    def _blank_project_uses_default(cls, value):
        """`AZDO_PROJECT=` vacío en el .env no debe pisar el valor por defecto."""
        return value if isinstance(value, str) and value.strip() else "ACME"

    @field_validator("azdo_epic_type", "azdo_story_type", "azdo_task_type", mode="before")
    @classmethod
    def _blank_work_item_type_uses_discovery(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("azdo_mcp_endpoint", mode="before")
    @classmethod
    def _blank_mcp_endpoint_uses_in_process_server(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("azdo_mcp_endpoint")
    @classmethod
    def _mcp_endpoint_uses_secure_transport(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        valid_transport = parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in local_hosts
        )
        if (
            not valid_transport
            or not parsed.hostname
            or parsed.path.rstrip("/") != "/mcp"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "AZDO_MCP_ENDPOINT debe usar HTTPS o HTTP local y terminar en /mcp, sin credenciales ni parámetros."
            )
        return value

    @classmethod
    def from_env(cls, env_path: str | Path | None = None):
        path = Path(env_path) if env_path is not None else None
        values = {"_env_file": path} if path is not None and path.exists() else {}
        return cls(**values)

    def anthropic_key_value(self) -> str | None:
        return self.anthropic_api_key.get_secret_value() if self.anthropic_api_key else None

    def gemini_key_value(self) -> str | None:
        return self.gemini_api_key.get_secret_value() if self.gemini_api_key else None

    def safe_dict(self) -> dict:
        data = self.model_dump(exclude={"anthropic_api_key", "gemini_api_key", "azdo_token"})
        data["anthropic_api_key"] = "***configurada***" if self.anthropic_api_key else None
        data["gemini_api_key"] = "***configurada***" if self.gemini_api_key else None
        data["azdo_token"] = "***configurado***" if self.azdo_token else None
        return data

    def azdo_token_value(self) -> str | None:
        return self.azdo_token.get_secret_value() if self.azdo_token else None
