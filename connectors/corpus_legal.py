"""Corpus legal local: los grandes cuerpos legales del BOE enteros y con TODAS sus versiones.

Por qué: hasta ahora solo se descargaban los artículos que el catálogo de submaterias pedía. Con el corpus descargado,
la ingesta puede BUSCAR el precepto pertinente (BM25 + vectores) en la redacción vigente a la fecha de los hechos y
el LLM solo elige de esa lista cerrada (docs/vision.md §3).

- Ingesta incremental: el índice oficial da la fecha de actualización de cada bloque; solo se descarga lo que cambió.
- Reanudable: lo ya guardado no se vuelve a pedir.
- Identidad comprobada en tiempo real (`BOERepository.ensure_norma` + `titulo_boe_contiene`).
- Primero se intenta el texto completo en una petición; si falla, bloque a bloque (endpoints verificados).
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from connectors.boe_client import BOEClient, BOEError, BOERepository
from connectors.boe_models import Bloque, IndiceEntry
from connectors.embeddings import Embedder
from core.materias import alias_de, id_norma, normas, nucleo
from core.normalize import fold
from storage.lance_schema import LegislacionStore, chunk_text

log = logging.getLogger(__name__)

# Niveles de la estructura de una norma, de mayor a menor.
_NIVELES = ("parte", "libro", "titulo", "capitulo", "seccion", "subseccion")
_PRECEPTO = re.compile(r"^(articulo|disposicion)\b")


def _nivel(titulo: str) -> int | None:
    t = fold(titulo or "").lower().strip()
    for i, nombre in enumerate(_NIVELES):
        if t.startswith(nombre):
            return i
    return None


def es_precepto(titulo: str, tipo: str | None = None) -> bool:
    return tipo == "precepto" or bool(_PRECEPTO.match(fold(titulo or "").lower().strip()))


@dataclass
class ProgresoIngesta:
    alias: str
    id_norma: str
    fase: str  # indice | texto | bloques | vectores | fin
    hechos: int = 0
    total: int = 0


Progreso = Callable[[ProgresoIngesta], None]


@dataclass
class ResultadoIngesta:
    alias: str
    id_norma: str
    titulo: str = ""
    modo: str = ""
    preceptos: int = 0
    descargados: int = 0
    sin_cambios: int = 0
    errores: int = 0
    vectores_nuevos: int = 0
    avisos: list[str] = field(default_factory=list)


class _Ubicacion:
    """Ruta jerárquica (Libro > Título > Capítulo…) a partir del orden del documento."""

    def __init__(self) -> None:
        self._niveles: dict[int, str] = {}

    def encabezado(self, nivel: int, texto: str) -> None:
        self._niveles = {k: v for k, v in self._niveles.items() if k < nivel}
        self._niveles[nivel] = " ".join(texto.split())[:120]

    def actual(self) -> str:
        return " > ".join(self._niveles[k] for k in sorted(self._niveles))


def _texto_encabezado(b: Bloque) -> str:
    """'TÍTULO IV' + su rúbrica, si el bloque la trae ('TÍTULO IV De la compraventa')."""
    if not b.versiones:
        return b.titulo
    lineas = [ln for ln in b.versiones[-1].texto.split("\n") if ln.strip()][:2]
    texto = " ".join(lineas) if lineas else b.titulo
    return texto if fold(b.titulo).lower() in fold(texto).lower() else f"{b.titulo} {texto}".strip()


class CorpusLegal:
    # Con más preceptos pendientes que esto, compensa pedir el texto completo en una sola petición.
    UMBRAL_TEXTO_COMPLETO = 20

    def __init__(
        self,
        con: sqlite3.Connection,
        repo: BOERepository,
        client: BOEClient,
        *,
        store: LegislacionStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._con = con
        self._repo = repo
        self._client = client
        self.store = store
        self.embedder = embedder

    # ---------- estado ----------
    def estado(self) -> list[dict[str, Any]]:
        """Una fila por norma del núcleo (y por cualquier otra ya descargada), con su estado de descarga."""
        filas = {
            r[0]: {
                "id_norma": r[0],
                "alias": r[1],
                "titulo": r[2],
                "estado": r[3],
                "preceptos": r[4],
                "preceptos_ok": r[5],
                "errores": r[6],
                "modo": r[7],
                "ultimo_error": r[8],
                "actualizado_en": r[9],
            }
            for r in self._con.execute(
                """SELECT id_norma, alias, titulo, estado, preceptos, preceptos_ok, errores, modo, ultimo_error,
                          actualizado_en FROM boe_corpus"""
            ).fetchall()
        }
        catalogo = normas()
        salida: list[dict[str, Any]] = []
        for alias in nucleo():
            meta = catalogo[alias]
            fila = filas.pop(
                meta["id"],
                {
                    "id_norma": meta["id"],
                    "alias": alias,
                    "titulo": meta["titulo"],
                    "estado": "pendiente",
                    "preceptos": 0,
                    "preceptos_ok": 0,
                    "errores": 0,
                    "modo": None,
                    "ultimo_error": None,
                    "actualizado_en": None,
                },
            )
            salida.append({**fila, "nucleo": True, "verificado": meta.get("verificado", True) is not False})
        salida.extend({**f, "nucleo": False, "verificado": True} for f in filas.values())
        return salida

    def ids_descargados(self) -> list[str]:
        return [
            str(r[0])
            for r in self._con.execute(
                "SELECT id_norma FROM boe_corpus WHERE estado IN ('completa', 'parcial') AND preceptos_ok > 0"
            ).fetchall()
        ]

    def _registrar(self, id_norma_boe: str, alias: str, **campos: Any) -> None:
        self._con.execute(
            """INSERT INTO boe_corpus(id_norma, alias, actualizado_en) VALUES (?, ?, datetime('now'))
               ON CONFLICT(id_norma) DO UPDATE SET alias = excluded.alias, actualizado_en = datetime('now')""",
            (id_norma_boe, alias),
        )
        if campos:
            asignaciones = ", ".join(f"{k} = ?" for k in campos)
            self._con.execute(
                f"UPDATE boe_corpus SET {asignaciones} WHERE id_norma = ?", [*campos.values(), id_norma_boe]
            )

    def _guardado(self, id_norma_boe: str) -> dict[str, str | None]:
        return {
            str(r[0]): r[1]
            for r in self._con.execute(
                """SELECT cb.id_bloque, cb.fecha_actualizacion_boe FROM boe_corpus_bloques cb
                   WHERE cb.id_norma = ? AND EXISTS (SELECT 1 FROM boe_bloques b
                                                     WHERE b.id_norma = cb.id_norma AND b.id_bloque = cb.id_bloque)""",
                (id_norma_boe,),
            ).fetchall()
        }

    def _marcar(self, id_norma_boe: str, id_bloque: str, orden: int, ubicacion: str, fecha: date | None) -> None:
        self._con.execute(
            """INSERT INTO boe_corpus_bloques(id_norma, id_bloque, orden, ubicacion, fecha_actualizacion_boe)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id_norma, id_bloque) DO UPDATE SET orden = excluded.orden, ubicacion = excluded.ubicacion,
                 fecha_actualizacion_boe = excluded.fecha_actualizacion_boe, ingerido_en = datetime('now')""",
            (id_norma_boe, id_bloque, orden, ubicacion, fecha.isoformat() if fecha else None),
        )

    # ---------- ingesta ----------
    async def ingerir(
        self, alias: str, *, progreso: Progreso | None = None, forzar: bool = False, vectores: bool = True
    ) -> ResultadoIngesta:
        nid = id_norma(alias)
        res = ResultadoIngesta(alias=alias, id_norma=nid)
        avisar = progreso or (lambda p: None)
        self._registrar(nid, alias, estado="en_curso", ultimo_error=None)
        try:
            meta = await self._repo.ensure_norma(nid)  # comprueba la identidad contra el BOE en tiempo real
            res.titulo = meta.titulo
            self._registrar(nid, alias, titulo=meta.titulo)
            if meta.derogada:
                res.avisos.append(f"{alias}: la norma figura como derogada en el BOE; se guarda para hechos pasados.")
            avisar(ProgresoIngesta(alias, nid, "indice"))
            indice = await self._client.indice(nid)
        except BOEError as exc:
            self._registrar(nid, alias, estado="error", ultimo_error=str(exc)[:500])
            res.errores += 1
            res.avisos.append(f"{alias}: {exc}")
            return res
        preceptos = [e for e in indice if es_precepto(e.titulo)]
        res.preceptos = len(preceptos)
        guardado = self._guardado(nid)
        pendientes = [e for e in preceptos if forzar or not _al_dia(e, guardado)]
        res.sin_cambios = len(preceptos) - len(pendientes)
        if pendientes:
            usar_texto = len(pendientes) > self.UMBRAL_TEXTO_COMPLETO
            completos = await self._texto_completo(nid, alias, indice, res, avisar) if usar_texto else False
            if not completos:
                await self._bloque_a_bloque(nid, alias, indice, {e.id_bloque for e in pendientes}, res, avisar)
        else:
            res.modo = "sin_cambios"
        ok = len(self._guardado(nid))
        self._registrar(
            nid,
            alias,
            estado="completa" if res.errores == 0 and ok >= res.preceptos else ("parcial" if ok else "error"),
            preceptos=res.preceptos,
            preceptos_ok=ok,
            errores=res.errores,
            modo=res.modo,
        )
        if vectores and self.store is not None and self.embedder is not None:
            res.vectores_nuevos = await self.indexar_vectores(nid, alias, progreso=avisar)
        avisar(ProgresoIngesta(alias, nid, "fin", ok, res.preceptos))
        return res

    async def _texto_completo(
        self, nid: str, alias: str, indice: list[IndiceEntry], res: ResultadoIngesta, avisar: Progreso
    ) -> bool:
        avisar(ProgresoIngesta(alias, nid, "texto", 0, res.preceptos))
        try:
            bloques = await self._client.texto_completo(nid)
        except BOEError as exc:
            log.info("%s: sin texto completo (%s); se descarga bloque a bloque", alias, exc)
            return False
        fechas = {e.id_bloque: e.fecha_actualizacion for e in indice}
        ubic = _Ubicacion()
        n = 0
        for orden, b in enumerate(bloques):
            nivel = _nivel(b.titulo)
            if not es_precepto(b.titulo, b.tipo):
                if nivel is not None:
                    ubic.encabezado(nivel, _texto_encabezado(b))
                continue
            self._repo.store_bloque(b)
            self._marcar(nid, b.id_bloque, orden, ubic.actual(), fechas.get(b.id_bloque))
            n += 1
        if n == 0:
            return False
        res.modo, res.descargados = "texto_completo", n
        avisar(ProgresoIngesta(alias, nid, "texto", n, res.preceptos))
        return True

    async def _bloque_a_bloque(
        self,
        nid: str,
        alias: str,
        indice: list[IndiceEntry],
        pendientes: set[str],
        res: ResultadoIngesta,
        avisar: Progreso,
    ) -> None:
        res.modo = "bloques"
        ubic = _Ubicacion()
        hechos = 0
        for orden, e in enumerate(indice):
            if not es_precepto(e.titulo):
                if (nivel := _nivel(e.titulo)) is not None:
                    ubic.encabezado(nivel, e.titulo)
                continue
            if e.id_bloque not in pendientes:
                # Ya estaba al día: solo se refresca la ubicación (puede no tenerla si vino de la caché del pipeline).
                self._con.execute(
                    "UPDATE boe_corpus_bloques SET orden = ?, ubicacion = ? WHERE id_norma = ? AND id_bloque = ?",
                    (orden, ubic.actual(), nid, e.id_bloque),
                )
                continue
            try:
                bloque = await self._client.bloque(nid, e.id_bloque)
            except BOEError as exc:
                res.errores += 1
                if res.errores <= 5:
                    res.avisos.append(f"{alias} {e.titulo}: {exc}")
                continue
            if not bloque.versiones:
                continue
            self._repo.store_bloque(bloque)
            self._marcar(nid, e.id_bloque, orden, ubic.actual(), e.fecha_actualizacion)
            res.descargados += 1
            hechos += 1
            if hechos % 10 == 0 or hechos == len(pendientes):
                avisar(ProgresoIngesta(alias, nid, "bloques", hechos, len(pendientes)))

    # ---------- vectores ----------
    async def indexar_vectores(self, nid: str, alias: str | None = None, *, progreso: Progreso | None = None) -> int:
        """Un vector por trozo de cada VERSIÓN de precepto. Solo se calculan los trozos nuevos o cambiados (la clave
        incluye la vigencia, que cambia cuando el BOE añade una redacción nueva)."""
        if self.store is None or self.embedder is None:
            return 0
        alias = alias or alias_de(nid) or nid
        filas = self._con.execute(
            """SELECT b.id_bloque, b.titulo, b.version_vigencia_desde, b.version_vigencia_hasta, b.texto_consolidado,
                      b.texto_hash, COALESCE(cb.ubicacion, '')
               FROM boe_bloques b JOIN boe_corpus_bloques cb ON cb.id_norma = b.id_norma AND cb.id_bloque = b.id_bloque
               WHERE b.id_norma = ? ORDER BY cb.orden, b.version_vigencia_desde""",
            (nid,),
        ).fetchall()
        max_chars = 500 if "minilm" in self.embedder.model.lower() else 1500
        trozos: list[dict[str, Any]] = []
        for id_bloque, titulo, desde, hasta, texto, texto_hash, ubicacion in filas:
            for i, trozo in enumerate(chunk_text(texto or "", max_chars=max_chars)):
                clave = hashlib.sha256(f"{id_bloque}|{desde}|{hasta}|{texto_hash}|{i}".encode()).hexdigest()
                trozos.append(
                    {
                        "chunk_id": f"{nid}:{id_bloque}:{desde}:{i}",
                        "id_norma": nid,
                        "id_bloque": id_bloque,
                        "titulo": titulo or "",
                        "ubicacion": ubicacion,
                        "vigencia_desde": date.fromisoformat(desde),
                        "vigencia_hasta": date.fromisoformat(hasta) if hasta else None,
                        "chunk_text": f"{alias} · {titulo or ''}\n{trozo}",
                        "texto_hash": clave,
                        "embedding_model": self.embedder.model,
                    }
                )
        vigentes = {t["texto_hash"] for t in trozos}
        existentes = self.store.hashes(nid)
        if existentes - vigentes:
            self.store.delete_norma(nid, salvo_hashes=vigentes & existentes)
        nuevos = [t for t in trozos if t["texto_hash"] not in existentes]
        avisar = progreso or (lambda p: None)
        for inicio in range(0, len(nuevos), 64):
            lote = nuevos[inicio : inicio + 64]
            vectores = await self.embedder.embed([t["chunk_text"] for t in lote], "RETRIEVAL_DOCUMENT")
            self.store.add([{**t, "vector": v} for t, v in zip(lote, vectores, strict=True)])
            avisar(ProgresoIngesta(alias, nid, "vectores", min(inicio + 64, len(nuevos)), len(nuevos)))
        return len(nuevos)


def _al_dia(e: IndiceEntry, guardado: dict[str, str | None]) -> bool:
    if e.id_bloque not in guardado:
        return False
    fecha = guardado[e.id_bloque]
    return bool(fecha and e.fecha_actualizacion and fecha >= e.fecha_actualizacion.isoformat())
