"""Guardarraíles deterministas de la Fase 4 (dossier §2.3, tabla G1–G10)."""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from core.normalize import normalize_with_map
from core.schemas import BANDA_ORDEN, PRONOSTICO_PORCENTUAL_RE, BandaSolidez

FUZZY_THRESHOLD = 95.0
MIN_QUOTE_CHARS = 40


@dataclass
class QuoteCheck:
    ok: bool
    score: float
    offsets: tuple[int, int] | None  # en el texto ORIGINAL de la fuente
    motivo: str = ""


def verify_quote(quote: str, source_text: str, *, threshold: float = FUZZY_THRESHOLD) -> QuoteCheck:
    """G3: la cita debe aparecer (casi) literal en la fuente declarada."""
    norm_quote, _ = normalize_with_map(quote)
    norm_src, offsets = normalize_with_map(source_text)
    if len(norm_quote) < MIN_QUOTE_CHARS:
        return QuoteCheck(False, 0.0, None, f"cita demasiado corta (< {MIN_QUOTE_CHARS} caracteres)")
    if not norm_src:
        return QuoteCheck(False, 0.0, None, "fuente vacía")
    exact = norm_src.find(norm_quote)
    if exact >= 0:
        return QuoteCheck(True, 100.0, (offsets[exact], offsets[exact + len(norm_quote) - 1] + 1))
    al = fuzz.partial_ratio_alignment(norm_quote, norm_src, score_cutoff=0)
    if al is None:
        return QuoteCheck(False, 0.0, None, "sin coincidencia")
    span = None
    if al.dest_end > al.dest_start:
        span = (offsets[al.dest_start], offsets[al.dest_end - 1] + 1)
    # partial_ratio compara la cita con la mejor ventana de su misma longitud: si la cita es más larga que
    # la fuente, se penaliza por la parte que sobra.
    score = float(al.score) * min(1.0, len(norm_src) / len(norm_quote))
    if score < threshold:
        return QuoteCheck(False, score, span, f"similitud {score:.1f} < {threshold:.0f}")
    return QuoteCheck(True, score, span)


def find_pronosticos(text: str) -> list[str]:
    """G4: pronósticos porcentuales prohibidos (art. 403 CP / §1.3.1)."""
    return [m.group(0) for m in PRONOSTICO_PORCENTUAL_RE.finditer(text)]


def _rank(b: BandaSolidez) -> int:
    return BANDA_ORDEN.index(b) if b in BANDA_ORDEN else len(BANDA_ORDEN)


def lower_band(banda: BandaSolidez, niveles: int = 1) -> BandaSolidez:
    if banda == BandaSolidez.CRITERIO_CONSOLIDADO_DESFAVORABLE:
        return banda
    return BANDA_ORDEN[min(_rank(banda) + niveles, len(BANDA_ORDEN) - 1)]


def cap_band(banda: BandaSolidez, tope: BandaSolidez) -> BandaSolidez:
    """Devuelve la menos favorable de las dos (nunca sube)."""
    if banda == BandaSolidez.CRITERIO_CONSOLIDADO_DESFAVORABLE:
        return banda
    return banda if _rank(banda) >= _rank(tope) else tope


@dataclass
class EvidenciaBanda:
    citas_boe_verificadas: int
    sentencias_favorables_ts: int
    sentencias_favorables_ap: int
    sentencias_desfavorables: int
    nli_neutral: int
    nli_contradice: int
    doctrina_cambiante: bool
    cobertura_degradada: bool
    hechos_sin_prueba: bool


def coherent_band(propuesta: BandaSolidez, ev: EvidenciaBanda) -> tuple[BandaSolidez, list[str]]:
    """G6/G10: ajusta la banda propuesta por el Magistrado a la evidencia verificada. Nunca la mejora."""
    motivos: list[str] = []
    banda = propuesta
    if ev.nli_contradice:
        return BandaSolidez.NO_DETERMINABLE, ["Una conclusión contradice la norma citada (NLI)."]
    if ev.citas_boe_verificadas == 0 and ev.sentencias_favorables_ts + ev.sentencias_favorables_ap == 0:
        return BandaSolidez.NO_DETERMINABLE, ["No hay ninguna cita verificada que sostenga el dictamen."]
    if banda == BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE:
        consolidado = ev.sentencias_favorables_ts >= 1 or ev.sentencias_favorables_ap >= 2
        if not consolidado or ev.sentencias_desfavorables:
            banda = BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA
            motivos.append("Sin jurisprudencia concordante suficiente (1 STS o 2 SAP) verificada.")
    if ev.sentencias_desfavorables and (ev.sentencias_favorables_ts or ev.sentencias_favorables_ap):
        nueva = cap_band(banda, BandaSolidez.DISPARIDAD_DE_CRITERIO)
        if nueva != banda:
            motivos.append("Hay sentencias citadas en ambos sentidos.")
        banda = nueva
    if ev.cobertura_degradada:
        nueva = cap_band(banda, BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA)
        if nueva != banda:
            motivos.append("Cobertura de jurisprudencia incompleta.")
        banda = nueva
    if ev.doctrina_cambiante:
        nueva = cap_band(banda, BandaSolidez.DISPARIDAD_DE_CRITERIO)
        if nueva != banda:
            motivos.append("Materia con jurisprudencia cambiante (🔎).")
        banda = nueva
    if ev.hechos_sin_prueba:
        nueva = cap_band(banda, BandaSolidez.RIESGO_PROBATORIO_ALTO)
        if nueva != banda:
            motivos.append("El resultado depende de hechos que no constan acreditados.")
        banda = nueva
    if ev.nli_neutral:
        # Una inferencia no literal resta solidez a la "doctrina consolidada", pero no crea una disparidad
        # entre tribunales: nunca se baja por NLI a una banda que describa algo que no ha ocurrido.
        motivos.append("Alguna afirmación no se deduce literalmente de la norma (inferencia).")
        if banda == BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE:
            banda = BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA
    return banda, motivos
