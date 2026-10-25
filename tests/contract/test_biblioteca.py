"""Biblioteca de documentos reutilizables y QR de la red local."""

from tests.contract.test_red_local import _activar, _dueno, _invitado, app  # noqa: F401  (fixture)

SENTENCIA = b"SENTENCIA. Fundamentos de derecho: el arrendatario no responde del desgaste por el uso ordinario."


def _subir(cli, nombre="sentencia.txt", datos=SENTENCIA):
    s = cli.app.state.services
    return cli.post(
        "/api/biblioteca",
        headers={"X-Iuris-Token": s.token},
        files={"archivo": (nombre, datos, "text/plain")},
        data={"permitir_envio": "true"},
    )


def test_guardar_listar_ver_y_borrar(app):  # noqa: F811
    with _dueno(app) as cli:
        r = _subir(cli)
        assert r.status_code == 201, r.text
        doc = r.json()
        assert doc["nombre"] == "sentencia.txt" and doc["permitir_envio"] is True and doc["caracteres"] > 50
        assert _subir(cli, nombre="otra.txt").json()["doc_id"] == doc["doc_id"]  # mismo contenido: no se duplica
        assert [d["doc_id"] for d in cli.get("/api/biblioteca").json()] == [doc["doc_id"]]
        assert "desgaste" in cli.get(f"/api/biblioteca/{doc['doc_id']}").json()["texto"]
        token = {"X-Iuris-Token": cli.app.state.services.token}
        assert cli.delete(f"/api/biblioteca/{doc['doc_id']}", headers=token).json() == {"ok": True}
        assert cli.get("/api/biblioteca").json() == []
        assert cli.get(f"/api/biblioteca/{doc['doc_id']}").status_code == 404


def test_adjuntar_crea_una_copia_para_la_consulta(app):  # noqa: F811
    with _dueno(app) as cli:
        doc = _subir(cli).json()
        token = {"X-Iuris-Token": cli.app.state.services.token}
        a1 = cli.post(f"/api/biblioteca/{doc['doc_id']}/adjuntar", headers=token).json()
        a2 = cli.post(f"/api/biblioteca/{doc['doc_id']}/adjuntar", headers=token).json()
        assert a1["adjunto_id"] != a2["adjunto_id"] and a1["nombre"] == "sentencia.txt"
        r = cli.post(
            "/api/consultas",
            headers=token,
            json={"texto": "El casero no me devuelve la fianza", "modo": "eco", "adjuntos": [a1["adjunto_id"]]},
        )
        c = cli.app.state.services.pipeline.store.get(r.json()["consulta_id"])
        assert [a["nombre"] for a in c.adjuntos] == ["sentencia.txt"]
        cli.delete(f"/api/biblioteca/{doc['doc_id']}", headers=token)
        assert cli.app.state.services.pipeline.store.get(c.consulta_id).adjuntos  # la consulta conserva su copia


def test_escrituras_exigen_token_y_formato(app):  # noqa: F811
    with _dueno(app) as cli:
        r = cli.post("/api/biblioteca", files={"archivo": ("a.txt", SENTENCIA, "text/plain")})
        assert r.status_code == 403
        r = _subir(cli, nombre="foto.png", datos=b"\x89PNG....")
        assert r.status_code == 415


def test_invitado_no_ve_la_biblioteca_ni_el_qr(app):  # noqa: F811
    with _dueno(app) as dueno:
        _activar(dueno)
        _subir(dueno)
        with _invitado(app) as inv:
            assert inv.get("/api/biblioteca").status_code == 403
            assert inv.get("/api/red/qr").status_code == 403


def test_qr_solo_con_la_red_activa(app):  # noqa: F811
    with _dueno(app) as dueno:
        assert dueno.get("/api/red/qr").status_code == 409
        _activar(dueno)
        r = dueno.get("/api/red/qr")
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
        assert r.text.lstrip().startswith("<svg")


def test_aviso_de_reforma_de_un_articulo_citado(app):  # noqa: F811
    from datetime import date

    from connectors.boe_models import Bloque, BloqueVersion

    sid = "BOE:BOE-A-1994-26003:a36:2019-03-06"
    with _dueno(app) as cli:
        s = cli.app.state.services
        store = s.pipeline.store
        cid = store.create("El casero no me devuelve la fianza", "eco")
        store.save(cid, dictamen_json={"dictamen": {"fundamentos": [{"source_id": sid}], "afirmaciones": []}})

        async def bloque(id_norma, id_bloque, refresh=False):  # noqa: ARG001
            versiones = [
                BloqueVersion(id_norma_modificadora="x", fecha_publicacion=None, vigencia_desde=d, texto="t")
                for d in (date(2019, 3, 6), date(2099, 1, 1))
            ]
            return Bloque(id_norma=id_norma, id_bloque=id_bloque, titulo="Artículo 36", versiones=versiones)

        s.pipeline.boe.get_bloque = bloque
        cambios = cli.get(f"/api/consultas/{cid}/vigencia").json()
        assert cambios == [
            {"source_id": sid, "titulo": "Artículo 36", "version_citada": "2019-03-06", "version_actual": "2099-01-01"}
        ]


def test_panel_de_salud(app):  # noqa: F811
    with _dueno(app) as cli:
        s = cli.app.state.services
        s.ledger.record(
            consulta_id=None,
            fase="magistrado",
            rol="magistrado",
            proveedor="gemini",
            modelo="m1",
            effort="medium",
            latencia_ms=2000,
            ok=False,
            error_tipo="EmptyResponse",
        )
        s.ledger.record(
            consulta_id=None,
            fase="magistrado",
            rol="magistrado",
            proveedor="gemini",
            modelo="m1",
            effort="medium",
            latencia_ms=4000,
            ok=True,
        )
        m = cli.get("/api/salud?dias=1").json()["modelos"][0]
        assert (m["modelo"], m["llamadas"], m["correctas"], m["vacias"], m["latencia_media_s"]) == ("m1", 2, 1, 1, 4.0)
        with _invitado(app) as inv:
            _activar(cli)
            assert inv.get("/api/salud").status_code == 403
