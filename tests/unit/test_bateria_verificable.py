"""Humo de la batería verificable: evaluación automática y expediente sin LLM ni red."""

import json
from pathlib import Path

from benchmark.evaluar import evaluar
from benchmark.expediente import expediente_md

CASOS = Path(__file__).resolve().parents[2] / "benchmark" / "casos_verificables"
LAU36 = "BOE:BOE-A-1994-26003:a36:2019-03-06"
TEXTO_36 = "El saldo de la fianza en metálico que deba ser restituido al arrendatario devengará el interés legal."


def _caso() -> dict:
    return json.loads((CASOS / "V01.json").read_text(encoding="utf-8"))


def _res(cita: str) -> dict:
    dictamen = {
        "respuesta_directa": "La fianza devenga interés legal.",
        "resumen_ciudadano": "",
        "afirmaciones": [
            {
                "seccion": "respuesta",
                "tipo": "norma",
                "texto": "La fianza devenga interés legal.",
                "citas": [{"source_id": LAU36, "verbatim_quote": cita}],
            },
        ],
        "fundamentos": [],
        "plazos": [],
        "postulacion": None,
    }
    return {
        "estado": "CERTIFICADA",
        "fecha": "2026-10-25",
        "aclaraciones": [],
        "fuentes": {LAU36: {"titulo": "Artículo 36 LAU", "texto": TEXTO_36, "url": "https://www.boe.es"}},
        "dictamen": {"estado": "CERTIFICADA", "dictamen": dictamen},
    }


def test_los_30_casos_tienen_hoja_de_verdad_y_campos_obligatorios():
    casos = sorted(CASOS.glob("V*.json"))
    assert len(casos) == 30
    for f in casos:
        c = json.loads(f.read_text(encoding="utf-8"))
        assert {"id", "categoria", "consulta", "verdad"} <= set(c)
        assert (CASOS / "hojas" / f.name).exists(), f.name


def test_evaluar_detecta_una_cita_no_literal():
    buena = evaluar(_caso(), None, _res("deba ser restituido al arrendatario devengará el interés legal"))
    mala = evaluar(_caso(), None, _res("la fianza genera intereses del cinco por ciento"))
    assert buena["checks"]["citas_literales"]["ok"] is True
    assert mala["checks"]["citas_literales"]["ok"] is False


def test_expediente_incluye_fuente_completa_y_hoja_de_verdad():
    caso = _caso()
    hoja = json.loads((CASOS / "hojas" / "V01.json").read_text(encoding="utf-8"))
    md = expediente_md(caso, hoja, _res("devengará el interés legal"))
    assert "## 5. Texto completo de las fuentes citadas" in md and TEXTO_36 in md
    assert "## 6. Hoja de verdad" in md and hoja["articulos"][0]["sha256"][:16] in md
