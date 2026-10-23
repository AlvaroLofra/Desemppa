import sqlite3

from scripts.migrar_datos import copiar
from storage.database import open_database


def test_copiar_preserva_consultas_y_respalda(tmp_path):
    origen = tmp_path / "viejo"
    origen.mkdir()
    con = open_database(origen / "local_cache.db")  # WAL activo, como en la app
    con.execute(
        "INSERT INTO sesiones_consultas(consulta_id, modo_utilizado, estado, consulta_usuario_cifrada, "
        "consulta_seudonimizada) VALUES ('c1', 'eco', 'CERTIFICADA', x'00', 'texto')"
    )
    destino = tmp_path / "nuevo"
    destino.mkdir()
    (destino / "local_cache.db").write_bytes(b"previo")
    copiar(origen, destino)
    assert (destino / "local_cache.db.antes_de_migrar").read_bytes() == b"previo"
    copia = sqlite3.connect(destino / "local_cache.db")
    assert copia.execute("SELECT consulta_id FROM sesiones_consultas").fetchall() == [("c1",)]
