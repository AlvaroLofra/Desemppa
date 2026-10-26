"""Historial: renombrar, archivar y borrar consultas."""

from tests.contract.test_red_local import TEXTO, _activar, _dueno, _invitado, app  # noqa: F401  (fixture)


def test_renombrar_archivar_y_borrar(app):  # noqa: F811
    with _dueno(app) as cli:
        s = cli.app.state.services
        h = {"X-Iuris-Token": s.token}
        cid = s.pipeline.store.create(TEXTO, "eco")
        s.pipeline.bus.emit(cid, "estado", {"estado": "RECIBIDA"})

        r = cli.patch(f"/api/consultas/{cid}", headers=h, json={"titulo": "Fianza del piso de Juan"})
        assert r.status_code == 200, r.text
        assert r.json()["titulo"] == "Fianza del piso de Juan" and r.json()["renombrada"] is True
        # El título se guarda cifrado, no en claro
        crudo = s.pipeline.store._con.execute(  # noqa: SLF001
            "SELECT titulo_cifrado FROM sesiones_consultas WHERE consulta_id = ?", (cid,)
        ).fetchone()[0]
        assert b"Juan" not in crudo or crudo.startswith(b"PLAIN1:")  # PLAIN1: solo fuera de Windows (sin DPAPI)

        assert cli.patch(f"/api/consultas/{cid}", headers=h, json={"archivada": True}).json()["archivada"] is True
        assert (
            cli.patch(f"/api/consultas/{cid}", headers=h, json={"titulo": ""}).json()["titulo"].startswith("El casero")
        )

        assert cli.patch(f"/api/consultas/{cid}", json={"archivada": False}).status_code == 403  # sin token
        assert cli.delete(f"/api/consultas/{cid}", headers=h).status_code == 204
        assert cli.get(f"/api/consultas/{cid}").status_code == 404
        assert cli.get("/api/consultas").json() == []
        assert s.pipeline.bus.history(cid) == []  # eventos borrados en cascada
        assert cli.delete(f"/api/consultas/{cid}", headers=h).status_code == 404


def test_invitado_no_toca_consultas_ajenas(app):  # noqa: F811
    with _dueno(app) as dueno:
        _activar(dueno)
        ajena = dueno.app.state.services.pipeline.store.create(TEXTO, "eco")
        with _invitado(app) as inv:
            h = {"X-Iuris-Token": inv.get("/api/token").json()["token"]}
            assert inv.patch(f"/api/consultas/{ajena}", headers=h, json={"titulo": "x"}).status_code == 404
            assert inv.delete(f"/api/consultas/{ajena}", headers=h).status_code == 404
        assert len(dueno.get("/api/consultas").json()) == 1
