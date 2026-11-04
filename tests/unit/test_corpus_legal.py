"""Corpus legal local versionado: ingesta incremental, identidad de la norma, búsqueda a la fecha y vectores.

El BOE se simula (sin red). Los textos de los artículos son SINTÉTICOS: sirven para probar la mecánica (versiones,
vigencia, búsqueda), no son Derecho."""

from __future__ import annotations

import hashlib
import math
from datetime import date

import httpx
import pytest

from connectors.boe_client import BOEClient, BOEError, BOERepository, consulta_fts_legal
from connectors.corpus_legal import CorpusLegal, es_precepto
from connectors.embeddings import LocalEmbedder, crear_embedder
from connectors.recuperador_legislacion import RecuperadorLegislacion
from core.materias import id_norma, normas, nucleo
from storage.lance_schema import LegislacionStore

LAU = id_norma("LAU")
CCOM = id_norma("CCOM")


def _version(fecha: str, texto: str) -> str:
    parrafos = "".join(f'<p class="parrafo">{t}</p>' for t in texto.split("|"))
    attrs = f'id_norma="BOE-A-1994-26003" fecha_publicacion="{fecha}" fecha_vigencia="{fecha}"'
    return f"<version {attrs}>{parrafos}</version>"


BLOQUES = {
    "ti": ("TÍTULO I", "encabezado", [("19950101", "TÍTULO I|Disposiciones generales")]),
    "a1": (
        "Artículo 1",
        "precepto",
        [("19950101", "Artículo 1. Ámbito.|La presente ley regula el arrendamiento de fincas urbanas.")],
    ),
    "ci": ("CAPÍTULO I", "encabezado", [("19950101", "CAPÍTULO I|De la fianza")]),
    "a2": (
        "Artículo 2",
        "precepto",
        [
            ("19950101", "Artículo 2. Fianza.|El arrendador devolverá la fianza en el plazo de quince días."),
            ("20200301", "Artículo 2. Fianza.|El arrendador devolverá la fianza en el plazo de treinta días."),
        ],
    ),
    "a3": (
        "Artículo 3",
        "precepto",
        [("20220101", "Artículo 3. Desistimiento.|El inquilino podrá desistir del contrato.")],
    ),
    "dt1": (
        "Disposición transitoria primera",
        "precepto",
        [("19950101", "Disposición transitoria primera.|Contratos anteriores.")],
    ),
    "preambulo": ("", "preambulo", [("19950101", "Exposición de motivos")]),
}


def _bloque_xml(id_bloque: str) -> str:
    titulo, tipo, versiones = BLOQUES[id_bloque]
    cuerpo = "".join(_version(f, t) for f, t in versiones)
    return f'<bloque id="{id_bloque}" tipo="{tipo}" titulo="{titulo}">{cuerpo}</bloque>'


def _respuesta(data: str) -> bytes:
    estado = "<status><code>200</code><text>ok</text></status>"
    return f'<?xml version="1.0" encoding="utf-8"?><response>{estado}<data>{data}</data></response>'.encode()


class BOEFalso:
    def __init__(self, *, texto_completo: bool = False, titulo: str = "Ley 29/1994, de Arrendamientos Urbanos") -> None:
        self.texto_completo = texto_completo
        self.titulo = titulo
        self.fechas = {k: "19950101" for k in BLOQUES}
        self.llamadas: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.llamadas.append(path)
        nid = path.split("/id/")[1].split("/")[0]
        if path.endswith("/metadatos"):
            meta = {
                "identificador": nid,
                "titulo": self.titulo,
                "rango": {"texto": "Ley"},
                "ambito": {"texto": "Estatal"},
                "estatus_derogacion": "N",
            }
            return httpx.Response(200, json={"data": [meta]})
        if path.endswith("/texto/indice"):
            bloques = [{"id": k, "titulo": v[0], "fecha_actualizacion": self.fechas[k]} for k, v in BLOQUES.items()]
            return httpx.Response(200, json={"data": {"bloque": bloques}})
        if "/texto/bloque/" in path:
            bid = path.rsplit("/", 1)[1]
            return httpx.Response(200, content=_respuesta(_bloque_xml(bid))) if bid in BLOQUES else httpx.Response(404)
        if path.endswith("/texto"):
            if not self.texto_completo:
                return httpx.Response(404)
            return httpx.Response(
                200, content=_respuesta("<texto>" + "".join(_bloque_xml(k) for k in BLOQUES) + "</texto>")
            )
        return httpx.Response(404)

    def cliente(self) -> BOEClient:
        http = httpx.AsyncClient(base_url="https://boe.test", transport=httpx.MockTransport(self.handler))
        return BOEClient(client=http, max_rps=10_000)


