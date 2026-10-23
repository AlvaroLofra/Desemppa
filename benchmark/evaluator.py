"""Rúbrica 0–100 (dossier v2.1 §9.3): Outcome 30, Recall BOE 30, Doctrina 25, Alucinación 15.
Outcome, Recall y Alucinación son deterministas; Doctrina usa un juez LLM opcional de otra familia."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Puntuacion:
    caso: str
    outcome: float
    recall: float
    doctrina: float | None
    alucinacion: float
    estado: str

    @property
    def total(self) -> float:
        """Sobre 100; sin juez de doctrina se reescala sobre los 75 puntos deterministas."""
        base = self.outcome + self.recall + self.alucinacion
        return round(base + self.doctrina, 1) if self.doctrina is not None else round(base * 100 / 75, 1)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "total": self.total}


def norma_bloque(source_id: str) -> str:
    parts = source_id.split(":")
    return f"{parts[1]}:{parts[2]}" if source_id.startswith("BOE:") and len(parts) >= 3 else ""


def puntuar(
    caso: dict[str, Any], final: dict[str, Any], guardrails: list[dict[str, Any]], doctrina: float | None = None
) -> Puntuacion:
    esperado = caso["esperado"]
    estado = str(final.get("estado", "ERROR"))
    dictamen = final.get("dictamen") or {}
    cuestiones = dictamen.get("cuestiones", [])
    votos = [q.get("estimacion") for q in cuestiones]
    mayoria = max(set(votos), key=votos.count) if votos else None
    outcome = 30.0 if mayoria == esperado["estimacion_principal"] else 0.0
    citados = {norma_bloque(f["source_id"]) for f in dictamen.get("fundamentos", [])} - {""}
    gold = set(esperado.get("articulos_gold", []))
    recall = 30.0 * len(gold & citados) / len(gold) if gold else 30.0
    primer = next((g for g in guardrails if str(g.get("id", "")).startswith("G2-G4")), None)
    fallos = len(primer.get("detalle", [])) if primer and not primer.get("ok") else 0
    total_citas = max(1, sum(len(a.get("citas", [])) for q in cuestiones for a in q.get("fundamentos", [])))
    alucinacion = 15.0 * max(0.0, 1 - fallos / total_citas)
    if estado != "CERTIFICADA":
        outcome, recall = 0.0, 0.0
    return Puntuacion(
        caso=caso["id"],
        outcome=outcome,
        recall=round(recall, 1),
        doctrina=doctrina,
        alucinacion=round(alucinacion, 1),
        estado=estado,
    )
