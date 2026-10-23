"""Conexión SQLite (WAL) y aplicación idempotente de migraciones (dossier §3.2)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_VERSION_RE = re.compile(r"^(\d+)_.*\.sql$")


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA synchronous = NORMAL")
    return con


def _applied(con: sqlite3.Connection) -> set[int]:
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
    if not exists:
        return set()
    return {row[0] for row in con.execute("SELECT version FROM schema_migrations")}


def migrate(con: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """Aplica en orden las migraciones pendientes. Devuelve las versiones aplicadas en esta llamada."""
    done = _applied(con)
    applied: list[int] = []
    for file in sorted(migrations_dir.glob("*.sql")):
        match = _VERSION_RE.match(file.name)
        if not match or int(match.group(1)) in done:
            continue
        version = int(match.group(1))
        con.executescript(file.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        applied.append(version)
    return applied


def open_database(path: Path | str) -> sqlite3.Connection:
    con = connect(path)
    migrate(con)
    return con