class EmbedderFalso:
    """Bolsa de palabras con hash: determinista y sin red."""

    model = "falso-bow"
    dim = 64

    async def embed(self, texts, task):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def _corpus(db, boe: BOEFalso, **kw) -> CorpusLegal:
    client = boe.cliente()
    return CorpusLegal(db, BOERepository(db, client), client, **kw)


async def test_ingesta_bloque_a_bloque_con_ubicacion_y_estado(db):
    boe = BOEFalso()
    corpus = _corpus(db, boe)
    res = await corpus.ingerir("LAU")
    assert (res.modo, res.preceptos, res.descargados, res.errores) == ("bloques", 4, 4, 0)
    assert not any(p.endswith("/bloque/preambulo") or p.endswith("/bloque/ti") for p in boe.llamadas)
    ubic = dict(db.execute("SELECT id_bloque, ubicacion FROM boe_corpus_bloques").fetchall())
    assert ubic["a1"] == "TÍTULO I" and ubic["a2"] == "TÍTULO I > CAPÍTULO I"
    fila = next(f for f in corpus.estado() if f["alias"] == "LAU")
    assert (fila["estado"], fila["preceptos_ok"], fila["nucleo"]) == ("completa", 4, True)
    assert corpus.ids_descargados() == [LAU]


async def test_segunda_ingesta_solo_descarga_lo_que_cambio(db):
    boe = BOEFalso()
    corpus = _corpus(db, boe)
    await corpus.ingerir("LAU")
    boe.llamadas.clear()
    res = await corpus.ingerir("LAU")
    assert res.sin_cambios == 4 and not [p for p in boe.llamadas if "/bloque/" in p]
    boe.fechas["a2"] = "20200301"  # el índice oficial dice que a2 cambió
    boe.llamadas.clear()
    res = await corpus.ingerir("LAU")
    assert [p.rsplit("/", 1)[1] for p in boe.llamadas if "/bloque/" in p] == ["a2"]
    assert res.descargados == 1


async def test_texto_completo_en_una_peticion_con_rubricas(db):
    boe = BOEFalso(texto_completo=True)
    corpus = _corpus(db, boe)
    corpus.UMBRAL_TEXTO_COMPLETO = 0
    res = await corpus.ingerir("LAU")
    assert res.modo == "texto_completo" and res.descargados == 4
    assert not [p for p in boe.llamadas if "/bloque/" in p]
    ubic = dict(db.execute("SELECT id_bloque, ubicacion FROM boe_corpus_bloques").fetchall())
    assert ubic["a2"] == "TÍTULO I Disposiciones generales > CAPÍTULO I De la fianza"


async def test_identificador_equivocado_lo_desmiente_el_boe(db):
    """CCOM se añadió sin poder consultar el BOE: si su id no fuera el Código de Comercio, no se usa nunca."""
    assert normas()["CCOM"].get("verificado") is False and "CCOM" in nucleo()
    corpus = _corpus(db, BOEFalso(titulo="Ley de algo completamente distinto"))
    res = await corpus.ingerir("CCOM")
    assert res.errores == 1 and "no es la norma esperada" in res.avisos[0]
    assert next(f for f in corpus.estado() if f["alias"] == "CCOM")["estado"] == "error"
    assert db.execute("SELECT COUNT(*) FROM boe_bloques").fetchone()[0] == 0
    with pytest.raises(BOEError):
        await BOERepository(db, BOEFalso(titulo="Otra ley").cliente()).get_articulo(CCOM, "1")
    ok = _corpus(
        db, BOEFalso(titulo="Real Decreto de 22 de agosto de 1885 por el que se publica el Código de Comercio.")
    )
    assert (await ok.ingerir("CCOM")).errores == 0


