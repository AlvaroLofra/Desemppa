"""Orquestador del pipeline de 4 fases (dossier §2.2–2.4): triaje, ingesta, juicio contradictorio y
guardarraíles. Emite eventos SSE por el EventBus; nunca deja que el LLM calcule fechas ni elija normas."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel, ValidationError

from connectors.boe_client import BOEError, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine, PlazoError
from core.errors import ProviderError
from core.llm_types import LLMRequest, LLMResult
from core.materias import Submateria, catalogo_para_prompt, id_norma, submaterias
from core.nli import NLIChecker, extract_json
from core.normalize import fold
from core.postulacion_rules import CasoPostulacion, evaluar
from core.router import ModelRouter
from core.schemas import (
    AVISO_LEGAL,
    BANDA_TEXTO,
    AlegatoSchema,
    AlertaPlazo,
    ArticuloBOE,
    BandaSolidez,
    Cita,
    ClausulaConvenio,
    DictamenCertificadoSchema,
    DossierIngestaSchema,
    ExtractoSentencia,
    FragmentoFuente,
    Fundamento,
    Jurisdiccion,
    NormaObjetivo,
    PlazoCalculado,
    PreguntaAclaratoria,
    RamaCandidata,
    ResolucionMagistradoSchema,
    TriageOutputSchema,
)
from core.state import ConsultaStore, Estado, EventBus
from core.temporal_sync import select_version
from core.validators import EvidenciaBanda, coherent_band, find_pronosticos, verify_quote

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parent / "prompts"
MAX_FUENTE_CHARS = 6000
M = TypeVar("M", bound=BaseModel)


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


_fold = fold


class TriageLLM(BaseModel):
    """Salida cruda del LLM de triaje (tolerante); el código la convierte en TriageOutputSchema."""

    jurisdiccion_principal: str = "fuera_alcance"
    submateria_principal: str = ""
    ramas: list[dict[str, Any]] = []
    grado_ambiguedad: float = 0.0
    preguntas_aclaracion: list[dict[str, Any]] = []
    datos_criticos_faltantes: list[str] = []
    fecha_hechos: date | None = None
    fecha_inicio_plazo: date | None = None
    municipio: str | None = None
    vecindad_civil: str = "desconocida"
    cuantia_estimada_eur: float | None = None
    terminos_cendoj: list[str] = []
    convenio_aplicable: str | None = None
    resumen_hechos: str = ""


@dataclass
class Services:
    router: ModelRouter
    boe: BOERepository
    retriever: HybridRetriever
    cendoj: CendojRepository
    convenios: ConveniosRepository
    calendar: CalendarEngine
    store: ConsultaStore
    bus: EventBus
    today: Callable[[], date] = date.today


@dataclass
class _Run:
    consulta_id: str
    modo: str
    modelos: dict[str, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(self, services: Services) -> None:
        self.s = services

    # ---------- utilidades ----------
    def _emit(self, run: _Run, tipo: str, data: dict[str, Any]) -> None:
        self.s.bus.emit(run.consulta_id, tipo, data)

    def _estado(self, run: _Run, estado: Estado) -> None:
        self.s.store.set_estado(run.consulta_id, estado)
        self._emit(run, "phase", {"estado": estado.value})

    async def _llm_json(
        self, run: _Run, role: str, system: str, prompt: str, model: type[M], *, delta_rol: str | None = None
    ) -> M:
        """Llama al rol con salida JSON y valida con Pydantic; 1 reintento con el error como feedback."""
        last_error = ""
        for intento in range(2):
            full_prompt = prompt
            if last_error:
                full_prompt += f"\n\nTu respuesta anterior no era válida ({last_error[:600]}). Devuelve SOLO el JSON."
            text = ""
            async for item in self.s.router.stream(
                run.modo,
                role,
                LLMRequest(system=system, prompt=full_prompt, json_mode=True),
                fase=role,
                consulta_id=run.consulta_id,
                restartable=True,  # solo se usa el JSON final: un corte a mitad puede repetirse en otro modelo
            ):
                if isinstance(item, LLMResult):
                    text = item.text
                    run.modelos[role] = item.model
                    if item.degradado:
                        run.avisos.extend(item.avisos)
                        self._emit(run, "quota", {"rol": role, "avisos": item.avisos, "modelo": item.model})
                elif delta_rol:
                    self._emit(run, "debate_delta", {"rol": delta_rol, "text": item.text})
            try:
                return model.model_validate(extract_json(text))
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)
                log.warning("salida inválida de %s (intento %d): %s", role, intento + 1, last_error[:300])
        raise ProviderError(f"El modelo del rol '{role}' no devolvió un JSON válido: {last_error[:300]}")

    def _municipio_ine(self, nombre: str | None) -> str | None:
        if not nombre:
            return None
        target = _fold(nombre)
        municipios = self.s.calendar.festivos.municipios
        exact = [m.codigo_ine for m in municipios.values() if _fold(m.nombre) == target]
        if not exact:
            exact = [m.codigo_ine for m in municipios.values() if target in [_fold(p) for p in m.nombre.split("/")]]
        return exact[0] if len(exact) == 1 else None

    # ---------- Fase 1 ----------
    async def _triaje(self, run: _Run) -> TriageOutputSchema | None:
        c = self.s.store.get(run.consulta_id)
        self._estado(run, Estado.TRIAJE)
        hoy = self.s.today()
        texto = c.texto_seudonimizado
        if c.aclaraciones:
            texto += "\n\nACLARACIONES DEL USUARIO:\n" + "\n".join(
                f"- {a['pregunta']}: {a['respuesta']}" for a in c.aclaraciones
            )
        for adj in c.adjuntos:
            if adj.get("permitido"):
                texto += f"\n\nDOCUMENTO ADJUNTO ({adj['tipo']}, {adj['nombre']}):\n{adj['texto'][:3000]}"
            else:
                texto += f"\n\n(El usuario aporta un documento de tipo '{adj['tipo']}' cuyo contenido no se comparte.)"
                run.avisos.append(
                    f"El contenido de «{adj['nombre']}» no se ha enviado a los modelos (sin tu "
                    "consentimiento): el análisis no lo tiene en cuenta."
                )
        convenios = {c["codigo"]: c for c in self.s.convenios.indexados()}
        lista_convenios = "\n".join(
            f"- {c['codigo']} · {c['denominacion']} · {c['sector']} · {c['territorio']}" for c in convenios.values()
        )
        system = (
            _prompt("triaje")
            .replace("{hoy}", hoy.isoformat())
            .replace("{catalogo}", catalogo_para_prompt())
            .replace("{convenios}", lista_convenios or "(ninguno indexado: usa null)")
        )
        raw = await self._llm_json(run, "triaje", system, f"CONSULTA DEL CIUDADANO:\n{texto}", TriageLLM)
        cat = submaterias()
        principal = (
            raw.submateria_principal
            if raw.submateria_principal in cat
            else next((r.get("submateria") for r in raw.ramas if r.get("submateria") in cat), None)
        )
        if principal is None:
            principal = "FUERA_PENAL" if raw.jurisdiccion_principal == "penal" else None
        sub: Submateria | None = cat.get(principal) if principal else None
        municipio_ine = c.municipio_ine or self._municipio_ine(raw.municipio)
        preguntas = [
            PreguntaAclaratoria.model_validate({"tipo_respuesta": "texto", **p})
            for p in raw.preguntas_aclaracion[:5]
            if p.get("texto")
        ]
        faltan = list(raw.datos_criticos_faltantes)
        if sub and sub.plazos and raw.fecha_inicio_plazo is None:
            evento = sub.campos_criticos[0] if sub.campos_criticos else "fecha de inicio del plazo"
            if not any(p.tipo_respuesta == "fecha" for p in preguntas):
                preguntas.append(
                    PreguntaAclaratoria(
                        id="q_fecha", texto=f"¿Cuál es la {evento}?", tipo_respuesta="fecha", motivo="cálculo de plazos"
                    )
                )
        if (
            sub
            and municipio_ine is None
            and not sub.fuera_alcance
            and not any(p.tipo_respuesta == "municipio" for p in preguntas)
        ):
            preguntas.append(
                PreguntaAclaratoria(
                    id="q_municipio",
                    texto="¿En qué municipio está el juzgado o el organismo (o, si no lo sabes, tu municipio)?",
                    tipo_respuesta="municipio",
                    motivo="festivos locales del calendario",
                )
            )
        if raw.grado_ambiguedad >= 0.35 and not preguntas:
            preguntas.append(
                PreguntaAclaratoria(
                    id="q_amb",
                    texto="¿Puedes dar más detalles de lo ocurrido?",
                    tipo_respuesta="texto",
                    motivo="ambigüedad",
                )
            )
        ya_aclarado = bool(c.aclaraciones)
        if ya_aclarado:  # una sola ronda: lo que falte se convierte en aviso
            if preguntas:
                run.avisos.append("Faltan datos tras la aclaración: " + "; ".join(p.texto for p in preguntas))
            preguntas = []
        try:
            jur = Jurisdiccion(sub.jurisdiccion if sub else raw.jurisdiccion_principal)
        except ValueError:
            jur = Jurisdiccion.FUERA_ALCANCE
        ramas = []
        for r in raw.ramas[:4]:
            if r.get("submateria") in cat:
                ramas.append(
                    RamaCandidata(
                        submateria=r["submateria"],
                        jurisdiccion=Jurisdiccion(cat[r["submateria"]].jurisdiccion),
                        peso_enrutamiento=min(1.0, max(0.0, float(r.get("peso_enrutamiento", 0.5)))),
                        justificacion=str(r.get("justificacion", ""))[:400],
                    )
                )
        if not ramas:
            ramas = [
                RamaCandidata(
                    submateria=principal or "desconocida",
                    jurisdiccion=jur,
                    peso_enrutamiento=1.0,
                    justificacion="rama única",
                )
            ]
        triage = TriageOutputSchema(
            consulta_id=run.consulta_id,
            jurisdiccion_principal=jur,
            submateria_principal=principal or "desconocida",
            ramas=ramas,
            grado_ambiguedad=min(1.0, max(0.0, raw.grado_ambiguedad))
            if not ya_aclarado
            else min(raw.grado_ambiguedad, 0.34),
            preguntas_aclaracion=preguntas,
            datos_criticos_faltantes=[] if ya_aclarado else faltan,
            fecha_hechos=raw.fecha_hechos or raw.fecha_inicio_plazo,
            municipio_ine_organo=municipio_ine,
            vecindad_civil=cast(Any, raw.vecindad_civil)
            if raw.vecindad_civil in ("comun", "catalana", "aragonesa", "navarra", "vasca", "gallega", "balear")
            else "desconocida",
            cuantia_estimada_eur=raw.cuantia_estimada_eur,
            alertas_plazo=[
                AlertaPlazo(
                    tipo_plazo_id=p,
                    fecha_inicio_computo=raw.fecha_inicio_plazo,
                    evento_inicio=(sub.campos_criticos[0] if sub and sub.campos_criticos else ""),
                )
                for p in (sub.plazos if sub else [])
            ],
            normas_boe_objetivo=[
                NormaObjetivo(id_norma=id_norma(n.norma), articulos=n.articulos, motivo=n.norma)
                for n in (sub.normas if sub else [])
            ],
            terminos_cendoj=(raw.terminos_cendoj or (sub.terminos_cendoj if sub else []))[:8],
            # Solo códigos que existen en la base local: un código inventado por el modelo se descarta.
            convenio_aplicable=raw.convenio_aplicable if raw.convenio_aplicable in convenios else None,
            competencia_local=bool(sub and sub.competencia_local),
        )
        self.s.store.save(
            run.consulta_id, triage_json={**triage.model_dump(mode="json"), "resumen_hechos": raw.resumen_hechos}
        )
        self._emit(
            run,
            "triage",
            {
                **triage.model_dump(mode="json"),
                "resumen_hechos": raw.resumen_hechos,
                "submateria_descripcion": sub.descripcion if sub else None,
            },
        )
        if sub is None or sub.fuera_alcance or jur in (Jurisdiccion.PENAL, Jurisdiccion.FUERA_ALCANCE):
            self._estado(run, Estado.FUERA_DE_ALCANCE)
            self._emit(
                run,
                "final",
                {
                    "estado": "FUERA_DE_ALCANCE",
                    "mensaje": (
                        "Esta consulta queda fuera del alcance de Iuris-IA (asuntos penales o no identificados). "
                        "Consulta con un abogado o solicita asistencia jurídica gratuita."
                    ),
                    "aviso_legal": AVISO_LEGAL,
                },
            )
            return None
        if triage.preguntas_aclaracion:
            self._estado(run, Estado.ESPERANDO_ACLARACION)
            self._emit(
                run, "clarification_needed", {"preguntas": [p.model_dump() for p in triage.preguntas_aclaracion]}
            )
            return None
        return triage

    # ---------- Fase 2 ----------
    async def _ingesta(self, run: _Run, triage: TriageOutputSchema, resumen: str) -> DossierIngestaSchema:
        self._estado(run, Estado.INGESTA)
        c = self.s.store.get(run.consulta_id)
        avisos: list[str] = []
        articulos: list[ArticuloBOE] = []
        for norma in triage.normas_boe_objetivo:
            for art in norma.articulos:
                try:
                    bloque = await self.s.boe.get_articulo(norma.id_norma, art)
                except BOEError as exc:
                    avisos.append(f"No se pudo obtener el art. {art} ({norma.motivo}) del BOE: {exc}")
                    continue
                va = select_version(bloque, triage.fecha_hechos)
                avisos.extend(va.avisos)
                if va.version is None:
                    continue
                fuente = ArticuloBOE(
                    source_id=f"BOE:{norma.id_norma}:{bloque.id_bloque}:{va.version.vigencia_desde.isoformat()}",
                    titulo=f"{bloque.titulo} {norma.motivo}",
                    texto_verbatim=va.version.texto[:MAX_FUENTE_CHARS],
                    url_oficial=f"https://www.boe.es/buscar/act.php?id={norma.id_norma}#{bloque.id_bloque}",
                    id_norma=norma.id_norma,
                    id_bloque=bloque.id_bloque,
                    version_fecha_vigencia=va.version.vigencia_desde,
                    vigente_a_fecha_hechos=va.vigente_a_fecha_hechos,
                    reformado_tras_fecha_hechos=va.reformado_tras_fecha_hechos,
                )
                articulos.append(fuente)
                self._emit(
                    run,
                    "source",
                    {
                        "source_id": fuente.source_id,
                        "tipo": "boe",
                        "titulo": fuente.titulo,
                        "url": fuente.url_oficial,
                        "extracto": fuente.texto_verbatim[:280],
                    },
                )
        jur_filtro = {"administrativa_previa": "contencioso"}.get(
            triage.jurisdiccion_principal.value, triage.jurisdiccion_principal.value
        )
        query = " ".join([resumen, *triage.terminos_cendoj])
        sentencias: list[ExtractoSentencia] = []
        for hit in await self.s.retriever.search(query, jurisdiccion=jur_filtro, k=4):
            det = self.s.cendoj.detalle(hit.roj_id) or {}
            nivel = hit.nivel if hit.nivel in ("TS", "AN", "TSJ", "AP") else "JUZGADO"
            ext = ExtractoSentencia(
                source_id=f"ROJ:{hit.roj_id}",
                titulo=f"{hit.roj_id} ({hit.tribunal}, {hit.fecha_resolucion:%d/%m/%Y})",
                texto_verbatim=(det.get("fundamentos") or "\n".join(hit.fragmentos))[:MAX_FUENTE_CHARS],
                url_oficial=det.get("url"),
                roj=hit.roj_id,
                ecli=det.get("ecli"),
                tribunal=hit.tribunal,
                nivel=cast(Literal["TS", "AN", "TSJ", "AP", "JUZGADO"], nivel),
                fecha_resolucion=hit.fecha_resolucion,
                seccion="fundamentos_mayoria",
            )
            sentencias.append(ext)
            self._emit(
                run,
                "source",
                {
                    "source_id": ext.source_id,
                    "tipo": "sentencia",
                    "titulo": ext.titulo,
                    "url": ext.url_oficial,
                    "extracto": ext.texto_verbatim[:280],
                },
            )
        clausulas: list[ClausulaConvenio] = []
        encontrados: list[dict[str, Any]] = []
        if triage.jurisdiccion_principal == Jurisdiccion.SOCIAL and triage.convenio_aplicable:
            fecha_ref = triage.fecha_hechos or self.s.today()
            encontrados = self.s.convenios.buscar_en_vigentes(query, fecha_ref, triage.convenio_aplicable, limit=4)
            if not encontrados:
                run.avisos.append(
                    "No hay texto del convenio aplicable vigente en la fecha de los hechos en la base local: "
                    "el análisis no cita cláusulas de convenio."
                )
        elif triage.jurisdiccion_principal == Jurisdiccion.SOCIAL and self.s.convenios.indexados():
            run.avisos.append(
                "No se ha identificado tu convenio colectivo (indica tu sector o convenio en la consulta): "
                "el análisis no cita cláusulas de convenio."
            )
        for ch in encontrados:
            ref = str(ch.get("boletin_ref") or "")
            url_conv = f"https://www.boe.es/buscar/doc.php?id={ref}" if ref.startswith("BOE-") else None
            cl = ClausulaConvenio(
                source_id=f"CONV:{ch['version_id']}:art{ch['articulo']}",
                titulo=f"Art. {ch['articulo']} {ch['titulo'] or ''} ({ch['denominacion']})".strip(),
                texto_verbatim=str(ch["texto"])[:MAX_FUENTE_CHARS],
                url_oficial=url_conv,
                codigo_convenio=str(ch["codigo_convenio"]),
                version_id=str(ch["version_id"]),
                articulo=str(ch["articulo"]),
                vigencia_desde=ch["vigencia_desde"],
                vigencia_hasta=ch["vigencia_hasta"],
            )
            clausulas.append(cl)
            self._emit(
                run,
                "source",
                {
                    "source_id": cl.source_id,
                    "tipo": "convenio",
                    "titulo": cl.titulo,
                    "url": cl.url_oficial,
                    "extracto": cl.texto_verbatim[:280],
                },
            )
        adjuntos = [
            FragmentoFuente(
                source_id=f"DOC:{a['adjunto_id'][:8]}",
                tipo="adjunto",
                titulo=f"Documento aportado: {a['nombre']}",
                texto_verbatim=a["texto"][:MAX_FUENTE_CHARS],
            )
            for a in c.adjuntos
            if a.get("permitido")
        ]
        for a in adjuntos:
            self._emit(
                run,
                "source",
                {"source_id": a.source_id, "tipo": "adjunto", "titulo": a.titulo, "extracto": a.texto_verbatim[:280]},
            )
        if not sentencias:
            avisos.append(
                "No hay jurisprudencia aplicable en el corpus local: la valoración se apoya solo en la ley. "
                "Se ha encolado una búsqueda para ampliar el corpus."
            )
            self.s.cendoj.enqueue(query[:500])
        if triage.competencia_local:
            avisos.append(
                "Interviene una ordenanza municipal que no está en el BOE: adjunta el PDF de la sanción "
                "o de la ordenanza para un análisis completo."
            )
        cobertura = (
            "degradada_sin_boe" if not articulos else "degradada_sin_jurisprudencia" if not sentencias else "completa"
        )
        total = sum(len(f.texto_verbatim) for f in [*articulos, *sentencias, *clausulas, *adjuntos])
        dossier = DossierIngestaSchema(
            consulta_id=run.consulta_id,
            articulos_boe=articulos,
            sentencias=sentencias,
            clausulas_convenio=clausulas,
            extractos_adjuntos=adjuntos,
            resumen_hechos=resumen[:2500],
            cobertura=cast(Any, cobertura),
            tokens_estimados=min(12000, total // 4),
            avisos=avisos,
        )
        self.s.store.save(run.consulta_id, dossier_json=dossier.model_dump(mode="json"))
        if cobertura != "completa":
            self._estado(run, Estado.INGESTA_DEGRADADA)
        return dossier

    # ---------- Fase 3 ----------
    @staticmethod
    def _dossier_texto(dossier: DossierIngestaSchema) -> str:
        partes = [f"HECHOS (seudonimizados):\n{dossier.resumen_hechos}", "FUENTES:"]
        for f in dossier.fuentes().values():
            partes.append(f"[{f.source_id}] {f.titulo}\n{f.texto_verbatim}")
        return "\n\n".join(partes)

    def _verificar_citas(self, citas: list[Cita], fuentes: dict[str, FragmentoFuente]) -> list[dict[str, Any]]:
        out = []
        for cita in citas:
            fuente = fuentes.get(cita.source_id)
            if fuente is None:
                out.append(
                    {"source_id": cita.source_id, "ok": False, "score": 0.0, "motivo": "fuente inexistente (G2)"}
                )
                continue
            chk = verify_quote(cita.verbatim_quote, fuente.texto_verbatim)
            out.append(
                {
                    "source_id": cita.source_id,
                    "ok": chk.ok,
                    "score": round(chk.score, 1),
                    "offsets": chk.offsets,
                    "motivo": chk.motivo,
                }
            )
        return out

    async def _debate(
        self, run: _Run, dossier: DossierIngestaSchema, feedback: str = "", previo: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._estado(run, Estado.DEBATE)
        base = self._dossier_texto(dossier)
        alegato_fmt = _prompt("_alegato")
        fuentes = dossier.fuentes()
        if previo is None:
            defensa = await self._llm_json(
                run,
                "defensa",
                _prompt("defensa") + "\n\n" + alegato_fmt.replace("{rol}", "DEFENSA"),
                base + "\n\nCUESTIONES LITIGIOSAS: defínelas tú (C1, C2...) incluyendo en cada argumento la cuestión "
                "que resuelve. Defiende al ciudadano.",
                AlegatoSchema,
                delta_rol="defensa",
            )
            self._emit(
                run,
                "debate_done",
                {
                    "rol": "defensa",
                    "alegato": defensa.model_dump(),
                    "verificacion": [
                        self._verificar_citas(a.citas, fuentes) for q in defensa.cuestiones for a in q.argumentos
                    ],
                },
            )
            cuestiones_txt = "\n".join(f"{q.id}: {q.argumentos[0].afirmacion[:200]}" for q in defensa.cuestiones)
            contraparte = await self._llm_json(
                run,
                "contraparte",
                _prompt("contraparte") + "\n\n" + alegato_fmt.replace("{rol}", "CONTRAPARTE"),
                base + f"\n\nCUESTIONES LITIGIOSAS (planteadas por la Defensa):\n{cuestiones_txt}\n\n"
                f"ALEGATO DE LA DEFENSA:\n{defensa.model_dump_json()}",
                AlegatoSchema,
                delta_rol="contraparte",
            )
            self._emit(
                run,
                "debate_done",
                {
                    "rol": "contraparte",
                    "alegato": contraparte.model_dump(),
                    "verificacion": [
                        self._verificar_citas(a.citas, fuentes) for q in contraparte.cuestiones for a in q.argumentos
                    ],
                },
            )
        else:
            defensa = AlegatoSchema.model_validate(previo["defensa"])
            contraparte = AlegatoSchema.model_validate(previo["contraparte"])
        prompt = (
            base + f"\n\nALEGATO DE LA DEFENSA:\n{defensa.model_dump_json()}\n\n"
            f"ALEGATO DE LA CONTRAPARTE:\n{contraparte.model_dump_json()}"
        )
        if feedback:
            prompt += f"\n\nCORRECCIONES OBLIGATORIAS (verificación automática de tu resolución anterior):\n{feedback}"
        magistrado = await self._llm_json(
            run, "magistrado", _prompt("magistrado"), prompt, ResolucionMagistradoSchema, delta_rol="magistrado"
        )
        self._emit(run, "debate_done", {"rol": "magistrado", "resolucion": magistrado.model_dump()})
        debate = {
            "defensa": defensa.model_dump(),
            "contraparte": contraparte.model_dump(),
            "magistrado": magistrado.model_dump(),
        }
        self.s.store.save(run.consulta_id, debate_json=debate)
        return debate

    # ---------- Fase 4 ----------
    def _fallos_magistrado(self, res: ResolucionMagistradoSchema, fuentes: dict[str, FragmentoFuente]) -> list[str]:
        fallos = []
        for q in res.cuestiones:
            citas = [c for a in q.fundamentos for c in a.citas] + (
                [q.fundamento_cuantia] if q.fundamento_cuantia else []
            )
            for cita, v in zip(citas, self._verificar_citas(citas, fuentes), strict=True):
                if not v["ok"]:
                    fallos.append(
                        f"{q.id}: cita a {cita.source_id} no verificada ({v['motivo']}): «{cita.verbatim_quote[:120]}»"
                    )
            if q.tipo == "cuantia" and q.importe_estimado_eur is not None and q.fundamento_cuantia is None:
                fallos.append(f"{q.id}: importe sin fundamento_cuantia")
        textos = [
            res.resumen_ciudadano,
            res.razonamiento_banda,
            *res.fortalezas,
            *res.riesgos_propios,
            *res.pasos_inmediatos,
            *[a.afirmacion for q in res.cuestiones for a in q.fundamentos],
        ]
        for t in textos:
            for p in find_pronosticos(t):
                fallos.append(f"pronóstico porcentual prohibido: «{p}»")
        return fallos

    def _plazos(self, triage: TriageOutputSchema) -> tuple[list[PlazoCalculado], list[str]]:
        plazos, avisos = [], []
        ccaa = self.s.calendar.festivos.ccaa_de(triage.municipio_ine_organo)
        foral = "CT" if triage.vecindad_civil == "catalana" or ccaa == "CT" else None
        for alerta in triage.alertas_plazo:
            if alerta.fecha_inicio_computo is None:
                avisos.append(f"No se ha podido calcular el plazo {alerta.tipo_plazo_id}: falta la fecha de inicio.")
                continue
            try:
                plazos.append(
                    self.s.calendar.compute(
                        alerta.tipo_plazo_id,
                        alerta.fecha_inicio_computo,
                        municipio_ine=triage.municipio_ine_organo,
                        territorio_foral=foral,
                        hoy=self.s.today(),
                    )
                )
            except PlazoError as exc:
                avisos.append(f"Plazo {alerta.tipo_plazo_id}: {exc}")
        return plazos, avisos

    async def _guardarrailes(
        self, run: _Run, triage: TriageOutputSchema, dossier: DossierIngestaSchema, debate: dict[str, Any]
    ) -> None:
        self._estado(run, Estado.GUARDARRAILES)
        fuentes = dossier.fuentes()
        res = ResolucionMagistradoSchema.model_validate(debate["magistrado"])
        fallos = self._fallos_magistrado(res, fuentes)
        self._emit(run, "guardrail", {"id": "G2-G4", "ok": not fallos, "detalle": fallos[:10]})
        if fallos:  # 1 reintento del Magistrado con el informe de errores (§2.3)
            debate = await self._debate(run, dossier, feedback="\n".join(fallos[:20]), previo=debate)
            self._estado(run, Estado.GUARDARRAILES)
            res = ResolucionMagistradoSchema.model_validate(debate["magistrado"])
            fallos = self._fallos_magistrado(res, fuentes)
            self._emit(run, "guardrail", {"id": "G2-G4 (reintento)", "ok": not fallos, "detalle": fallos[:10]})

        # Construcción de fundamentos verificados (las citas que sigan fallando se descartan con aviso)
        fundamentos: list[Fundamento] = []
        pares: list[tuple[str, str]] = []
        ref: list[tuple[str, str, str, float, tuple[int, int], str]] = []
        descartadas = 0
        for q in res.cuestiones:
            for arg in q.fundamentos:
                for cita, v in zip(arg.citas, self._verificar_citas(arg.citas, fuentes), strict=True):
                    if not v["ok"] or v.get("offsets") is None:
                        descartadas += 1
                        continue
                    pares.append((cita.verbatim_quote, arg.afirmacion))
                    ref.append(
                        (
                            arg.afirmacion,
                            cita.source_id,
                            cita.verbatim_quote,
                            v["score"],
                            tuple(v["offsets"]),
                            q.estimacion,
                        )
                    )
        if descartadas:
            run.avisos.append(f"Se han descartado {descartadas} cita(s) que no coinciden literalmente con la fuente.")
        pronosticos = [p for t in [res.resumen_ciudadano] for p in find_pronosticos(t)]
        resumen = res.resumen_ciudadano
        for p in pronosticos:
            resumen = resumen.replace(p, "[pronóstico eliminado]")

        nli_neutral = nli_contra = 0
        if pares:
            try:
                resultados = await NLIChecker(self.s.router, run.modo).check(pares[:12], consulta_id=run.consulta_id)
            except (ProviderError, ValueError) as exc:
                resultados = []
                run.avisos.append(f"Validación NLI no disponible ({exc}); se rebaja la banda por prudencia.")
                nli_neutral += 1
            for i, (afirm, sid, quote, score, offs, _est) in enumerate(ref):
                label = resultados[i].label if i < len(resultados) else "NEUTRAL"
                if label == "CONTRADICTS":
                    nli_contra += 1
                    run.avisos.append(f"Descartado un fundamento que contradice {sid} (NLI).")
                    continue
                nli_neutral += label == "NEUTRAL"
                fundamentos.append(
                    Fundamento(
                        texto=afirm, source_id=sid, verbatim_quote=quote, fuzzy_score=score, nli=label, offsets=offs
                    )
                )
        self._emit(
            run,
            "guardrail",
            {
                "id": "G5",
                "ok": nli_contra == 0,
                "detalle": [
                    f"{nli_neutral} inferencia(s) no literal(es)",
                    f"{nli_contra} contradicción(es) descartada(s)",
                ],
            },
        )

        sub = submaterias().get(triage.submateria_principal)
        roj_favor = {sid for (_, sid, _, _, _, est) in ref if sid.startswith("ROJ:") and est == "DEFENSA"}
        roj_contra = {sid for (_, sid, _, _, _, est) in ref if sid.startswith("ROJ:") and est == "CONTRAPARTE"}
        niveles = {f.source_id: getattr(f, "nivel", None) for f in dossier.sentencias}
        ev = EvidenciaBanda(
            citas_boe_verificadas=sum(1 for f in fundamentos if f.source_id.startswith("BOE:")),
            sentencias_favorables_ts=sum(1 for s in roj_favor if niveles.get(s) == "TS"),
            sentencias_favorables_ap=sum(1 for s in roj_favor if niveles.get(s) in ("AP", "TSJ", "AN")),
            sentencias_desfavorables=len(roj_contra),
            nli_neutral=nli_neutral,
            nli_contradice=0,
            doctrina_cambiante=bool(sub and sub.doctrina_cambiante),
            cobertura_degradada=dossier.cobertura != "completa",
            hechos_sin_prueba=bool(triage.datos_criticos_faltantes),
        )
        banda, motivos = coherent_band(res.banda_propuesta, ev)
        if fallos:
            # Las citas fallidas ya se han descartado; solo se rebaja la "doctrina consolidada".
            if banda == BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE:
                banda = BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA
            motivos.append("Persistían citas no verificadas tras el reintento: se han descartado.")
        self._emit(
            run,
            "guardrail",
            {
                "id": "G6",
                "ok": banda == res.banda_propuesta,
                "detalle": motivos,
                "banda_propuesta": res.banda_propuesta,
                "banda_final": banda,
            },
        )

        plazos, avisos_plazos = self._plazos(triage)
        self._emit(run, "deadline", {"plazos": [p.model_dump(mode="json") for p in plazos], "avisos": avisos_plazos})
        sub_proc = sub.procedimiento if sub else None
        postulacion = evaluar(
            CasoPostulacion(
                jurisdiccion=triage.jurisdiccion_principal.value,
                procedimiento=sub_proc,
                fase="instancia",
                cuantia_eur=triage.cuantia_estimada_eur,
            )
        )
        self._emit(
            run,
            "guardrail",
            {
                "id": "G9",
                "ok": True,
                "detalle": [postulacion.texto_usuario],
                "bloquea_escritos": postulacion.bloquea_escritos,
            },
        )

        avisos = list(dict.fromkeys([*run.avisos, *dossier.avisos, *avisos_plazos, *motivos]))
        if not fundamentos:
            self._estado(run, Estado.BLOQUEADA)
            payload = {
                "estado": "BLOQUEADA",
                "mensaje": (
                    "No se ha podido emitir un dictamen verificable: ninguna afirmación pudo contrastarse literalmente "
                    "con la ley o la jurisprudencia. Te mostramos los plazos y la información de postulación, que se "
                    "calculan de forma independiente."
                ),
                "plazos": [p.model_dump(mode="json") for p in plazos],
                "postulacion": postulacion.model_dump(),
                "avisos": avisos,
                "aviso_legal": AVISO_LEGAL,
            }
            self.s.store.save(run.consulta_id, dictamen_json=payload, banda_solidez=BandaSolidez.NO_DETERMINABLE.value)
            self._emit(run, "final", payload)
            return
        dictamen = DictamenCertificadoSchema(
            consulta_id=run.consulta_id,
            modo=cast(Any, run.modo),
            modelos_usados=run.modelos,
            banda_solidez=banda,
            resumen_ciudadano=resumen,
            fundamentos=fundamentos,
            cuestiones=res.cuestiones,
            fortalezas=res.fortalezas,
            debilidades_contraparte=res.debilidades_contraparte,
            riesgos_propios=res.riesgos_propios,
            pasos_inmediatos=res.pasos_inmediatos[:8],
            plazos=plazos,
            postulacion=postulacion,
            avisos=avisos,
            guardarrailes={
                "G1_schema": True,
                "G2_G3_citas": not fallos,
                "G4_sin_pronosticos": True,
                "G5_nli": nli_contra == 0,
                "G6_banda": True,
                "G8_plazos": True,
                "G9_postulacion": True,
            },
            aviso_legal=AVISO_LEGAL,
            generado_en=datetime.now(UTC),
        )
        payload = {
            "estado": "CERTIFICADA",
            "dictamen": dictamen.model_dump(mode="json"),
            "banda_texto": BANDA_TEXTO[banda],
        }
        self.s.store.save(
            run.consulta_id,
            dictamen_json=payload,
            dictamen_markdown=render_markdown(dictamen),
            banda_solidez=banda.value,
            fuzzy_min_score=min(f.fuzzy_score for f in fundamentos),
            guardrails_json=dictamen.guardarrailes,
        )
        self._estado(run, Estado.CERTIFICADA)
        self._emit(run, "final", payload)

    # ---------- punto de entrada ----------
    async def run(self, consulta_id: str) -> None:
        c = self.s.store.get(consulta_id)
        run = _Run(consulta_id=consulta_id, modo=c.modo)
        try:
            triage = await self._triaje(run)
            if triage is None:
                return
            resumen = (self.s.store.get(consulta_id).triage or {}).get("resumen_hechos") or c.texto_seudonimizado
            dossier = await self._ingesta(run, triage, resumen)
            debate = await self._debate(run, dossier)
            await self._guardarrailes(run, triage, dossier, debate)
        except Exception as exc:  # noqa: BLE001 — cualquier fallo se comunica a la UI
            log.exception("consulta %s fallida", consulta_id)
            try:
                self.s.store.set_estado(consulta_id, Estado.ERROR, error=str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
            self._emit(run, "error", {"mensaje": str(exc)[:500], "tipo": type(exc).__name__})


def render_markdown(d: DictamenCertificadoSchema) -> str:
    lines = [f"# Dictamen Iuris-IA — {BANDA_TEXTO[d.banda_solidez]}", "", d.resumen_ciudadano, ""]
    if d.plazos:
        lines += [
            "## Plazos",
            *[f"- **{p.descripcion}**: hasta el {p.fecha_limite_segura:%d/%m/%Y} ({p.base_legal})" for p in d.plazos],
            "",
        ]
    lines += [
        "## Fundamentos verificados",
        *[f"- {f.texto}\n  > «{f.verbatim_quote}» — `{f.source_id}`" for f in d.fundamentos],
        "",
    ]
    if d.pasos_inmediatos:
        lines += ["## Pasos inmediatos", *[f"1. {p}" for p in d.pasos_inmediatos], ""]
    if d.postulacion:
        lines += ["## ¿Necesitas abogado?", d.postulacion.texto_usuario, ""]
    if d.avisos:
        lines += ["## Avisos", *[f"- {a}" for a in d.avisos], ""]
    lines += ["---", d.aviso_legal]
    return "\n".join(lines)
