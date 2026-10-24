"""Configuración: variables de entorno (.env) + catálogos TOML de modelos y perfiles (dossier §1.1)."""

from __future__ import annotations

import json
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

Effort = Literal["low", "medium", "high"]
Role = Literal["triaje", "cribado", "defensa", "contraparte", "magistrado", "nli", "auditor"]
CORE_ROLES: tuple[Role, ...] = ("triaje", "cribado", "defensa", "contraparte", "magistrado", "nli")


def _default_data_dir() -> Path:
    # Dentro del proyecto (ignorado por git) y no en %LOCALAPPDATA%: Windows redirige %LOCALAPPDATA% para los
    # procesos lanzados desde apps empaquetadas (MSIX) y la app acababa con dos bases de datos distintas según
    # cómo se arrancara.
    return ROOT / "data" / "local"


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


class ProviderSpec(BaseModel):
    """Bloque de config/providers.toml (ver la cabecera de ese fichero)."""

    tipo: Literal["cli", "api_gemini", "api_openai", "api_anthropic"]
    etiqueta: str
    compania: str = "Otra"
    modalidad: Literal["plan", "api"] | None = None
    habilitado: bool = True
    ejecutable: str | None = None
    args: list[str] = Field(default_factory=list)
    system_prompt: Literal["file", "inline"] = "inline"
    system_prompt_args: list[str] = Field(default_factory=list)
    stdin: Literal["text", "agy_ndjson"] = "text"
    parser: str | None = None
    json_schema_args: list[str] = Field(default_factory=list)
    descubrir: list[str] = Field(default_factory=list)
    modelos_conocidos: list[str] = Field(default_factory=list)
    base_url: str | None = None
    api_key_env: str | None = None
    login: str = ""

    @model_validator(mode="after")
    def _cli_completo(self) -> ProviderSpec:
        if self.modalidad is None:
            self.modalidad = "plan" if self.tipo == "cli" else "api"
        if self.tipo == "cli" and not (self.ejecutable and self.args and self.parser):
            raise ValueError("un proveedor 'cli' necesita ejecutable, args y parser")
        peligrosos = [a for a in self.args if "dangerously" in a.lower() or "skip-permissions" in a.lower()]
        if peligrosos:
            # Autoaprobar herramientas dejaría al modelo escribir ficheros o ejecutar comandos en el equipo.
            raise ValueError(f"flags no permitidos en un proveedor: {peligrosos}")
        return self


class ModelSpec(BaseModel):
    provider: str  # clave de config/providers.toml
    model_id: str  # puede contener {effort}: "gemini-3.8-flash-{effort}"
    etiqueta: str = ""
    efforts: list[Effort] = Field(default_factory=lambda: list[Effort](["low", "medium", "high"]))
    rpm: int | None = None
    rpd: int | None = None
    timeout_s: float = 60
    output_dimensionality: int | None = None
    fallbacks: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _compat_cli_model(cls, data: Any) -> Any:
        # Compatibilidad con el formato anterior (cli_model para Claude).
        if isinstance(data, dict) and "model_id" not in data and "cli_model" in data:
            data = {**data, "model_id": data["cli_model"]}
        return data

    def resolved_id(self, effort: str) -> str:
        return self.model_id.replace("{effort}", effort)


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
    providers: dict[str, ProviderSpec]
    models: dict[str, ModelSpec]
    profiles: dict[str, Profile]
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()

    @model_validator(mode="after")
    def _referencias(self) -> Catalog:
        for alias, spec in self.models.items():
            if spec.provider not in self.providers:
                raise ValueError(f"el modelo '{alias}' usa un proveedor desconocido '{spec.provider}'")
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
USER_PROFILES = "user_profiles.toml"  # asignaciones del usuario (excluido de git); se superpone a profiles.toml
USER_MODELS = "user_models.toml"  # modelos o activaciones de proveedor personalizados por el usuario


def _split_profiles(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            **{k: v for k, v in body.items() if k in _PROFILE_META},
            "roles": {k: v for k, v in body.items() if k not in _PROFILE_META},
        }
        for name, body in raw.get("profiles", {}).items()
    }


