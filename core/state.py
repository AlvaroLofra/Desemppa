"""Estado de las consultas (máquina §2.2), persistencia en SQLite y bus de eventos SSE con replay."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from core.pii_redactor import Redaction, redact
from core.secure_store import decrypt, encrypt


class Estado(StrEnum):
    RECIBIDA = "RECIBIDA"
    TRIAJE = "TRIAJE"
    ESPERANDO_ACLARACION = "ESPERANDO_ACLARACION"
    FUERA_DE_ALCANCE = "FUERA_DE_ALCANCE"
    INGESTA = "INGESTA"
    INGESTA_DEGRADADA = "INGESTA_DEGRADADA"
    DEBATE = "DEBATE"
    GUARDARRAILES = "GUARDARRAILES"
    CERTIFICADA = "CERTIFICADA"
    BLOQUEADA = "BLOQUEADA"
    ERROR = "ERROR"


TERMINALES = {Estado.CERTIFICADA, Estado.BLOQUEADA, Estado.FUERA_DE_ALCANCE, Estado.ERROR}
TRANSICIONES: dict[Estado, set[Estado]] = {
    Estado.RECIBIDA: {Estado.TRIAJE, Estado.ERROR},
    Estado.TRIAJE: {Estado.ESPERANDO_ACLARACION, Estado.FUERA_DE_ALCANCE, Estado.INGESTA, Estado.ERROR},
    Estado.ESPERANDO_ACLARACION: {Estado.TRIAJE, Estado.ERROR},
    Estado.INGESTA: {Estado.INGESTA_DEGRADADA, Estado.DEBATE, Estado.ERROR},
    Estado.INGESTA_DEGRADADA: {Estado.DEBATE, Estado.ERROR},
    Estado.DEBATE: {Estado.GUARDARRAILES, Estado.ERROR},
    Estado.GUARDARRAILES: {Estado.DEBATE, Estado.CERTIFICADA, Estado.BLOQUEADA, Estado.ERROR},
    Estado.CERTIFICADA: set(),
    Estado.BLOQUEADA: set(),
    Estado.FUERA_DE_ALCANCE: set(),
    Estado.ERROR: set(),
}


class TransicionInvalida(RuntimeError):
    pass


def tipo_adjunto(texto: str) -> str:
    t = texto.lower()
    if "nómina" in t or "nomina" in t or "líquido a percibir" in t or "devengos" in t:
        return "nomina"
    if "carta de despido" in t or "despido disciplinario" in t or "extinción de su contrato" in t:
        return "carta_despido"
    if "sanción" in t or "denuncia" in t or "boletín de denuncia" in t or "multa" in t:
        return "sancion"
    if "contrato" in t or "arrendamiento" in t:
        return "contrato"
    return "otro"


@dataclass
class Consulta:
    consulta_id: str
    modo: str
    estado: Estado
    texto_seudonimizado: str
    pii_map: dict[str, str]
    municipio_ine: str | None
    aclaraciones: list[dict[str, str]] = field(default_factory=list)
    adjuntos: list[dict[str, str]] = field(default_factory=list)  # {adjunto_id, nombre, tipo, texto (seud.)}
    triage: dict[str, Any] | None = None
    dossier: dict[str, Any] | None = None
    debate: dict[str, Any] | None = None
    dictamen: dict[str, Any] | None = None


class ConsultaStore:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._lock = threading.Lock()

    # ---------- adjuntos ----------
    def add_adjunto(
        self, nombre: str, sha256: str, texto: str, *, ocr_usado: bool, permitir_envio: bool = False
    ) -> dict[str, str]:
        """`permitir_envio`: consentimiento explícito para enviar el texto (seudonimizado) a los modelos
        externos. Por defecto NO (dossier §1.1.4): sin él, el documento solo se usa para clasificarlo."""
        adjunto_id = uuid.uuid4().hex
        tipo = tipo_adjunto(texto)
        self._con.execute(
            """INSERT INTO adjuntos(adjunto_id, consulta_id, nombre, sha256, tipo_detectado, texto_extraido_cifrado,
                   ocr_usado, permitir_gemini) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)""",
            (adjunto_id, nombre, sha256, tipo, encrypt(texto), int(ocr_usado), int(permitir_envio)),
        )
        return {"adjunto_id": adjunto_id, "nombre": nombre, "tipo": tipo}

    # ---------- consultas ----------
    def create(
        self,
        texto: str,
        modo: str,
        *,
        municipio_ine: str | None = None,
        adjuntos: list[str] | None = None,
        origen: str = "local",
    ) -> str:
        consulta_id = str(uuid.uuid4())
        red = redact(texto)
        self._con.execute(
            """INSERT INTO sesiones_consultas(consulta_id, modo_utilizado, estado, consulta_usuario_cifrada,
                   consulta_seudonimizada, pii_map_cifrado, origen) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                consulta_id,
                modo,
                Estado.RECIBIDA,
                encrypt(texto),
                red.text,
                encrypt(json.dumps({"mapping": red.mapping, "municipio_ine": municipio_ine, "aclaraciones": []})),
                origen,
            ),
        )
        for adjunto_id in adjuntos or []:
            self._con.execute(
                "UPDATE adjuntos SET consulta_id = ? WHERE adjunto_id = ? AND consulta_id IS NULL",
                (consulta_id, adjunto_id),
            )
        return consulta_id

    def _meta(self, consulta_id: str) -> dict[str, Any]:
        row = self._con.execute(
            "SELECT pii_map_cifrado FROM sesiones_consultas WHERE consulta_id = ?", (consulta_id,)
        ).fetchone()
        if row is None:
            raise KeyError(consulta_id)
        return dict(json.loads(decrypt(row[0])))

    def _save_meta(self, consulta_id: str, meta: dict[str, Any]) -> None:
        self._con.execute(
            "UPDATE sesiones_consultas SET pii_map_cifrado = ? WHERE consulta_id = ?",
            (encrypt(json.dumps(meta, ensure_ascii=False)), consulta_id),
        )

    def get(self, consulta_id: str) -> Consulta:
        row = self._con.execute(
            """SELECT modo_utilizado, estado, consulta_seudonimizada, triage_json, dossier_json, debate_json,
                      dictamen_json FROM sesiones_consultas WHERE consulta_id = ?""",
            (consulta_id,),
        ).fetchone()
        if row is None:
            raise KeyError(consulta_id)
        meta = self._meta(consulta_id)
        mapping: dict[str, str] = meta.get("mapping", {})
        adjuntos = []
        for a in self._con.execute(
            """SELECT adjunto_id, nombre, tipo_detectado, texto_extraido_cifrado, permitir_gemini
               FROM adjuntos WHERE consulta_id = ?""",
            (consulta_id,),
        ):
            red: Redaction = redact(decrypt(a[3]), mapping=mapping)
            mapping = red.mapping
            adjuntos.append(
                {"adjunto_id": a[0], "nombre": a[1], "tipo": a[2], "texto": red.text, "permitido": "1" if a[4] else ""}
            )
        if mapping != meta.get("mapping"):
            meta["mapping"] = mapping
            self._save_meta(consulta_id, meta)

        def _j(v: str | None) -> dict[str, Any] | None:
            return json.loads(v) if v else None

        return Consulta(
            consulta_id=consulta_id,
            modo=row[0],
            estado=Estado(row[1]),
            texto_seudonimizado=row[2],
            pii_map=mapping,
            municipio_ine=meta.get("municipio_ine"),
            aclaraciones=meta.get("aclaraciones", []),
            adjuntos=adjuntos,
            triage=_j(row[3]),
            dossier=_j(row[4]),
            debate=_j(row[5]),
            dictamen=_j(row[6]),
        )

    def add_aclaraciones(self, consulta_id: str, respuestas: list[dict[str, str]]) -> None:
        meta = self._meta(consulta_id)
        mapping: dict[str, str] = meta.get("mapping", {})
        nuevas = []
        for r in respuestas:
            red = redact(str(r.get("respuesta", "")), mapping=mapping)
            mapping = red.mapping
            nuevas.append({"pregunta": str(r.get("pregunta", "")), "respuesta": red.text})
        meta["mapping"] = mapping
        meta["aclaraciones"] = meta.get("aclaraciones", []) + nuevas
        if any(r.get("municipio_ine") for r in respuestas):
            meta["municipio_ine"] = next(r["municipio_ine"] for r in respuestas if r.get("municipio_ine"))
        self._save_meta(consulta_id, meta)

    def set_estado(self, consulta_id: str, nuevo: Estado, *, error: str | None = None) -> None:
        with self._lock:
            actual = Estado(
                self._con.execute(
                    "SELECT estado FROM sesiones_consultas WHERE consulta_id = ?", (consulta_id,)
                ).fetchone()[0]
            )
            if nuevo != actual and nuevo not in TRANSICIONES[actual]:
                raise TransicionInvalida(f"{actual} -> {nuevo}")
            self._con.execute(
                "UPDATE sesiones_consultas SET estado = ?, error = coalesce(?, error) WHERE consulta_id = ?",
                (nuevo, error, consulta_id),
            )

    def save(self, consulta_id: str, **fields: Any) -> None:
        allowed = {
            "triage_json",
            "dossier_json",
            "debate_json",
            "dictamen_json",
            "dictamen_markdown",
            "banda_solidez",
            "fuzzy_min_score",
            "guardrails_json",
        }
        assert set(fields) <= allowed, set(fields) - allowed
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = [
            json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v
            for v in fields.values()
        ]
        self._con.execute(f"UPDATE sesiones_consultas SET {sets} WHERE consulta_id = ?", (*values, consulta_id))

    def recover_interrupted(self) -> int:
        """Al arrancar: las consultas que quedaron a medias (proceso cerrado) pasan a ERROR. Las que esperan una
        aclaración del usuario se conservan."""
        activos = [e.value for e in Estado if e not in TERMINALES and e != Estado.ESPERANDO_ACLARACION]
        cur = self._con.execute(
            f"UPDATE sesiones_consultas SET estado = ?, error = ? WHERE estado IN ({', '.join('?' * len(activos))})",
            (Estado.ERROR.value, "interrumpida: la aplicación se cerró durante el análisis", *activos),
        )
        return int(cur.rowcount or 0)

    def listar(self, limit: int = 50, *, origen: str | None = None) -> list[dict[str, Any]]:
        """Historial. Con `origen` solo las de ese origen (lo que ve un invitado); sin él, todas."""
        filtro, params = ("WHERE origen = ?", (origen, limit)) if origen else ("", (limit,))
        rows = self._con.execute(
            f"""SELECT consulta_id, creado_en, modo_utilizado, estado, consulta_seudonimizada, banda_solidez, origen
               FROM sesiones_consultas {filtro} ORDER BY creado_en DESC LIMIT ?""",
            params,
        ).fetchall()
        return [
            {
                "consulta_id": r[0],
                "creado_en": r[1],
                "modo": r[2],
                "estado": r[3],
                "titulo": r[4][:90],
                "banda": r[5],
                "invitado": r[6] != "local",
            }
            for r in rows
        ]

    def origen(self, consulta_id: str) -> str:
        row = self._con.execute(
            "SELECT origen FROM sesiones_consultas WHERE consulta_id = ?", (consulta_id,)
        ).fetchone()
        if row is None:
            raise KeyError(consulta_id)
        return str(row[0])

    def contar_hoy(self, origen: str) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM sesiones_consultas WHERE origen = ? AND date(creado_en) = date('now')", (origen,)
        ).fetchone()
        return int(row[0])

    def contar_hoy_invitados(self) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM sesiones_consultas WHERE origen != 'local' AND date(creado_en) = date('now')"
        ).fetchone()
        return int(row[0])

    def restore_pii(self, consulta_id: str, text: str) -> str:
        return Redaction(text="", mapping=self._meta(consulta_id).get("mapping", {})).restore(text)


