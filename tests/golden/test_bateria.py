"""Regresión de la batería verificable: los casos que pasaron 7/7 con modelos reales (congelados con
`benchmark/congelar.py`) se vuelven a evaluar sin LLM ni red. Si un cambio en el evaluador, el cortafuegos o el motor
de plazos rompe uno, este test lo dice."""

import json
from pathlib import Path

import pytest

from benchmark.evaluar import evaluar

CONGELADOS = sorted((Path(__file__).parent / "bateria").glob("V*.json"))


@pytest.mark.parametrize("fichero", CONGELADOS, ids=[f.stem for f in CONGELADOS])
def test_caso_congelado_sigue_pasando(fichero: Path) -> None:
    d = json.loads(fichero.read_text(encoding="utf-8"))
    ev = evaluar(d["caso"], d["hoja"], d["resultado"])
    fallos = {k: c["detalle"] for k, c in ev["checks"].items() if not c["ok"]}
    assert not fallos, fallos
