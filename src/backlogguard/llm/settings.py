"""Configuración validada de la aplicación (clase 3 del curso).

Adaptación: dos proveedores (Anthropic y Gemini), el interruptor `LIVE_MODE`
de las clases 9 a 11 y las rutas de persistencia del Día 3.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    request_timeout_seconds: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=8)
    retry_base_delay_seconds: float = Field(default=0.25, ge=0)

    backlogguard_db_path: Path = Path("data/backlogguard.sqlite")
    backlogguard_checkpoint_path: Path = Path("data/checkpoints.json")

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
        data = self.model_dump(exclude={"anthropic_api_key", "gemini_api_key"})
        data["anthropic_api_key"] = "***configurada***" if self.anthropic_api_key else None
        data["gemini_api_key"] = "***configurada***" if self.gemini_api_key else None
        return data
