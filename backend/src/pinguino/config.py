"""Local runtime settings. The API binds to loopback only and never stores credentials."""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PINGUINO_", extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8787, ge=1024, le=65535)
    data_dir: Path = Path("./data")
    source_locale: str = "fr"
    request_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    @field_validator("host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        if value not in LOOPBACK_HOSTS:
            raise ValueError("the API may only bind to a loopback address")
        return value

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset(
            f"{scheme}://{host}:{self.port}"
            for scheme in ("http",)
            for host in ("127.0.0.1", "localhost")
        )


def load_settings() -> Settings:
    return Settings()
