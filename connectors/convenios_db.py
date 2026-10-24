"""Gestor de convenios colectivos (dossier §1.2.3): versiones, artículos (FTS5) y tablas salariales
verificadas de forma determinista contra el texto del convenio."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz

from connectors.boe_client import fts_query
from core.normalize import normalize

_ART_RE = re.compile(r"^\s*Art[íi]culo\s+(\d+(?:\s?bis|\s?ter)?)\s*[.\-–:]*\s*(.*)$", re.M | re.I)
SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "convenios_seed.yaml"


@dataclass
class FilaSalarial:
    anio: int
    grupo_categoria: str
    concepto: str
    importe_eur: float
    periodicidad: str
    texto_fila: str  # literal de la fila tal como aparece en el convenio


def split_articulos(texto: str) -> list[tuple[str, str, str]]:
    marks = list(_ART_RE.finditer(texto))
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(texto)
        out.append((m.group(1).strip(), m.group(2).strip()[:200], texto[m.start() : end].strip()))
    return out


def importe_en_texto(importe: float, texto: str) -> bool:
    """¿Aparece el importe escrito en formato español (1.234,56 / 1234,56 / 1234.56) en el texto?"""
    entero, dec = f"{importe:.2f}".split(".")
    con_miles = f"{int(entero):,}".replace(",", ".")
    variantes = {f"{con_miles},{dec}", f"{entero},{dec}", f"{entero}.{dec}"}
    if dec == "00":
        variantes |= {con_miles, entero}
    return any(re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d]|,\d)", texto) for v in variantes)


def verificar_fila(fila: FilaSalarial, texto_convenio: str) -> float:
    """Puntuación 0–100: la fila literal debe estar en el convenio y contener el importe declarado."""
    if not importe_en_texto(fila.importe_eur, fila.texto_fila):
        return 0.0
    return float(fuzz.partial_ratio(normalize(fila.texto_fila), normalize(texto_convenio)))


class ConveniosRepository:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def upsert_convenio(
        self,
        codigo: str,
        denominacion: str,
        ambito_funcional: str,
        ambito_territorial: str,
        *,
        cnae: list[str] | None = None,
        trabajadores: int | None = None,
        prioridad: int | None = None,
    ) -> None:
        self._con.execute(
            """INSERT INTO convenios_cache(codigo_convenio, denominacion, ambito_funcional, ambito_territorial,
                   cnae, trabajadores_afectados, prioridad_seed) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(codigo_convenio) DO UPDATE SET denominacion=excluded.denominacion,
                   ambito_funcional=excluded.ambito_funcional, ambito_territorial=excluded.ambito_territorial,
                   cnae=excluded.cnae, trabajadores_afectados=excluded.trabajadores_afectados,
                   prioridad_seed=excluded.prioridad_seed""",
            (codigo, denominacion, ambito_funcional, ambito_territorial, str(cnae or []), trabajadores, prioridad),
        )

    def add_version(
        self,
        codigo: str,
        texto: str,
        *,
        boletin_ref: str,
        vigencia_desde: date,
        vigencia_hasta: date | None = None,
        anio_publicacion: int | None = None,
    ) -> str:
        version_id = f"{codigo}:{anio_publicacion or vigencia_desde.year}"
        self._con.execute("BEGIN")
        try:
            self._con.execute("DELETE FROM convenios_articulos WHERE version_id = ?", (version_id,))
            self._con.execute("DELETE FROM convenios_tablas_salariales WHERE version_id = ?", (version_id,))
            self._con.execute(
                """INSERT OR REPLACE INTO convenios_versiones(version_id, codigo_convenio, boletin_ref,
                       vigencia_desde, vigencia_hasta, texto_integro) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    version_id,
                    codigo,
                    boletin_ref,
                    vigencia_desde.isoformat(),
                    vigencia_hasta.isoformat() if vigencia_hasta else None,
                    texto,
                ),
            )
            for articulo, titulo, cuerpo in split_articulos(texto):
                self._con.execute(
                    "INSERT OR IGNORE INTO convenios_articulos(version_id, articulo, titulo, texto) "
                    "VALUES (?, ?, ?, ?)",
                    (version_id, articulo, titulo, cuerpo),
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise
        return version_id

    def add_tabla_salarial(self, version_id: str, filas: list[FilaSalarial], *, umbral: float = 95.0) -> list[str]:
        """Inserta solo las filas verificadas (≥ umbral). Devuelve los motivos de rechazo."""
        texto = self._con.execute(
            "SELECT texto_integro FROM convenios_versiones WHERE version_id = ?", (version_id,)
        ).fetchone()
        if texto is None:
            raise KeyError(version_id)
        rechazos: list[str] = []
        for fila in filas:
            score = verificar_fila(fila, texto[0])
            if score < umbral:
                rechazos.append(f"{fila.grupo_categoria}/{fila.concepto}: verificación {score:.0f} < {umbral:.0f}")
                continue
            self._con.execute(
                """INSERT INTO convenios_tablas_salariales(version_id, anio, grupo_categoria, concepto,
                       importe_eur, periodicidad, verificado_fuzzy) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    version_id,
                    fila.anio,
                    fila.grupo_categoria,
                    fila.concepto,
                    fila.importe_eur,
                    fila.periodicidad,
                    score,
                ),
            )
        return rechazos

    def version_vigente(self, codigo: str, fecha: date) -> str | None:
        row = self._con.execute(
            """SELECT version_id FROM convenios_versiones WHERE codigo_convenio = ? AND vigencia_desde <= ?
                   AND (vigencia_hasta IS NULL OR vigencia_hasta >= ?)
               ORDER BY vigencia_desde DESC LIMIT 1""",
            (codigo, fecha.isoformat(), fecha.isoformat()),
        ).fetchone()
        return row[0] if row else None

    def buscar_clausulas(self, version_id: str, consulta: str, limit: int = 5) -> list[dict[str, Any]]:
        q = fts_query(consulta)
        if not q:
            return []
        rows = self._con.execute(
            """SELECT a.articulo, a.titulo, a.texto FROM convenios_fts JOIN convenios_articulos a
                   ON a.id = convenios_fts.rowid
               WHERE convenios_fts MATCH ? AND a.version_id = ? ORDER BY bm25(convenios_fts) LIMIT ?""",
            (q, version_id, limit),
        ).fetchall()
        return [{"articulo": r[0], "titulo": r[1], "texto": r[2]} for r in rows]

    def buscar_en_vigentes(
        self, consulta: str, fecha: date, codigo_convenio: str, limit: int = 4
    ) -> list[dict[str, Any]]:
        """Artículos relevantes de la versión del convenio `codigo_convenio` vigente en `fecha`.

        Solo se busca en el convenio identificado para el caso: mezclar convenios de otros sectores daría
        «fuentes verificadas» que no se aplican al trabajador."""
        q = fts_query(consulta)
        version_id = self.version_vigente(codigo_convenio, fecha)
        if not q or version_id is None:
            return []
        rows = self._con.execute(
            """SELECT c.codigo_convenio, c.denominacion, v.version_id, v.boletin_ref,
                      v.vigencia_desde, v.vigencia_hasta, a.articulo, a.titulo, a.texto
               FROM convenios_fts
               JOIN convenios_articulos a ON a.id = convenios_fts.rowid
               JOIN convenios_versiones v ON v.version_id = a.version_id
               JOIN convenios_cache c ON c.codigo_convenio = v.codigo_convenio
               WHERE convenios_fts MATCH ? AND a.version_id = ?
               ORDER BY bm25(convenios_fts) LIMIT ?""",
            (q, version_id, limit),
        ).fetchall()
        return [
            {
                "codigo_convenio": r[0],
                "denominacion": r[1],
                "version_id": r[2],
                "boletin_ref": r[3],
                "vigencia_desde": date.fromisoformat(r[4]),
                "vigencia_hasta": date.fromisoformat(r[5]) if r[5] else None,
                "articulo": r[6],
                "titulo": r[7],
                "texto": r[8],
            }
            for r in rows
        ]

    def indexados(self) -> list[dict[str, str]]:
        """Convenios con al menos una versión con texto indexado (los únicos que el triaje puede elegir)."""
        rows = self._con.execute(
            """SELECT DISTINCT c.codigo_convenio, c.denominacion, c.ambito_funcional, c.ambito_territorial
               FROM convenios_cache c JOIN convenios_versiones v ON v.codigo_convenio = c.codigo_convenio
               ORDER BY c.prioridad_seed"""
        ).fetchall()
        return [dict(zip(("codigo", "denominacion", "sector", "territorio"), r, strict=True)) for r in rows]

    def detalle_clausula(self, source_id: str) -> dict[str, Any] | None:
        m = re.match(r"^CONV:([^:]+):([^:]+):art(.+)$", source_id)
        if not m:
            return None
        codigo, anio, art = m.groups()
        version_id = f"{codigo}:{anio}"
        row = self._con.execute(
            """SELECT c.denominacion, v.boletin_ref, a.titulo, a.texto
               FROM convenios_articulos a
               JOIN convenios_versiones v ON v.version_id = a.version_id
               JOIN convenios_cache c ON c.codigo_convenio = v.codigo_convenio
               WHERE a.version_id = ? AND a.articulo = ?""",
            (version_id, art),
        ).fetchone()
        if not row:
            return None
        denom, ref, tit, texto = row
        url = f"https://www.boe.es/buscar/doc.php?id={ref}" if str(ref).startswith("BOE-") else None
        return {"titulo": f"Art. {art} {tit or ''} ({denom})".strip(), "texto": texto, "url": url}

    def listar(self, sector: str | None = None, territorio: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT codigo_convenio, denominacion, ambito_funcional, ambito_territorial FROM convenios_cache WHERE 1=1"
        )
        params: list[str] = []
        if sector:
            sql += " AND ambito_funcional LIKE ?"
            params.append(f"%{sector}%")
        if territorio:
            sql += " AND ambito_territorial LIKE ?"
            params.append(f"%{territorio}%")
        return [
            dict(zip(("codigo", "denominacion", "sector", "territorio"), r, strict=True))
            for r in self._con.execute(sql + " ORDER BY prioridad_seed", params).fetchall()
        ]


def load_seed(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("convenios", []))