async def test_busqueda_a_la_fecha_sin_anacronismos(db):
    corpus = _corpus(db, BOEFalso())
    await corpus.ingerir("LAU")
    repo = BOERepository(db, BOEFalso().cliente())
    antes = repo.buscar_a_fecha("devolución de la fianza", date(2010, 6, 1))
    despues = repo.buscar_a_fecha("devolución de la fianza", date(2021, 6, 1))
    assert antes[0].id_bloque == "a2" and "quince" in antes[0].inicio and antes[0].vigencia_hasta == date(2020, 3, 1)
    assert despues[0].id_bloque == "a2" and "treinta" in despues[0].inicio and despues[0].vigencia_hasta is None
    assert antes[0].ubicacion == "TÍTULO I > CAPÍTULO I"
    # El art. 3 entra en vigor en 2022: no existe para hechos de 2021.
    assert not repo.buscar_a_fecha("desistir inquilino", date(2021, 6, 1))
    assert repo.buscar_a_fecha("desistir inquilino", date(2022, 6, 1))[0].id_bloque == "a3"
    assert not repo.buscar_a_fecha("fianza", date(2021, 6, 1), normas=["BOE-A-1889-4763"])


def test_consulta_fts_quita_palabras_vacias_y_usa_raices():
    q = consulta_fts_legal("¿Me pueden devolver la fianza del arrendamiento?")
    assert '"devolver"' in q and '"fianza"' in q and '"arrendamiento"' in q and '"arrendamie"*' in q
    assert '"pueden"' not in q and '"del"' not in q
    assert consulta_fts_legal("de la que") == '""'


def test_clasificacion_de_preceptos():
    assert es_precepto("Artículo 1902") and es_precepto("Disposición adicional primera")
    assert not es_precepto("TÍTULO I") and not es_precepto("Preámbulo")


async def test_vectores_incrementales_y_filtrados_por_vigencia(db, tmp_path):
    emb = EmbedderFalso()
    store = LegislacionStore(tmp_path / "lance", emb.dim)
    corpus = _corpus(db, BOEFalso(), store=store, embedder=emb)
    res = await corpus.ingerir("LAU")
    assert res.vectores_nuevos == store.count() > 0
    assert await corpus.indexar_vectores(LAU) == 0  # nada cambió: no se recalcula
    [v] = await emb.embed(["inquilino desistir contrato"], "RETRIEVAL_QUERY")
    assert all(r["id_bloque"] != "a3" for r in store.search(v, fecha=date(2021, 1, 1)))
    assert store.search(v, fecha=date(2023, 1, 1))[0]["id_bloque"] == "a3"


async def test_recuperador_fusiona_bm25_y_vectores_a_la_fecha(db, tmp_path):
    emb = EmbedderFalso()
    store = LegislacionStore(tmp_path / "lance", emb.dim)
    boe = BOEFalso()
    corpus = _corpus(db, boe, store=store, embedder=emb)
    await corpus.ingerir("LAU")
    rec = RecuperadorLegislacion(BOERepository(db, boe.cliente()), store=store, embedder=emb)
    assert rec.vectorial
    cands = await rec.buscar(["fianza devolver arrendador", "plazo para devolver la fianza"], date(2010, 1, 1))
    assert cands[0].precepto.id_bloque == "a2" and cands[0].fuentes == {"bm25", "vector"}
    assert "quince" in cands[0].precepto.inicio
    assert all(c.precepto.id_bloque != "a3" for c in cands)
    assert await rec.buscar(["", "  "], date(2010, 1, 1)) == []
    solo_bm25 = RecuperadorLegislacion(BOERepository(db, boe.cliente()))
    assert not solo_bm25.vectorial
    assert (await solo_bm25.buscar(["fianza"], date(2021, 1, 1)))[0].fuentes == {"bm25"}


async def test_embedder_local_con_prefijos_y_fabrica(monkeypatch):
    class Motor:
        dim = 3
        visto: list[str] = []

        def embed(self, textos):
            self.visto.extend(textos)
            return [[1.0, 0.0, 0.0] for _ in textos]

    motor = Motor()
    emb = LocalEmbedder("google/embeddinggemma-300m", motor=motor)
    assert await emb.embed(["despido"], "RETRIEVAL_QUERY") == [[1.0, 0.0, 0.0]]
    await emb.embed(["texto"], "RETRIEVAL_DOCUMENT")
    assert motor.visto == ["task: search result | query: despido", "title: none | text: texto"]
    monkeypatch.setenv("IURIS_EMBEDDINGS", "no")
    assert crear_embedder(None) is None
