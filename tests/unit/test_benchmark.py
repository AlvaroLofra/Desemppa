from benchmark.blind_judge import cargar_casos, resumir
from benchmark.evaluator import puntuar
from benchmark.permutations import permutar
from benchmark.purge import hechos_purgados
from tests.conftest import FIXTURES, ROOT

CASO = {"id": "X", "esperado": {"estimacion_principal": "DEFENSA", "articulos_gold": ["BOE-A-1:a1", "BOE-A-1:a2"]}}


def _final(estimacion="DEFENSA", sids=("BOE:BOE-A-1:a1:2020-01-01",), estado="CERTIFICADA"):
    return {
        "estado": estado,
        "dictamen": {
            "cuestiones": [{"estimacion": estimacion, "fundamentos": [{"citas": [{}, {}]}]}],
            "fundamentos": [{"source_id": s} for s in sids],
        },
    }


def test_puntuar_deterministic_parts():
    p = puntuar(CASO, _final(), [{"id": "G2-G4", "ok": True, "detalle": []}])
    assert (p.outcome, p.recall, p.alucinacion) == (30, 15, 15) and p.total == 80
    p = puntuar(CASO, _final("CONTRAPARTE"), [{"id": "G2-G4", "ok": False, "detalle": ["x"]}])
    assert p.outcome == 0 and p.alucinacion == 7.5
    p = puntuar(CASO, _final(estado="BLOQUEADA"), [])
    assert p.outcome == 0 and p.recall == 0


def test_purge_removes_prior_instances_and_ids():
    texto = (FIXTURES / "sentencias" / "sap_fianza_sintetica.txt").read_text(encoding="utf-8")
    hechos = hechos_purgados(texto)
    assert "entregó las llaves" in hechos
    for fuga in ("SAP M 9999", "ECLI", "dictó sentencia", "recurso de apelación"):
        assert fuga not in hechos


def test_permutation_preserves_structure():
    texto = "El 1/6/2024 [[PERSONA_1]] pagó 900 euros a Inmobiliaria Sol S.L. en 2024."
    p = permutar(texto, seed=1, desplazamiento_anios=2)
    assert "2026" in p and "2024" not in p
    assert "[[PERSONA_1]]" not in p and "Inmobiliaria Sol S.L." not in p
    assert "euros" in p and "900 euros" not in p
    assert permutar(texto, seed=1, desplazamiento_anios=2) == p  # reproducible


def test_cases_load_and_summary():
    casos = cargar_casos(ROOT / "benchmark" / "cases")
    assert {c["id"] for c in casos} >= {"SYN-001", "SYN-002"}
    filas = [{"outcome": 30, "total": 80, "estado": "CERTIFICADA"}, {"outcome": 0, "total": 40, "estado": "ERROR"}]
    assert resumir(filas, "eco") == {
        "modo": "eco",
        "ejecuciones": 2,
        "outcome_match": 0.5,
        "total_medio": 60,
        "certificadas": 1,
    }
