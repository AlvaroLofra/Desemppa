import shutil
from pathlib import Path

import pytest

from config.settings import (
    CORE_ROLES,
    Settings,
    load_catalog,
    reset_user_models,
    reset_user_profiles,
    save_user_profiles,
    save_user_provider_or_model,
)

CONFIG = Path(__file__).resolve().parents[2] / "config"

# Perfiles por defecto (config/profiles.toml): (modo, rol) -> (alias, effort)
EXPECTED = {
    "eco": {
        "triaje": ("agy_gemini_flash", "low"),
        "cribado": ("agy_gemini_flash", "low"),
        "defensa": ("agy_gemini_flash", "medium"),
        "contraparte": ("agy_gemini_flash", "medium"),
        "magistrado": ("agy_gemini_flash", "medium"),
        "nli": ("agy_gemini_flash", "low"),
    },
    "equilibrado": {
        "magistrado": ("claude_sonnet", "medium"),
        "defensa": ("agy_gemini_flash", "medium"),
    },
    "pro": {
        "defensa": ("claude_sonnet", "medium"),
        "contraparte": ("claude_sonnet", "medium"),
        "magistrado": ("agy_gemini_argon", "high"),
    },
}


def test_profiles_match_defaults(catalog):
    for mode, roles in EXPECTED.items():
        for role, (alias, effort) in roles.items():
            got = catalog.profiles[mode].roles[role]
            assert (got.model, got.effort) == (alias, effort), (mode, role)
    assert set(catalog.profiles) == {"eco", "equilibrado", "pro", "auditoria"}
    assert all(r in catalog.profiles["auditoria"].roles for r in CORE_ROLES)
    assert catalog.default_profile() == "equilibrado"


def test_claude_calls_per_query_consistent(catalog):
    for name, profile in catalog.profiles.items():
        calls = sum(
            1
            for role, a in profile.roles.items()
            if role in CORE_ROLES and catalog.models[a.model].provider == "claude_cli"
        )
        assert calls == profile.claude_calls_per_query, name


def test_providers_loaded_and_models_reference_them(catalog):
    assert {
        "gemini_api",
        "claude_cli",
        "antigravity_cli",
        "codex_cli",
        "openai_api",
        "anthropic_api",
        "xai_api",
        "deepseek_api",
        "mistral_api",
        "openrouter_api",
    } <= set(catalog.providers)
    assert catalog.providers["codex_cli"].habilitado is False
    assert all(m.provider in catalog.providers for m in catalog.models.values())
    assert catalog.models["agy_gemini_flash"].resolved_id("low") == "gemini-3.8-flash-low"
    assert catalog.models["agy_gemini_flash"].resolved_id("high") == "gemini-3.8-flash-high"
    assert catalog.models["agy_gemini_argon"].resolved_id("high") == "gemini-4-argon-high"


def _config_copy(tmp_path: Path) -> Path:
    for name in ("models.toml", "providers.toml", "profiles.toml"):
        shutil.copy(CONFIG / name, tmp_path / name)
    return tmp_path


def test_unknown_alias_in_profile_fails(tmp_path):
    cfg = _config_copy(tmp_path)
    text = (
        (cfg / "profiles.toml")
        .read_text(encoding="utf-8")
        .replace(
            'triaje      = { model = "agy_gemini_flash", effort = "low" }',
            'triaje = { model = "no_existe", effort = "low" }',
            1,
        )
    )
    (cfg / "profiles.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="alias desconocido"):
        load_catalog(cfg)


def test_unknown_provider_fails(tmp_path):
    cfg = _config_copy(tmp_path)
    text = (cfg / "models.toml").read_text(encoding="utf-8").replace('provider = "gemini_api"', 'provider = "nope"', 1)
    (cfg / "models.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="proveedor desconocido"):
        load_catalog(cfg)


def test_user_profiles_overlay_save_and_reset(tmp_path):
    cfg = _config_copy(tmp_path)
    cat = save_user_profiles({"eco": {"magistrado": {"model": "claude_opus", "effort": "high"}}}, cfg)
    assert cat.profiles["eco"].roles["magistrado"].model == "claude_opus"
    assert cat.profiles["eco"].roles["triaje"].model == "agy_gemini_flash"  # el resto se conserva
    assert load_catalog(cfg, user_overrides=False).profiles["eco"].roles["magistrado"].model == "agy_gemini_flash"
    with pytest.raises(ValueError):  # inválido: no se guarda y se conserva lo anterior
        save_user_profiles({"eco": {"magistrado": {"model": "fantasma", "effort": "low"}}}, cfg)
    assert load_catalog(cfg).profiles["eco"].roles["magistrado"].model == "claude_opus"
    reset_user_profiles(cfg)
    assert load_catalog(cfg).profiles["eco"].roles["magistrado"].model == "agy_gemini_flash"


def test_settings_paths_and_loopback(tmp_path):
    s = Settings(IURIS_DATA_DIR=str(tmp_path))
    assert s.sqlite_path == tmp_path / "local_cache.db"
    with pytest.raises(ValueError, match="loopback"):
        Settings(IURIS_DATA_DIR=str(tmp_path), IURIS_HOST="0.0.0.0")


def test_default_data_dir_is_inside_project(monkeypatch):
    monkeypatch.delenv("IURIS_DATA_DIR", raising=False)
    s = Settings()
    assert s.data_dir == Path(__file__).resolve().parents[2] / "data" / "local"


def test_dangerous_cli_flags_are_rejected(tmp_path):
    cfg = _config_copy(tmp_path)
    text = (
        (cfg / "providers.toml")
        .read_text(encoding="utf-8")
        .replace('"--disable-slash-commands",', '"--disable-slash-commands", "--dangerously-skip-permissions",', 1)
    )
    (cfg / "providers.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="no permitidos"):
        load_catalog(cfg)


def test_user_models_escapes_strings_and_survives_profile_reset(tmp_path):
    cfg = _config_copy(tmp_path)
    (cfg / "user_models.toml").unlink(missing_ok=True)
    etiqueta = r'Modelo "raro" \ con barra'
    cat = save_user_provider_or_model(
        model_overrides={
            "mi_modelo": {"provider": "antigravity_cli", "model_id": "gemini-3.8-flash-{effort}", "etiqueta": etiqueta}
        },
        provider_overrides={"codex_cli": {"habilitado": True}},
        config_dir=cfg,
    )
    assert cat.models["mi_modelo"].etiqueta == etiqueta and cat.providers["codex_cli"].habilitado
    reset_user_profiles(cfg)  # restablecer asignaciones NO borra modelos ni proveedores personalizados
    assert "mi_modelo" in load_catalog(cfg).models
    reset_user_models(cfg)
    assert "mi_modelo" not in load_catalog(cfg).models and not load_catalog(cfg).providers["codex_cli"].habilitado
