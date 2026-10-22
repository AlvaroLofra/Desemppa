"""Sanidad del entorno (Fase 0): librerías clave importables, FTS5 disponible y migración aplicable."""

import importlib
import sqlite3
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "storage" / "migrations" / "0001_init.sql"


@pytest.mark.parametrize("module", ["fastapi", "pydantic", "lancedb", "rapidfuzz", "google.genai"])
def test_key_libraries_import(module: str) -> None:
    importlib.import_module(module)


def test_pydantic_v2() -> None:
    import pydantic

    assert int(pydantic.VERSION.split(".")[0]) >= 2


def test_sqlite_supports_fts5() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='unicode61 remove_diacritics 2')")
    con.execute("INSERT INTO t VALUES ('Artículo 36 de la Ley de Arrendamientos Urbanos')")
    assert con.execute("SELECT count(*) FROM t WHERE t MATCH 'articulo'").fetchone()[0] == 1


def test_initial_migration_applies(tmp_path: Path) -> None:
    con = sqlite3.connect(tmp_path / "test.db")
    con.executescript(MIGRATION.read_text(encoding="utf-8"))
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "boe_bloques",
        "cendoj_sentencias",
        "convenios_cache",
        "municipios_festivos",
        "sesiones_consultas",
        "llm_calls_ledger",
        "boe_bloques_fts",
    } <= names
