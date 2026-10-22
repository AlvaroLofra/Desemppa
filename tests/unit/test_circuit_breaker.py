from datetime import UTC, datetime, timedelta

from core.circuit_breaker import CircuitBreaker
from storage.database import open_database


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.now


def test_transitions(db):
    clock = Clock()
    cb = CircuitBreaker(db, default_open_minutes=60, clock=clock)
    assert cb.state("claude") == "closed" and cb.allow("claude")

    cb.trip("claude", motivo="usage limit")
    assert cb.state("claude") == "open" and not cb.allow("claude")

    clock.now += timedelta(minutes=61)
    assert cb.state("claude") == "half_open"
    assert cb.allow("claude")  # una sonda
    assert not cb.allow("claude")  # la segunda espera

    cb.record_failure("claude")  # la sonda falla -> vuelve a abrir
    assert cb.state("claude") == "open"

    clock.now += timedelta(minutes=61)
    assert cb.allow("claude")
    cb.record_success("claude")
    assert cb.state("claude") == "closed"


def test_trip_honours_reset_at(db):
    clock = Clock()
    cb = CircuitBreaker(db, clock=clock)
    cb.trip("claude", reset_at=clock.now + timedelta(minutes=5))
    clock.now += timedelta(minutes=6)
    assert cb.state("claude") == "half_open"


def test_state_persists_across_connections(tmp_path):
    path = tmp_path / "cb.db"
    clock = Clock()
    CircuitBreaker(open_database(path), clock=clock).trip("claude", motivo="x")
    reopened = CircuitBreaker(open_database(path), clock=clock)
    snap = reopened.snapshot("claude")
    assert snap["estado"] == "open" and snap["motivo"] == "x"
    assert reopened.state("gemini") == "closed"