def load_catalog(config_dir: Path = CONFIG_DIR, *, user_overrides: bool = True) -> Catalog:
    models_raw = tomllib.loads((config_dir / "models.toml").read_text(encoding="utf-8"))
    providers_raw = tomllib.loads((config_dir / "providers.toml").read_text(encoding="utf-8"))
    providers_dict: dict[str, Any] = dict(providers_raw["providers"])
    models_dict: dict[str, Any] = dict(models_raw["models"])
    profiles = _split_profiles(tomllib.loads((config_dir / "profiles.toml").read_text(encoding="utf-8")))
    user_models_path = config_dir / USER_MODELS
    if user_overrides and user_models_path.exists():
        um_raw = tomllib.loads(user_models_path.read_text(encoding="utf-8"))
        for pid, p_override in um_raw.get("providers", {}).items():
            if pid in providers_dict and isinstance(p_override, dict):
                providers_dict[pid] = {**providers_dict[pid], **p_override}
        for alias, m_override in um_raw.get("models", {}).items():
            if isinstance(m_override, dict):
                models_dict[alias] = {**models_dict.get(alias, {}), **m_override}
    user_path = config_dir / USER_PROFILES
    if user_overrides and user_path.exists():
        for name, body in _split_profiles(tomllib.loads(user_path.read_text(encoding="utf-8"))).items():
            if name in profiles:
                profiles[name]["roles"].update(body["roles"])
    return Catalog.model_validate(
        {
            "providers": providers_dict,
            "models": models_dict,
            "profiles": profiles,
            "circuit_breaker": models_raw.get("circuit_breaker", {}),
        }
    )


def save_user_profiles(assignments: dict[str, dict[str, dict[str, str]]], config_dir: Path = CONFIG_DIR) -> Catalog:
    """Valida y guarda {modo: {rol: {model, effort}}} en user_profiles.toml. Devuelve el catálogo resultante."""
    lines = ["# Generado por la página «Modelos» de Iuris-IA. Se superpone a profiles.toml.", ""]
    for modo, roles in assignments.items():
        lines.append(f"[profiles.{modo}]")
        for rol, a in roles.items():
            lines.append(f'{rol} = {{ model = "{a["model"]}", effort = "{a["effort"]}" }}')
        lines.append("")
    path = config_dir / USER_PROFILES
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        return load_catalog(config_dir)
    except ValueError:
        if previous is None:
            path.unlink()
        else:
            path.write_text(previous, encoding="utf-8")
        raise


def _toml_str(value: str) -> str:
    """Cadena básica TOML: el escape de JSON (comillas, barras, controles) es compatible."""
    return json.dumps(value, ensure_ascii=False)


def save_user_provider_or_model(
    *,
    provider_overrides: dict[str, dict[str, Any]] | None = None,
    model_overrides: dict[str, dict[str, Any]] | None = None,
    config_dir: Path = CONFIG_DIR,
) -> Catalog:
    """Guarda activación de proveedores o modelos personalizados en user_models.toml y valida el catálogo."""
    path = config_dir / USER_MODELS
    existing: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    provs: dict[str, Any] = dict(existing.get("providers", {}))
    mods: dict[str, Any] = dict(existing.get("models", {}))
    if provider_overrides:
        for pid, data in provider_overrides.items():
            provs[pid] = {**provs.get(pid, {}), **data}
    if model_overrides:
        for alias, data in model_overrides.items():
            mods[alias] = {**mods.get(alias, {}), **data}
    lines = ["# Generado por la página «Modelos» de Iuris-IA (excluido de git).", ""]
    for pid, pdata in provs.items():
        lines.append(f"[providers.{pid}]")
        for k, v in pdata.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, str):
                lines.append(f"{k} = {_toml_str(v)}")
        lines.append("")
    for alias, mdata in mods.items():
        lines.append(f"[models.{alias}]")
        for k, v in mdata.items():
            if isinstance(v, str):
                lines.append(f"{k} = {_toml_str(v)}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            elif isinstance(v, list):
                items = ", ".join(_toml_str(str(x)) for x in v)
                lines.append(f"{k} = [{items}]")
        lines.append("")
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        return load_catalog(config_dir)
    except ValueError:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(previous, encoding="utf-8")
        raise


def reset_user_profiles(config_dir: Path = CONFIG_DIR) -> None:
    """Restablece solo las asignaciones de modelos por modo (no toca proveedores ni modelos personalizados)."""
    (config_dir / USER_PROFILES).unlink(missing_ok=True)


def reset_user_models(config_dir: Path = CONFIG_DIR) -> None:
    (config_dir / USER_MODELS).unlink(missing_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_catalog() -> Catalog:
    return load_catalog()
