"""Humo de scripts/copia_seguridad.py: crea una copia cifrada y la restaura sin pérdida."""

import sqlite3
from datetime import datetime

from scripts.copia_seguridad import crear, restaurar


def test_copia_y_restauracion(tmp_path):
    datos = tmp_path / "local"
    (datos / "logs").mkdir(parents=True)
    (datos / "sandboxes" / "x").mkdir(parents=True)
    (datos / "logs" / "iuris.log").write_text("hola", encoding="utf-8")
    (datos / "sandboxes" / "x" / "tmp.txt").write_text("no se copia", encoding="utf-8")
    con = sqlite3.connect(datos / "local_cache.db")
    con.execute("CREATE TABLE t(v TEXT)")
    con.execute("INSERT INTO t VALUES ('dato')")
    con.commit()
    con.close()
    copias = tmp_path / "copias"
    for i in range(12):
        ruta = crear(datos, copias, datetime(2026, 10, 25, 12, 0, i))
    assert len(list(copias.glob("*.bak"))) == 10  # solo se conservan las 10 últimas
    assert b"dato" not in ruta.read_bytes()  # cifrada
    out = restaurar(ruta, tmp_path / "restaurado")
    assert (out / "logs" / "iuris.log").read_text(encoding="utf-8") == "hola"
    assert not (out / "sandboxes").exists()
    con = sqlite3.connect(out / "local_cache.db")
    assert con.execute("SELECT v FROM t").fetchone() == ("dato",)
    con.close()
