"""Circuit breaker de cuota por proveedor, persistido en SQLite (dossier §1.1.2)."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

State = Literal["closed", "open", "half_open"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CircuitBreaker:
    def __init__(
        self,
        con: sqlite3.Connection,
        *,
        default_open_minutes: int = 60,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._con = con
        self._default_open = timedelta(minutes=default_open_minutes)
        self._clock = clock
        self._lock = threading.Lock()
        self._probe_in_flight: set[str] = set()

    def _row(self, proveedor: str) -> tuple[State, datetime | None, str | None]:
        row = self._con.execute(
            "SELECT estado, abierto_hasta, motivo FROM circuit_breaker_state WHERE proveedor = ?",
            (proveedor,),
        ).fetchone()
        if row is None:
            return "closed", None, None
        until = datetime.fromisoformat(row[1]) if row[1] else None
        return row[0], until, row[2]

    def _save(self, proveedor: str, estado: State, until: datetime | None, motivo: str | None) -> None:
        self._con.execute(
            """INSERT INTO circuit_breaker_state(proveedor, estado, abierto_hasta, motivo) VALUES (?, ?, ?, ?)
               ON CONFLICT(proveedor) DO UPDATE SET estado = excluded.estado,
                   abierto_hasta = excluded.abierto_hasta, motivo = excluded.motivo""",
            (proveedor, estado, until.isoformat() if until else None, motivo),
        )

    def state(self, proveedor: str) -> State:
        estado, until, motivo = self._row(proveedor)
        if estado == "open" and until is not None and self._clock() >= until:
            self._save(proveedor, "half_open", None, motivo)
            return "half_open"
        return estado

    def allow(self, proveedor: str) -> bool:
        """True si se puede llamar. En half_open solo deja pasar una sonda a la vez."""
        with self._lock:
            estado = self.state(proveedor)
            if estado == "closed":
                return True
            if estado == "half_open" and proveedor not in self._probe_in_flight:
                self._probe_in_flight.add(proveedor)
                return True
            return False

    def record_success(self, proveedor: str) -> None:
        with self._lock:
            self._probe_in_flight.discard(proveedor)
            if self._row(proveedor)[0] != "closed":
                self._save(proveedor, "closed", None, None)

    def record_failure(self, proveedor: str) -> None:
        """Fallo que no es de cuota: si era la sonda, se vuelve a abrir el breaker."""
        with self._lock:
            if proveedor in self._probe_in_flight:
                self._probe_in_flight.discard(proveedor)
                _, _, motivo = self._row(proveedor)
                self._save(proveedor, "open", self._clock() + self._default_open, motivo)

    def trip(self, proveedor: str, *, reset_at: datetime | None = None, motivo: str | None = None) -> None:
        with self._lock:
            self._probe_in_flight.discard(proveedor)
            self._save(proveedor, "open", reset_at or self._clock() + self._default_open, motivo)

    def snapshot(self, proveedor: str) -> dict[str, str | None]:
        estado = self.state(proveedor)
        _, until, motivo = self._row(proveedor)
        return {"estado": estado, "abierto_hasta": until.isoformat() if until else None, "motivo": motivo}
