"""Registro de cada llamada LLM en `llm_calls_ledger` (dossier §1.1.1: medir la cuota real, no estimarla)."""

from __future__ import annotations

import sqlite3
import threading
from typing import Any


class QuotaLedger:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._lock = threading.Lock()

    def record(
        self,
        *,
        fase: str,
        proveedor: str,
        modelo: str,
        latencia_ms: int,
        ok: bool,
        consulta_id: str | None = None,
        rol: str | None = None,
        effort: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        coste_equivalente_usd: float | None = None,
        error_tipo: str | None = None,
    ) -> None:
        with self._lock:
            self._con.execute(
                """INSERT INTO llm_calls_ledger (consulta_id, fase, rol, proveedor, modelo, effort,
                       input_tokens, output_tokens, coste_equivalente_usd, latencia_ms, ok, error_tipo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    consulta_id, fase, rol, proveedor, modelo, effort, input_tokens, output_tokens,
                    coste_equivalente_usd, latencia_ms, int(ok), error_tipo,
                ),
            )

    def window_usage(self, proveedor: str, horas: float = 5) -> dict[str, Any]:
        row = self._con.execute(
            """SELECT count(*), coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0),
                      coalesce(sum(coste_equivalente_usd), 0)
               FROM llm_calls_ledger
               WHERE proveedor = ? AND ok = 1 AND creado_en >= datetime('now', ?)""",
            (proveedor, f"-{horas * 60:.0f} minutes"),
        ).fetchone()
        return {
            "llamadas": row[0],
            "input_tokens": row[1],
            "output_tokens": row[2],
            "coste_equivalente_usd": round(row[3], 4),
        }

    def daily_count(self, modelo: str) -> int:
        """Llamadas a un modelo desde la medianoche UTC (los RPD de Gemini se reinician a diario)."""
        row = self._con.execute(
            "SELECT count(*) FROM llm_calls_ledger WHERE modelo = ? AND creado_en >= date('now')",
            (modelo,),
        ).fetchone()
        return int(row[0])
