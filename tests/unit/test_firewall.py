"""Cortafuegos anti-invención: cada invención inyectada debe acabar eliminada, reclasificada o señalada.

Sin red: fuentes sintéticas con textos reales (LAU art. 36, CC art. 1561, Reglamento 261/2004 art. 7) y un router
simulado para la NLI y la comprobación de hechos.
"""

import asyncio
import json
import re
from datetime import date

import pytest

from core.firewall import Contexto, escanear, numeros_en, verificar_afirmaciones
from core.llm_types import LLMResult
from core.schemas import Afirmacion, ArticuloBOE, ArticuloUE, ExtractoSentencia, PlazoCalculado

HOY = date(2026, 10, 24)
LAU36 = (
    "Artículo 36. Fianza.\n4. El saldo de la fianza en metálico que deba ser restituido al arrendatario al final del "
    "arriendo, devengará el interés legal, transcurrido un mes desde la entrega de las llaves por el mismo sin que se "
    "hubiere hecho efectiva dicha restitución."
)
CC1561 = (
    "Artículo 1561. El arrendatario debe devolver la finca, al concluir el arriendo, tal como la recibió, salvo lo que "
    "hubiese perecido o se hubiera menoscabado por el tiempo o por causa inevitable."
)
UE7 = (
    "Artículo 7\nDerecho a compensación\n1. Cuando se haga referencia al presente artículo, los pasajeros recibirán "
    "una compensación por valor de:\na) 250 euros para vuelos de hasta 1500 kilómetros;"
)
FUENTES = {
    "BOE:BOE-A-1994-26003:a36:2019-03-06": ArticuloBOE(
        source_id="BOE:BOE-A-1994-26003:a36:2019-03-06",
        titulo="Artículo 36 LAU",
        texto_verbatim=LAU36,
        id_norma="BOE-A-1994-26003",
        id_bloque="a36",
        version_fecha_vigencia=date(2019, 3, 6),
        vigente_a_fecha_hechos=True,
    ),
    "BOE:BOE-A-1889-4763:art1561:1889-08-16": ArticuloBOE(
        source_id="BOE:BOE-A-1889-4763:art1561:1889-08-16",
        titulo="Artículo 1561 CC",
        texto_verbatim=CC1561,
        id_norma="BOE-A-1889-4763",
        id_bloque="art1561",
        version_fecha_vigencia=date(1889, 8, 16),
        vigente_a_fecha_hechos=True,
    ),
    "EUR:32004R0261:art7": ArticuloUE(
        source_id="EUR:32004R0261:art7",
        titulo="Art. 7 Reglamento (CE) 261/2004 (Derecho a compensación)",
        texto_verbatim=UE7,
        celex="32004R0261",
        articulo="7",
    ),
}
LAU = "BOE:BOE-A-1994-26003:a36:2019-03-06"
CC = "BOE:BOE-A-1889-4763:art1561:1889-08-16"
UE = "EUR:32004R0261:art7"
HECHOS = "Entregué las llaves el 1 de septiembre de 2026 y el casero no me devuelve la fianza de 900 euros."
PLAZO = PlazoCalculado(
    tipo_plazo_id="CIV_FIANZA_DEVOLUCION_1M",
    descripcion="Plazo del arrendador para devolver la fianza",
    naturaleza="sustantivo",
    tipo_computo="meses_fecha_a_fecha",
    titular="contraparte",
    fecha_inicio=date(2026, 9, 1),
    fecha_limite_segura=date(2026, 10, 1),
    base_legal="Art. 36.4 LAU",
)


@pytest.fixture
def ctx():
    return Contexto(fuentes=dict(FUENTES), hechos=HECHOS, hoy=HOY, plazos=[PLAZO], numeros_plazos={1.0})


# ---------- escáner determinista ----------


@pytest.mark.parametrize(
    "texto",
    [
        "El art. 36 LAU obliga a devolver la fianza.",
        "Según el artículo 1561 del Código Civil, el desgaste por el tiempo no es imputable.",
        "El art. 7 del Reglamento (CE) 261/2004 fija 250 euros.",
        "Reclama los 900 euros de la fianza.",
        "Pasado un mes desde la entrega de llaves, el saldo devenga interés.",
        "Devolviste las llaves el 1 de septiembre de 2026.",
        "El plazo del casero venció el 1 de octubre de 2026.",
    ],
)
def test_referencias_con_respaldo_pasan(ctx, texto):
    assert escanear(texto, ctx) == []


