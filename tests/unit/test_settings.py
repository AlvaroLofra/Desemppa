from pathlib import Path

import pytest

from config.settings import CORE_ROLES, Settings, load_catalog

# Tabla §1.1.1 del dossier: (modo, rol) -> (alias, effort)
EXPECTED = {
    "eco": {
        "triaje": ("gemini_flash", "low"),
        "cribado": ("gemini_flash", "low"),
        "defensa": ("gemini_flash", "medium"),
        "contraparte": ("gemini_flash", "medium"),
        "magistrado": ("gemini_flash", "high"),
        "nli": ("gemini_flash", "low"),
    },
    "equilibrado": {
        "triaje": ("gemini_flash", "low"),
        "cribado": ("gemini_flash", "low"),
        "defensa": ("gemini_flash", "medium"),
        "contraparte": ("gemini_flash", "medium"),
        "magistrado": ("claude_sonnet", "medium"),
        "nli": ("gemini_flash", "low"),
    },
    "pro": {
        "triaje": ("gemini_flash", "low"),
        "cribado": ("gemini_flash", "medium"),
        "defensa": ("claude_sonnet", "medium"),
        "contraparte": ("claude_sonnet", "medium"),
        "magistrado": ("claude_opus", "high"),
        "nli": ("gemini_flash", "low"),
    },
}


def test_profiles_match_dossier_table(catalog):
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
            if role in CORE_ROLES and catalog.models[a.model].provider == "claude"
        )
        assert calls == profile.claude_calls_per_query, name


def _write_config(tmp_path: Path, profiles: str) -> Path:
    src = Path(__file__).resolve().parents[2] / "config" / "models.toml"
    (tmp_path / "models.toml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "profiles.toml").write_text(profiles, encoding="utf-8")
    return tmp_path


def test_unknown_alias_in_profile_fails(tmp_path):
    roles = "\n".join(f'{r} = {{ model = "gemini_flash", effort = "low" }}' for r in CORE_ROLES)
    bad = f'[profiles.x]\nlabel = "X"\nclaude_calls_per_query = 0\n{roles}\n'.replace(
        'triaje = { model = "gemini_flash"', 'triaje = { model = "no_existe"'
    )
    with pytest.raises(ValueError, match="alias desconocido"):
        load_catalog(_write_config(tmp_path, bad))


def test_missing_role_fails(tmp_path):
    bad = '[profiles.x]\nlabel = "X"\nclaude_calls_per_query = 0\ntriaje = { model = "gemini_flash", effort = "low" }\n'
    with pytest.raises(ValueError, match="sin roles"):
        load_catalog(_write_config(tmp_path, bad))


def test_settings_paths_and_loopback(tmp_path):
    s = Settings(IURIS_DATA_DIR=str(tmp_path))
    assert s.sqlite_path == tmp_path / "local_cache.db"
    assert s.claude_lock_path == tmp_path / "claude.lock"
    with pytest.raises(ValueError, match="loopback"):
        Settings(IURIS_DATA_DIR=str(tmp_path), IURIS_HOST="0.0.0.0")
