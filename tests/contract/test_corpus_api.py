"""API del corpus legal: estado, descarga en segundo plano (solo el dueño, con token) y búsqueda a la fecha."""

import time

from connectors.boe_client import BOERepository
from connectors.corpus_legal import CorpusLegal
from connectors.recuperador_legislacion import RecuperadorLegislacion
from tests.contract.test_red_local import _activar, _dueno, _invitado, app  # noqa: F401  (fixture)
from tests.unit.test_corpus_legal import BOEFalso


def _con_boe_falso(cli):
    p = cli.app.state.services.pipeline
    con = p.boe._con
    cliente = BOEFalso().cliente()
    p.corpus = CorpusLegal(con, BOERepository(con, cliente), cliente)
    p.legislacion = RecuperadorLegislacion(BOERepository(con, cliente))


def test_estado_inicial_del_nucleo(app):  # noqa: F811
    with _dueno(app) as cli:
        r = cli.get("/api/corpus").json()
        alias = {n["alias"]: n for n in r["normas"]}
        assert {"CC", "CP", "ET", "LEC", "LECRIM", "TRLC", "LPAC", "CCOM"} <= set(alias)
        assert all(n["estado"] == "pendiente" for n in r["normas"]) and r["en_curso"] is None
        assert alias["CCOM"]["verificado"] is False and alias["CC"]["verificado"] is True
        assert r["vectorial"] is False


def test_descarga_en_segundo_plano_y_busqueda(app):  # noqa: F811
    with _dueno(app) as cli:
        _con_boe_falso(cli)
        token = {"X-Iuris-Token": cli.app.state.services.token}
        assert cli.post("/api/corpus/ingerir", json={"normas": ["LAU"]}).status_code in (401, 403)
        assert cli.post("/api/corpus/ingerir", headers=token, json={"normas": ["NOEXISTE"]}).status_code == 422
        r = cli.post("/api/corpus/ingerir", headers=token, json={"normas": ["LAU"]})
        assert r.status_code == 202 and r.json()["normas"] == ["LAU"]
        for _ in range(100):
            estado = cli.get("/api/corpus").json()
            if estado["en_curso"] is None:
                break
            time.sleep(0.05)
        assert estado["ultimo"] == [{"alias": "LAU", "descargados": 4, "errores": 0}]
        assert next(n for n in estado["normas"] if n["alias"] == "LAU")["estado"] == "completa"
        hits = cli.get("/api/corpus/buscar", params={"q": "devolver la fianza", "fecha": "2010-01-01"}).json()
        assert hits[0]["titulo"] == "Artículo 2" and "quince" in hits[0]["extracto"] and hits[0]["alias"] == "LAU"
        assert hits[0]["vigencia_hasta"] == "2020-03-01" and hits[0]["url"].endswith("#a2")


def test_el_invitado_no_ve_ni_descarga_el_corpus(app):  # noqa: F811
    with _dueno(app) as dueno, _invitado(app) as inv:
        _activar(dueno)
        assert inv.get("/api/corpus").status_code == 403
        assert inv.get("/api/corpus/buscar", params={"q": "fianza"}).status_code == 403