@pytest.mark.parametrize(
    ("texto", "tipo"),
    [
        ("El art. 37 LAU también te protege.", "norma"),  # artículo real que no está en el dossier
        ("Según el art. 9999 del Código Civil, ganas.", "norma"),  # artículo inexistente
        ("El art. 36 del Código Civil obliga a devolverla.", "norma"),  # número de otra ley con el mismo artículo
        ("El art. 1561 LAU lo dice claro.", "norma"),  # artículo cambiado de ley
        ("La Ley 49/1960 regula este caso.", "norma"),  # ley del catálogo ausente del dossier
        ("Lo establece la Ley 12/2023 por el derecho a la vivienda.", "norma"),
        ("El Reglamento (UE) 2019/1150 lo impone.", "norma"),  # norma europea ausente
        ("La STS 123/2020 es clara.", "jurisprudencia"),  # sentencia inventada
        ("La sentencia C-28/20 del TJUE lo resolvió.", "jurisprudencia"),
        ("El Tribunal Supremo ha establecido que siempre se devuelve.", "jurisprudencia"),
        ("ROJ: STS 4567/2021 lo confirma.", "jurisprudencia"),
        ("Te corresponden 1.200 euros de indemnización.", "cifra"),  # importe inventado
        ("Tienes un recargo del 20 % por mora.", "cifra"),  # porcentaje inventado
        ("Tienes 30 días para reclamar.", "cifra"),  # duración inventada
        ("Dispones de quince días hábiles.", "cifra"),  # en letra
        ("La entrega fue el 30 de septiembre de 2026.", "fecha"),  # fecha calculada por el modelo
        ("El plazo vence el 15 de noviembre de 2026.", "fecha"),
    ],
)
def test_invenciones_detectadas(ctx, texto, tipo):
    hallazgos = escanear(texto, ctx)
    assert hallazgos and hallazgos[0].tipo == tipo, (texto, hallazgos)


def test_consejo_no_puede_citar_normas(ctx):
    assert escanear("Envía un burofax citando el art. 36 LAU.", ctx, permite_referencias=False)
    assert escanear("Envía un burofax reclamando los 900 euros.", ctx, permite_referencias=False) == []


def test_cifras_solo_de_las_fuentes_citadas(ctx):
    # 250 € está en el Reglamento, pero si la afirmación solo cita la LAU, no tiene respaldo
    assert escanear("Te corresponden 250 euros.", ctx, citas=[UE]) == []
    assert escanear("Te corresponden 250 euros.", ctx, citas=[LAU])


def test_jurisprudencia_permitida_si_esta_en_el_corpus(ctx):
    sentencia = ExtractoSentencia(
        source_id="ROJ:SAP M 9999/2024",
        titulo="SAP M 9999/2024",
        texto_verbatim="Repintar tras varios años no es imputable al arrendatario.",
        roj="SAP M 9999/2024",
        tribunal="AP Madrid",
        nivel="AP",
        fecha_resolucion=date(2024, 3, 1),
        seccion="fundamentos_mayoria",
    )
    ctx2 = Contexto(fuentes={**FUENTES, sentencia.source_id: sentencia}, hechos=HECHOS, hoy=HOY)
    assert escanear("La Audiencia Provincial ha considerado que no se descuenta (SAP M 9999/2024).", ctx2) == []


def test_numeros_en_letra_y_con_miles():
    assert {20.0, 2000.0, 10.0} <= numeros_en("veinte días, 2.000 euros y el diez por ciento")


# ---------- verificador de afirmaciones ----------


class RouterSimulado:
    """NLI: CONTRADICTS si la hipótesis contiene «nunca», NEUTRAL si contiene «probablemente», si no ENTAILS.
    Hechos: marca como no constatadas las frases con «alega» o «ofreció»."""

    def __init__(self, falla=False):
        self.falla = falla

    async def stream(self, profile, role, request, **kw):
        from core.errors import ProviderTimeout

        if self.falla:
            raise ProviderTimeout("timeout", provider="x")
        if "### Par" in request.prompt:
            hip = re.findall(r"HIPÓTESIS: (.*)", request.prompt)
            etiquetas = [
                "CONTRADICTS" if "nunca" in h.lower() else "NEUTRAL" if "probablemente" in h.lower() else "ENTAILS"
                for h in hip
            ]
            payload = {"resultados": [{"id": f"P{i}", "etiqueta": e} for i, e in enumerate(etiquetas)]}
        else:
            frases = re.findall(r"### Frase F(\d+): (.*)", request.prompt)
            payload = {"no_constatados": [{"id": f"F{i}"} for i, f in frases if "alega" in f or "ofreció" in f]}
        yield LLMResult(text=json.dumps(payload), provider="sim", alias="sim", model="sim")


def _a(texto, tipo, *citas):
    return Afirmacion(
        texto=texto,
        tipo=tipo,
        citas=[{"source_id": sid, "verbatim_quote": q} for sid, q in citas],
    )


