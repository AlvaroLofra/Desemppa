from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import Catalog, load_catalog  # noqa: E402
from storage.database import open_database  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    con = open_database(tmp_path / "test.db")
    yield con
    con.close()


@pytest.fixture
def claude_fixture() -> callable:
    def _load(name: str) -> list[str]:
        return (FIXTURES / "claude_stream" / name).read_text(encoding="utf-8").splitlines()

    return _load
