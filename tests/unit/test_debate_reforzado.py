"""Debate reforzado: réplica de la Defensa (modos con `replica = true`) y cuestiones de plazo sin plazo calculado."""

from __future__ import annotations

from types import SimpleNamespace

from core.errors import ProviderTimeout
from core.orchestrator import Orchestrator, avisos_cuestiones_plazo
from core.schemas import ResolucionMagistradoSchema
from core.state import Estado
from tests.unit.test_orchestrator import ALEGATO, Q_BOE, TRIAJE_OK, magistrado, services  # noqa: F401  (fixture)

TEXTO = "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza por pintar."
REPLICA = {
    "rol": "DEFENSA",
    "pretension": "réplica",
    "cuestiones": [
        {
            "id": "C1",
            "argumentos": [
                {
                    "afirmacion": "La contraparte olvida el interés legal.",
                    "citas": [{"source_id": "BOE:x", "verbatim_quote": Q_BOE}],
                }
            ],
        }
    ],
}


def _con_replica(router, activa=True):
    router.catalog = SimpleNamespace(profiles={"eco": SimpleNamespace(replica=activa)}, models={})
    return router


async def test_la_replica_se_suma_a_la_defensa_y_la_ve_el_magistrado(services):  # noqa: F811
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE), REPLICA],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    _con_replica(router)
    prompts_magistrado: list[str] = []
    original = router.stream

    async def capturar(profile, role, request, **kw):
        if role == "magistrado":
            prompts_magistrado.append(request.prompt)
        async for x in original(profile, role, request, **kw):
            yield x

    router.stream = capturar
    cid = s.store.create(TEXTO, "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA
    assert router.calls[:4] == ["triaje", "defensa", "contraparte", "defensa"]
    assert c.debate["replica"]["cuestiones"][0]["argumentos"][0]["afirmacion"].startswith("La contraparte olvida")
    defensas = [d for _, t, d in s.bus.history(cid) if t == "debate_done" and d["rol"] == "defensa"]
    assert len(defensas) == 2 and defensas[1]["replica"] is True
    assert len(defensas[1]["alegato"]["cuestiones"][0]["argumentos"]) == 2
    assert defensas[1]["verificacion"][1][0]["ok"] is False  # cita a una fuente que no existe: se marca
    # El Magistrado recibe la réplica en su prompt.
    assert prompts_magistrado and "RÉPLICA DE LA DEFENSA" in prompts_magistrado[0]
    assert "La contraparte olvida el interés legal." in prompts_magistrado[0]


async def test_si_la_replica_falla_se_sigue_sin_ella(services):  # noqa: F811
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [
                ALEGATO("DEFENSA", Q_BOE),
                ProviderTimeout("x", provider="x"),
                ProviderTimeout("x", provider="x"),
            ],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    _con_replica(router)
    cid = s.store.create(TEXTO, "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    assert c.estado == Estado.CERTIFICADA and "replica" not in c.debate
    assert any("réplica de la defensa no se pudo completar" in a for a in c.dictamen["dictamen"]["avisos"])


async def test_sin_replica_en_el_modo_no_hay_llamada_extra(services):  # noqa: F811
    s, router = services(
        {
            "triaje": [TRIAJE_OK],
            "defensa": [ALEGATO("DEFENSA", Q_BOE)],
            "contraparte": [ALEGATO("CONTRAPARTE", Q_BOE)],
            "magistrado": [magistrado()],
        }
    )
    _con_replica(router, activa=False)
    cid = s.store.create(TEXTO, "eco")
    await Orchestrator(s).run(cid)
    assert router.calls.count("defensa") == 1


def test_cuestion_de_plazo_sin_plazo_calculado_avisa():
    res = ResolucionMagistradoSchema.model_validate(
        {
            **magistrado(),
            "cuestiones": [{**magistrado()["cuestiones"][0], "tipo": "plazo", "enunciado": "¿Ha caducado?"}],
        }
    )
    [aviso] = avisos_cuestiones_plazo(res, [])
    assert "¿Ha caducado?" in aviso and "no se da ninguna fecha" in aviso
    assert avisos_cuestiones_plazo(res, [object()]) == []  # con plazo del motor no hace falta
    assert avisos_cuestiones_plazo(ResolucionMagistradoSchema.model_validate(magistrado()), []) == []


def test_pro_tiene_replica_y_los_demas_modos_no(catalog):
    assert catalog.profiles["pro"].replica is True
    assert not catalog.profiles["eco"].replica and not catalog.profiles["equilibrado"].replica