Q_LAU = "devengará el interés legal, transcurrido un mes desde la entrega de las llaves"
Q_CC = "salvo lo que hubiese perecido o se hubiera menoscabado por el tiempo"


def _verificar(ctx, afirmaciones, router=None):
    return asyncio.run(verificar_afirmaciones(afirmaciones, ctx, router or RouterSimulado(), "eco"))


def test_afirmaciones_correctas_se_aceptan(ctx):
    r = _verificar(
        ctx,
        [
            (
                "respuesta",
                _a("Pasado un mes desde la entrega de llaves, la fianza genera interés.", "norma", (LAU, Q_LAU)),
            ),
            ("resumen", _a("Devolviste las llaves el 1 de septiembre de 2026.", "hecho")),
            ("paso", _a("Envía un burofax reclamando los 900 euros.", "consejo")),
            ("riesgo", _a("No consta cómo estaba el piso al entrar.", "limite")),
        ],
    )
    assert [v.estado for v in r.veredictos] == ["aceptada"] * 4 and r.fallos() == []


@pytest.mark.parametrize(
    ("afirmacion", "motivo"),
    [
        (_a("El casero debe pagarte intereses.", "norma"), "sin ninguna cita verificada"),  # norma sin cita
        (
            _a("El casero debe pagarte intereses.", "norma", (LAU, "el casero pagará intereses del cinco por ciento")),
            "no literal",
        ),  # cita parafraseada
        (
            _a("El casero debe pagarte intereses.", "norma", ("BOE:BOE-A-1994-26003:a99:2019-03-06", Q_LAU)),
            "fuente inexistente",
        ),
        (_a("El casero nunca debe devolver la fianza.", "norma", (LAU, Q_LAU)), "contradice"),  # NLI
        (_a("La aerolínea alega que debes esperar.", "hecho"), "no consta en la consulta"),  # hecho inventado
        (_a("El casero te ofreció 300 euros.", "razonamiento", (LAU, Q_LAU)), "importe"),  # cifra inventada
        (_a("Reclama citando el art. 36 LAU.", "consejo"), "no puede citar normas"),
        (_a("Ganarás con la STS 123/2020.", "razonamiento", (LAU, Q_LAU)), "corpus"),
    ],
)
def test_afirmaciones_inventadas_se_eliminan(ctx, afirmacion, motivo):
    r = _verificar(ctx, [("resumen", afirmacion)])
    v = r.veredictos[0]
    assert v.estado == "eliminada" and any(motivo in m for m in v.motivos), v.motivos
    assert r.fallos()  # el Magistrado recibe el motivo para corregirse


def test_norma_que_no_se_deduce_literalmente_pasa_a_razonamiento(ctx):
    r = _verificar(
        ctx, [("resumen", _a("Probablemente el desgaste de la pintura sea ordinario.", "norma", (CC, Q_CC)))]
    )
    v = r.veredictos[0]
    assert v.estado == "reclasificada" and v.tipo_final == "razonamiento"


def test_si_falla_la_nli_las_normas_quedan_como_razonamiento(ctx):
    r = _verificar(
        ctx,
        [("resumen", _a("Pasado un mes, la fianza genera interés.", "norma", (LAU, Q_LAU)))],
        RouterSimulado(falla=True),
    )
    assert r.veredictos[0].tipo_final == "razonamiento" and r.avisos


def test_firewall_completo_cifras_de_la_ue(ctx):
    r = _verificar(
        ctx,
        [
            (
                "respuesta",
                _a(
                    "Te corresponden 250 euros por la cancelación.",
                    "norma",
                    (UE, "a) 250 euros para vuelos de hasta 1500 kilómetros"),
                ),
            )
        ],
    )
    assert r.veredictos[0].estado == "aceptada"


def test_base_legal_de_plazos_y_postulacion_respalda_lo_que_se_diga():
    ctx = Contexto(
        fuentes=dict(FUENTES),
        hechos=HECHOS,
        hoy=HOY,
        referencias_extra=["Art. 1968.2 CC", "Arts. 93 y 95 RDLeg 6/2015 (Ley de Tráfico)", "arts. 5 y 10 LO 1/2025"],
    )
    assert escanear("El plazo es de un año (art. 1968.2 CC).", ctx) == []
    assert escanear("Lo regula el art. 95 del RDLeg 6/2015.", ctx) == []
    assert escanear("Antes hay que negociar (arts. 5 y 10 LO 1/2025).", ctx) == []
    assert escanear("El art. 1973 CC interrumpe el plazo.", ctx)  # sigue sin estar respaldado


def test_nli_por_identificador_aunque_el_modelo_desordene_o_cuente_desde_uno():
    from core.nli import _indice

    assert _indice({"id": "P3"}, "P") == 3 and _indice({"indice": 2}, "P") == 2 and _indice({"id": "x"}, "P") == -1
