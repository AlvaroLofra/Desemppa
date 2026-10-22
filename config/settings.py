"""Configuración: variables de entorno (.env) + catálogos TOML de modelos y perfiles (dossier §1.1)."""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

Provider = Literal["gemini", "claude"]
Effort = Literal["low", "medium", "high"]
Role = Literal["triaje", "cribado", "defensa", "contraparte", "magistrado", "nli", "auditor"]
CORE_ROLES: tuple[Role, ...] = ("triaje", "cribado", "defensa", "contraparte", "magistrado", "nli")


def _default_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "iuris"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    data_dir: Path = Field(default_factory=_default_data_dir, alias="IURIS_DATA_DIR")
    sqlite_path: Path | None = Field(default=None, alias="IURIS_SQLITE_PATH")
    lancedb_dir: Path | None = Field(default=None, alias="IURIS_LANCEDB_DIR")
    claude_exe: str | None = Field(default=None, alias="IURIS_CLAUDE_EXE")
    claude_sandbox_dir: Path | None = Field(default=None, alias="IURIS_CLAUDE_SANDBOX_DIR")
    host: str = Field(default="127.0.0.1", alias="IURIS_HOST")
    port: int = Field(default=8000, alias="IURIS_PORT")
    log_level: str = Field(default="INFO", alias="IURIS_LOG_LEVEL")

    @model_validator(mode="after")
    def _derive_paths(self) -> Settings:
        # Las rutas de .env.example usan %LOCALAPPDATA%: se expanden aquí.
        self.data_dir = Path(os.path.expandvars(str(self.data_dir)))
        self.sqlite_path = Path(os.path.expandvars(str(self.sqlite_path or self.data_dir / "local_cache.db")))
        self.lancedb_dir = Path(os.path.expandvars(str(self.lancedb_dir or self.data_dir / "lancedb_store")))
        self.claude_sandbox_dir = Path(
            os.path.expandvars(str(self.claude_sandbox_dir or self.data_dir / "claude_sandbox"))
        )
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("IURIS_HOST debe ser loopback (dossier §2.5)")
        return self

    @property
    def claude_lock_path(self) -> Path:
        return self.data_dir / "claude.lock"


class ModelSpec(BaseModel):
    provider: Provider
    model_id: str | None = None  # gemini
    cli_model: str | None = None  # claude
    efforts: list[Effort] = Field(default_factory=lambda: list[Effort](["low", "medium", "high"]))
    rpm: int | None = None
    rpd: int | None = None
    timeout_s: float = 60
    output_dimensionality: int | None = None
    fallbacks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _id_por_proveedor(self) -> ModelSpec:
        if self.provider == "gemini" and not self.model_id:
            raise ValueError("modelo gemini sin model_id")
        if self.provider == "claude" and not self.cli_model:
            raise ValueError("modelo claude sin cli_model")
        return self


class RoleAssignment(BaseModel):
    model: str
    effort: Effort


class Profile(BaseModel):
    label: str
    claude_calls_per_query: int
    default: bool = False
    optional: bool = False
    nli_cross_family: str | None = None
    roles: dict[Role, RoleAssignment]


class CircuitBreakerConfig(BaseModel):
    default_open_minutes: int = 60
    gemini_max_retries: int = 3


class Catalog(BaseModel):
    models: dict[str, ModelSpec]
    profiles: dict[str, Profile]
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()

    @model_validator(mode="after")
    def _referencias(self) -> Catalog:
        for alias, spec in self.models.items():
            for fb in spec.fallbacks:
                if fb not in self.models:
                    raise ValueError(f"fallback desconocido '{fb}' en el modelo '{alias}'")
        for name, profile in self.profiles.items():
            missing = [r for r in CORE_ROLES if r not in profile.roles]
            if missing:
                raise ValueError(f"perfil '{name}' sin roles {missing}")
            for role, assignment in profile.roles.items():
                target = self.models.get(assignment.model)
                if target is None:
                    raise ValueError(f"perfil '{name}', rol '{role}': alias desconocido '{assignment.model}'")
                if assignment.effort not in target.efforts:
                    raise ValueError(f"perfil '{name}', rol '{role}': effort no soportado")
        return self

    def default_profile(self) -> str:
        return next((n for n, p in self.profiles.items() if p.default), next(iter(self.profiles)))


_PROFILE_META = {"label", "claude_calls_per_query", "default", "optional", "nli_cross_family"}


def load_catalog(config_dir: Path = CONFIG_DIR) -> Catalog:
    models_raw = tomllib.loads((config_dir / "models.toml").read_text(encoding="utf-8"))
    profiles_raw = tomllib.loads((config_dir / "profiles.toml").read_text(encoding="utf-8"))
    profiles = {
        name: {
            **{k: v for k, v in body.items() if k in _PROFILE_META},
            "roles": {k: v for k, v in body.items() if k not in _PROFILE_META},
        }
        for name, body in profiles_raw["profiles"].items()
    }
    return Catalog.model_validate(
        {
            "models": models_raw["models"],
            "profiles": profiles,
            "circuit_breaker": models_raw.get("circuit_breaker", {}),
        }
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_catalog() -> Catalog:
    return load_catalog()
