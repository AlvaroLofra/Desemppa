"""Casos dorados del pipeline completo frente a un LLM ADVERSARIAL (sin red).

Ocho supuestos de materias distintas (despido, salarios, vicios ocultos, fianza, multa de tráfico, responsabilidad
patrimonial, estafa y desistimiento). En cada uno, el «Magistrado» simulado mezcla afirmaciones correctas con las
siete formas de invención que el cortafuegos debe parar:

  artículo inexistente · porcentaje de éxito · fecha inventada · cita no literal · fuente inexistente ·
  jurisprudencia sin sentencias · hecho que el ciudadano no contó (y un consejo que cita normas)

Invariantes comprobados en todos: nada inventado llega al ciudadano (y queda en la auditoría como eliminado), toda
afirmación jurídica mostrada tiene una cita literal verificada, los plazos son exactamente los del motor determinista,
hay postulación, la estimación es disyuntiva y ningún dato personal llega a ningún prompt.

Los textos del BOE son SINTÉTICOS (misma frase en todos los artículos): prueban la mecánica, no el Derecho.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

import httpx
import pytest

from connectors.boe_client import BOEClient, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine
from core.llm_types import LLMResult, StreamChunk
from core.materias import alias_de, normas, submaterias
from core.orchestrator import Orchestrator, Services
from core.state import ConsultaStore, Estado, EventBus

HOY = date(2026, 3, 20)
FECHA = "2026-03-02"
FRASE = (
    "El titular podrá ejercitar su derecho en el plazo que la ley establece y la otra parte deberá cumplir su "
    "obligación de buena fe."
)
PII = ("12345678Z", "ana.perez@example.com")
INVENCIONES = {
    "articulo": "Además, el artículo 9999 del Código Civil te da la razón sin ninguna duda.",
    "porcentaje": "Tienes un 85 % de probabilidades de ganar este asunto.",
    "fecha": "El plazo para actuar vence el 17 de marzo de 2031 sin posibilidad de prórroga.",
    "cita_falsa": "La ley obliga a la otra parte a indemnizarte con el doble de lo debido.",
    "fuente_inexistente": "La normativa sectorial reconoce expresamente tu derecho.",
    "jurisprudencia": "El Tribunal Supremo ha establecido que en casos como el tuyo se da la razón al ciudadano.",
    "hecho": "Como ya enviaste un burofax a la otra parte, tienes la prueba del requerimiento.",
    "consejo_con_norma": "Presenta el escrito citando el art. 1 de la Ley de Enjuiciamiento Civil.",
}
CORRECTAS = {
    "respuesta": "Sí: el titular puede ejercitar su derecho en el plazo que la ley establece.",
    "razonamiento": "La otra parte debe cumplir su obligación de buena fe.",
    "consejo": "Reúne todos los documentos que acrediten lo ocurrido.",
    "limite": "Necesitarás pruebas de lo que cuentas.",
}


@dataclass(frozen=True)
class Caso:
    id: str
    submateria: str
    texto: str
    municipio: str
    cuantia: float | None


CASOS = [
    Caso("despido", "SOC_DESPIDO_DISC", "Me entregaron una carta de despido disciplinario el 2 de marzo de 2026. "
         "Trabajaba de camarero y cobraba 1.500 euros al mes.", "Madrid", 1500),
    Caso("salarios", "SOC_RECLAMACION_CANTIDAD", "La empresa no me paga las nóminas; la última debía cobrarla el "
         "2 de marzo de 2026. Me deben 4.200 euros.", "Sevilla", 4200),
    Caso("vicios", "CIV_COMPRAVENTA_ARRAS_VICIOS", "Compré un piso y el 2 de marzo de 2026 aparecieron humedades "
         "que el vendedor ocultó. Pagué 180.000 euros.", "Valencia", 180000),
    Caso("fianza", "CIV_LAU_FIANZA", "Entregué las llaves del piso alquilado el 2 de marzo de 2026 y el casero no me "
         "devuelve la fianza de 900 euros.", "Madrid", 900),
    Caso("trafico", "ADM_TRAFICO_ORA", "El 2 de marzo de 2026 me notificaron una multa de tráfico de 200 euros por "
         "aparcar en zona azul.", "Barcelona", 200),
    Caso("patrimonial", "ADM_RESPONSABILIDAD_PATRIMONIAL", "El 2 de marzo de 2026 me caí por un socavón en la acera y "
         "me rompí la muñeca; quiero reclamar 3.000 euros al ayuntamiento.", "Zaragoza", 3000),
    Caso("estafa", "PEN_ESTAFAS_PATRIMONIO", "El 2 de marzo de 2026 pagué 600 euros por un móvil en una web que "
         "resultó falsa y nunca me lo enviaron. Quiero denunciar.", "Madrid", 600),
    Caso("desistimiento", "CIV_CONSUMO_DESISTIMIENTO_SUMINISTROS", "Compré un ordenador por internet el 2 de marzo de "
         "2026 por 300 euros y quiero devolverlo sin dar explicaciones.", "Bilbao", 300),
]  # fmt: skip


def _triaje(caso: Caso) -> dict:
    sub = submaterias()[caso.submateria]
    return {
        "jurisdiccion_principal": sub.jurisdiccion,
        "submateria_principal": caso.submateria,
        "ramas": [
            {
                "submateria": caso.submateria,
                "jurisdiccion": sub.jurisdiccion,
                "peso_enrutamiento": 1.0,
                "justificacion": "caso",
            }
        ],  # fmt: skip
        "grado_ambiguedad": 0.1,
        "fecha_hechos": FECHA,
        "fecha_inicio_plazo": FECHA if sub.plazos else None,
        "municipio": caso.municipio,
        "vecindad_civil": "comun",
        "cuantia_estimada_eur": caso.cuantia,
        "terminos_cendoj": [],
        "resumen_hechos": caso.texto,
        # «marzo de 2026» está en todas las consultas: los campos críticos constan con una cita literal.
        "campos_constan": [{"campo": c, "cita": "marzo de 2026"} for c in sub.campos_criticos],
        # El modelo «recuerda» artículos (incluido uno que no existe): solo se pueden pedir al BOE, nunca inventar.
        "normas_sugeridas": [{"norma": "CC", "articulos": ["9999"]}],
        "busquedas_boe": ["derecho del titular art. 54 BOE-A-2015-11430"],
    }


def _cita(sid: str, quote: str = FRASE) -> list[dict]:
    return [{"source_id": sid, "verbatim_quote": quote}]


def _alegato(rol: str, sid: str) -> dict:
    return {
        "rol": rol,
        "pretension": "pretensión",
        "cuestiones": [{"id": "C1", "argumentos": [{"afirmacion": CORRECTAS["razonamiento"], "citas": _cita(sid)}]}],
    }


def _magistrado(sid: str) -> dict:
    """Resolución que mezcla lo correcto con todas las formas de invención."""
    inv = INVENCIONES
    return {
        "cuestiones": [
            {
                "id": "C1",
                "enunciado": "¿Puede el ciudadano ejercitar su derecho?",
                "tipo": "calificacion_juridica",
                "estimacion": "DEFENSA",
                "fundamentos": [{"afirmacion": CORRECTAS["razonamiento"], "citas": _cita(sid)}],
            }
        ],
        "banda_propuesta": "criterio_consolidado_favorable",
        "razonamiento_banda": "x",
        "respuesta_directa": [{"texto": CORRECTAS["respuesta"], "tipo": "norma", "citas": _cita(sid)}],
        "resumen_ciudadano": [
            {"texto": CORRECTAS["razonamiento"], "tipo": "razonamiento", "citas": _cita(sid)},
            {"texto": inv["articulo"], "tipo": "norma", "citas": _cita(sid)},
            {"texto": inv["porcentaje"], "tipo": "razonamiento", "citas": _cita(sid)},
            {"texto": inv["fecha"], "tipo": "razonamiento", "citas": _cita(sid)},
            {
                "texto": inv["cita_falsa"],
                "tipo": "norma",
                "citas": _cita(sid, "la parte incumplidora indemnizará con el doble de lo debido al perjudicado"),
            },
            {"texto": inv["fuente_inexistente"], "tipo": "norma", "citas": _cita("BOE:BOE-A-1999-99999:a1:2000-01-01")},
            {"texto": inv["jurisprudencia"], "tipo": "razonamiento", "citas": _cita(sid)},
            {"texto": inv["hecho"], "tipo": "razonamiento", "citas": _cita(sid)},
        ],
        "fortalezas": [],
        "debilidades_contraparte": [],
        "riesgos_propios": [{"texto": CORRECTAS["limite"], "tipo": "limite"}],
        "pasos_inmediatos": [
            {"texto": CORRECTAS["consejo"], "tipo": "consejo"},
            {"texto": inv["consejo_con_norma"], "tipo": "consejo"},
        ],
    }


class RouterAdversarial:
    """LLM simulado: lee el dossier del prompt (como haría un modelo) y responde según el rol."""

    def __init__(self, triaje: dict) -> None:
        self.triaje = triaje
        self.llamadas: list[str] = []
        self.prompts: list[str] = []

    async def stream(self, profile, role, request, **kw):
        self.llamadas.append(role)
        self.prompts.append(request.system + "\n" + request.prompt)
        sid = next(iter(re.findall(r"\[(BOE:[^\]]+)\]", request.prompt)), "BOE:BOE-A-0000-0:a1:2000-01-01")
        if role == "triaje":
            payload = self.triaje
        elif role in ("defensa", "contraparte"):
            payload = _alegato(role.upper(), sid)
        elif role == "magistrado":
            payload = _magistrado(sid)
        elif role == "cribado":
            payload = {"elegidos": [0]}
        elif "### Frase" in request.prompt:  # hechos no constatados: el verificador detecta el burofax inventado
            frases = re.findall(r"### Frase (F\d+): (.*)", request.prompt)
            payload = {"no_constatados": [{"id": i, "motivo": "no consta"} for i, f in frases if "burofax" in f]}
        else:  # NLI de pares: lo que se afirma se deduce de la cita
            payload = {
                "resultados": [{"indice": i, "etiqueta": "ENTAILS"} for i in range(request.prompt.count("### Par"))]
            }
        text = json.dumps(payload, ensure_ascii=False)
        yield StreamChunk(text=text[:10])
        yield LLMResult(text=text, provider="fake", alias="fake", model=f"fake-{role}")


def _boe_sintetico() -> BOEClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        nid = path.split("/id/")[1].split("/")[0]
        if path.endswith("/metadatos"):
            alias = alias_de(nid) or ""
            titulo = normas().get(alias, {}).get("titulo", "Norma")
            meta = {"identificador": nid, "titulo": titulo, "rango": {"texto": "Ley"},
                    "ambito": {"texto": "Estatal"}, "estatus_derogacion": "N"}  # fmt: skip
            return httpx.Response(200, json={"data": [meta]})
        m = re.search(r"/texto/bloque/a(\d+)$", path)
        if m and m.group(1) != "9999":  # el artículo «recordado» por el modelo no existe en el BOE
            n = m.group(1)
            xml = (
                '<?xml version="1.0" encoding="utf-8"?><response><status><code>200</code></status><data>'
                f'<bloque id="a{n}" tipo="precepto" titulo="Artículo {n}">'
                f'<version id_norma="{nid}" fecha_publicacion="20000101" fecha_vigencia="20000101">'
                f"<p>Artículo {n}. Texto sintético de prueba.</p><p>{FRASE}</p></version></bloque></data></response>"
            )
            return httpx.Response(200, content=xml.encode())
        return httpx.Response(404)

    http = httpx.AsyncClient(base_url="https://boe.test", transport=httpx.MockTransport(handler))
    return BOEClient(client=http, max_rps=10_000)


def _texto_ciudadano(d: dict) -> str:
    partes = [d["respuesta_directa"], d["resumen_ciudadano"], *d["fortalezas"], *d["riesgos_propios"]]
    partes += [*d["pasos_inmediatos"], *(a["texto"] for a in d["afirmaciones"])]
    return "\n".join(partes)


@pytest.mark.parametrize("caso", CASOS, ids=[c.id for c in CASOS])
async def test_caso_dorado_adversarial(db, caso):
    router = RouterAdversarial(_triaje(caso))
    s = Services(
        router=router,
        boe=BOERepository(db, _boe_sintetico()),
        retriever=HybridRetriever(db),
        cendoj=CendojRepository(db),
        convenios=ConveniosRepository(db),
        calendar=CalendarEngine(),
        store=ConsultaStore(db),
        bus=EventBus(db),
        today=lambda: HOY,
    )
    texto = f"Me llamo Ana, DNI {PII[0]}, correo {PII[1]}. {caso.texto}"
    cid = s.store.create(texto, "eco")
    await Orchestrator(s).run(cid)
    c = s.store.get(cid)
    eventos = [(t, d) for _, t, d in s.bus.history(cid)]
    assert c.estado == Estado.CERTIFICADA, eventos[-1]
    d = c.dictamen["dictamen"]
    sub = submaterias()[caso.submateria]

    # 1. Nada inventado llega al ciudadano...
    visible = _texto_ciudadano(d)
    for prohibido in ("9999", "%", "2031", "Tribunal Supremo", "doble", "sectorial", "burofax", "art. 1 de la Ley"):
        assert prohibido not in visible, (prohibido, visible)
    # ...y todo queda en la auditoría como eliminado, con su motivo.
    eliminadas = {e["texto"] for e in d["auditoria"] if e["resultado"] == "eliminada"}
    assert set(INVENCIONES.values()) <= eliminadas
    assert all(e["motivos"] for e in d["auditoria"] if e["resultado"] == "eliminada")
    # 2. Lo correcto sí llega.
    assert d["respuesta_directa"].startswith("Sí: el titular puede ejercitar")
    assert CORRECTAS["consejo"] in d["pasos_inmediatos"] and CORRECTAS["limite"] in d["riesgos_propios"]
    # 3. Toda afirmación jurídica mostrada tiene al menos una cita literal a una fuente del dossier.
    fuentes = {e[1]["source_id"] for e in eventos if e[0] == "source"}
    for a in d["afirmaciones"]:
        if a["tipo"] in ("norma", "razonamiento"):
            assert a["citas"] and all(ci["source_id"] in fuentes for ci in a["citas"]), a
    # 4. Plazos: exactamente los del motor determinista para esta materia.
    motor = CalendarEngine()
    esperados = {
        p: motor.compute(p, date(2026, 3, 2), municipio_ine=c.triage["municipio_ine_organo"], hoy=HOY)
        for p in sub.plazos
    }
    assert {p["tipo_plazo_id"] for p in d["plazos"]} == set(sub.plazos)
    for p in d["plazos"]:
        assert p["fecha_limite_segura"] == esperados[p["tipo_plazo_id"]].fecha_limite_segura.isoformat()
    # 5. Postulación (abogado/procurador) y estimación disyuntiva.
    assert d["postulacion"] and d["postulacion"]["texto_usuario"]
    assert {q["estimacion"] for q in d["cuestiones"]} <= {"DEFENSA", "CONTRAPARTE"}
    # 6. El artículo 9999 «recordado» por el triaje no entra al dossier (no existe en el BOE).
    assert not any(":a9999:" in f for f in fuentes)
    # 7. Ningún dato personal llega a ningún modelo.
    for prompt in router.prompts:
        assert all(dato not in prompt for dato in PII)
    # 8. El Magistrado se repite como mucho dos veces (corrección + escalado): no hay bucles.
    assert router.llamadas.count("magistrado") <= 3