class EventBus:
    """Persiste cada evento en `consulta_eventos` (replay con Last-Event-ID) y lo difunde en vivo."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._subs: dict[str, list[asyncio.Queue[tuple[int, str, dict[str, Any]]]]] = {}
        self._lock = threading.Lock()

    def emit(self, consulta_id: str, tipo: str, data: dict[str, Any]) -> int:
        with self._lock:
            seq = int(
                self._con.execute(
                    "SELECT coalesce(max(seq), 0) + 1 FROM consulta_eventos WHERE consulta_id = ?", (consulta_id,)
                ).fetchone()[0]
            )
            if tipo not in ("token", "debate_delta"):  # los deltas no se persisten (el resultado sí)
                self._con.execute(
                    "INSERT INTO consulta_eventos(consulta_id, seq, tipo, data_json) VALUES (?, ?, ?, ?)",
                    (consulta_id, seq, tipo, json.dumps(data, ensure_ascii=False, default=str)),
                )
        for q in self._subs.get(consulta_id, []):
            q.put_nowait((seq, tipo, data))
        return seq

    def history(self, consulta_id: str, after: int = 0) -> list[tuple[int, str, dict[str, Any]]]:
        rows = self._con.execute(
            "SELECT seq, tipo, data_json FROM consulta_eventos WHERE consulta_id = ? AND seq > ? ORDER BY seq",
            (consulta_id, after),
        ).fetchall()
        return [(r[0], r[1], json.loads(r[2])) for r in rows]

    def subscribe(self, consulta_id: str) -> asyncio.Queue[tuple[int, str, dict[str, Any]]]:
        q: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
        self._subs.setdefault(consulta_id, []).append(q)
        return q

    def unsubscribe(self, consulta_id: str, q: asyncio.Queue[tuple[int, str, dict[str, Any]]]) -> None:
        if q in self._subs.get(consulta_id, []):
            self._subs[consulta_id].remove(q)
