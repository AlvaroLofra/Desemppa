from storage.database import connect, migrate


def test_sqlite_wal_enabled(tmp_path):
    con = connect(tmp_path / "x.db")
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_migrations_idempotent(tmp_path):
    con = connect(tmp_path / "x.db")
    applied = migrate(con)
    assert applied[:2] == [1, 2] and applied == sorted(applied)
    assert migrate(con) == []
    assert con.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == len(applied)
