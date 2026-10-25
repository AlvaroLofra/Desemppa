"""Orquestador del pipeline de 4 fases (dossier §2.2–2.4): triaje, ingesta, juicio contradictorio y
guardarraíles. Emite eventos SSE por el EventBus; nunca deja que el LLM calcule fechas ni elija normas."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from pydantic import BaseModel, ValidationError

from connectors.boe_client import BOEError, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.eurlex_client import EURLexError, EURLexRepository
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine, PlazoError
from core.errors import ProviderError
from core.fechas_es import fecha_consta, fechas_en_texto, mes_consta
from core.firewall import Contexto, ResultadoFirewall, Seccion, escanear, verificar_afirmaciones
from core.llm_types import LLMRequest, LLMResult
from core.materias import Submateria, catalogo_para_prompt, id_norma, normas_aplicables, submaterias
from core.nli import NLIChecker, extract_json
from core.normalize import fold
from core.postulacion_rules import CasoPostulacion, evaluar
from core.router import ModelRouter
from core.schemas import (
    AVISO_LEGAL,
    BANDA_TEXTO,
    AfirmacionVerificada,
    AlegatoSchema,
    AlertaPlazo,
    ArticuloBOE,
    ArticuloUE,
    BandaSolidez,
    Cita,
    CitaVerificada,
    ClausulaConvenio,
    DictamenCertificadoSchema,
    DossierIngestaSchema,
    EntradaAuditoria,
    ExtractoSentencia,
    FragmentoFuente,
    FuenteSellada,
    Fundamento,
    Jurisdiccion,
    NormaObjetivo,
    PlazoCalculado,
    PreguntaAclaratoria,
    RamaCandidata,
    ResolucionMagistradoSchema,
    SelloVerificacion,
    TriageOutputSchema,
)
from core.state import ConsultaStore, Estado, EventBus
from core.temporal_sync import select_version
from core.validators import EvidenciaBanda, coherent_band, find_pronosticos, lower_band, verify_quote

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parent / "prompts"
MAX_FUENTE_CHARS = 6000
M = TypeVar("M", bound=BaseModel)


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _prompt_rol(name: str) -> str:
    """Prompt de un rol del debate con las reglas comunes anti-invención delante (core/prompts/_reglas.md)."""
    return _prompt("_reglas") + "\n\n" + _prompt(name)


_fold = fold

_MOTIVOS = {
    "EmptyResponse": "respuesta vacía",
    "RateLimited": "límite de peticiones",
    "UsageLimitReached": "cuota agotada",
    "ProviderTimeout": "tiempo agotado",
    "ModelUnavailable": "no disponible",
    "NotAuthenticated": "sin sesión iniciada",
}


def _motivo_sustitucion(avisos: list[str]) -> str:
    """Motivo legible del primer fallo que llevó al router a otro modelo (avisos de core/router.py)."""
    for aviso in avisos:
        m = re.search(r"\((\w+)\)", aviso)
        if m:
            return _MOTIVOS.get(m.group(1), m.group(1))
        if "circuit breaker" in aviso:
            return "pausado tras varios fallos"
        if "desactivado" in aviso:
            return "proveedor desactivado"
    return "no disponible"


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
    # Campos críticos de la submateria que constan en la consulta, con la frase literal que lo prueba.
    campos_constan: list[dict[str, Any]] = []


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
    eurlex: EURLexRepository | None = None  # Derecho de la UE (opcional)


@dataclass
class _Run:
    consulta_id: str
    modo: str
    modelos: dict[str, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    discrepancias: list[str] = field(default_factory=list)  # cuestiones en que dos resoluciones no coinciden


class Orchestrator:
    def __init__(self, services: Services) -> None:
        self.s = services

    # ---------- utilidades ----------
    def _emit(self, run: _Run, tipo: str, data: dict[str, Any]) -> None:
        self.s.bus.emit(run.consulta_id, tipo, data)

    def _estado(self, run: _Run, estado: Estado) -> None:
        self.s.store.set_estado(run.consulta_id, estado)
        self._emit(run, "phase", {"estado": estado.value})

    def _modelo_previsto(self, modo: str, role: str) -> str:
        a = self.s.router.resolve(modo, role)
        return self.s.router.catalog.models[a.model].resolved_id(a.effort)

    async def _llm_json(
        self,
        run: _Run,
        role: str,
        system: str,
        prompt: str,
        model: type[M],
        *,
        delta_rol: str | None = None,
        modelo: str | None = None,
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
                restartable=True,
                modelo=modelo,  # solo se usa el JSON final: un corte a mitad puede repetirse en otro modelo
            ):
                if isinstance(item, LLMResult):
                    text = item.text
                    run.modelos[role] = item.model
                    if item.degradado:
                        # Lo resolvió otro modelo: se dice cuál, en lugar de cuál y por qué (progreso y dictamen).
                        previsto = self._modelo_previsto(run.modo, role)
                        motivo = _motivo_sustitucion(item.avisos)
                        run.modelos[role] = f"{item.model} (en lugar de {previsto}: {motivo})"
                        run.avisos.extend(item.avisos)
                        self._emit(
                            run,
                            "quota",
                            {
                                "rol": role,
                                "avisos": item.avisos,
                                "modelo": item.model,
                                "previsto": previsto,
                                "motivo": motivo,
                            },
                        )
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
        hechos_txt = c.texto_seudonimizado + "\n" + "\n".join(str(a.get("respuesta", "")) for a in c.aclaraciones)
        # Lo que ya se sabe (selector de municipio, fechas escritas) va al prompt para que no se vuelva a preguntar.
        conocidos = []
        if c.municipio_ine and (m := self.s.calendar.festivos.municipios.get(c.municipio_ine)):
            conocidos.append(f"- Municipio del juzgado u organismo, elegido por el usuario: {m.nombre}")
        fechas_dichas = sorted(fechas_en_texto(hechos_txt, hoy).exactas)
        if fechas_dichas:
            conocidos.append("- Fechas que constan en la consulta: " + ", ".join(f.isoformat() for f in fechas_dichas))
        system = (
            _prompt("triaje")
            .replace("{hoy}", hoy.isoformat())
            .replace("{catalogo}", catalogo_para_prompt())
            .replace("{convenios}", lista_convenios or "(ninguno indexado: usa null)")
            .replace("{conocidos}", "\n".join(conocidos) or "(ninguno)")
        )
        raw = await self._llm_json(run, "triaje", system, f"CONSULTA DEL CIUDADANO:\n{texto}", TriageLLM)
        # Las fechas solo valen si el ciudadano las ha escrito (o «hoy», «ayer», «hace N días»): el modelo no puede
        # deducirlas ni calcularlas. Una fecha inventada movería el plazo (benchmark 24-10-2026, caso de Barcelona).
        fecha_inicio = raw.fecha_inicio_plazo
        if fecha_inicio and not fecha_consta(fecha_inicio, hechos_txt, hoy):
            run.avisos.append(
                f"El modelo propuso el {fecha_inicio:%d/%m/%Y} como inicio del plazo, pero esa fecha no consta en tu "
                "consulta: no se ha usado."
            )
            fecha_inicio = None
        fecha_hechos = raw.fecha_hechos
        if fecha_hechos and not mes_consta(fecha_hechos, hechos_txt, hoy):
            fecha_hechos = None
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
        candidatas_modelo = [
            PreguntaAclaratoria.model_validate({"tipo_respuesta": "texto", **p})
            for p in raw.preguntas_aclaracion
            if p.get("texto")
        ]
        # El modelo a veces pregunta lo que ya se sabe (o el municipio como texto libre): se filtra por código.
        # Las preguntas de municipio se quitan siempre; si falta, se hace solo la canónica `q_municipio`.
        conocido = {
            "municipio": municipio_ine is not None,
            "fecha": fecha_inicio is not None,
            "importe": _importe_consta(raw.cuantia_estimada_eur, hechos_txt),
        }
        pide_municipio = any(_dato_preguntado(p.texto, p.tipo_respuesta) == "municipio" for p in candidatas_modelo)
        preguntas_modelo = [
            p
            for p in candidatas_modelo
            if (dato := _dato_preguntado(p.texto, p.tipo_respuesta)) != "municipio" and not conocido.get(dato or "")
        ][:4]
        faltan = [f for f in raw.datos_criticos_faltantes if not conocido.get(_dato_preguntado(f) or "")]
        esenciales: list[PreguntaAclaratoria] = []
        if sub and sub.plazos and fecha_inicio is None:
            evento = _campo_fecha(sub)
            if not any(p.tipo_respuesta == "fecha" for p in preguntas_modelo):
                esenciales.append(
                    PreguntaAclaratoria(
                        id="q_fecha",
                        texto=f"Indica la fecha exacta (día, mes y año): {evento}",
                        tipo_respuesta="fecha",
                        motivo="cálculo de plazos",
                    )
                )
        if municipio_ine is None and (pide_municipio or (sub and not sub.fuera_alcance)):
            esenciales.append(
                PreguntaAclaratoria(
                    id="q_municipio",
                    texto="¿En qué municipio está el juzgado o el organismo (o, si no lo sabes, tu municipio)?",
                    tipo_respuesta="municipio",
                    motivo="festivos locales del calendario",
                )
            )
        # Campos críticos de la submateria (catálogo): cuentan como conocidos solo si el modelo aporta una frase
        # LITERAL de la consulta que los contiene. Los que falten se preguntan siempre («más vale preguntar»).
        criticos = (
            _preguntas_campos_criticos(sub, raw.campos_constan, hechos_txt, conocido, esenciales + preguntas_modelo)
            if sub
            else []
        )
        preguntas = (esenciales + criticos + preguntas_modelo)[:5]
        if raw.grado_ambiguedad >= 0.35 and not preguntas:
            preguntas.append(
                PreguntaAclaratoria(
                    id="q_amb",
                    texto="¿Puedes dar más detalles de lo ocurrido?",
                    tipo_respuesta="texto",
                    motivo="ambigüedad",
                )
            )
        # Derecho civil catalán: por vecindad civil declarada o por estar el juzgado en Cataluña (mismo criterio
        # que el cálculo de plazos).
        foral = (
            "CT"
            if raw.vecindad_civil == "catalana" or self.s.calendar.festivos.ccaa_de(municipio_ine) == "CT"
            else None
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
            fecha_hechos=fecha_hechos or fecha_inicio,
            municipio_ine_organo=municipio_ine,
            vecindad_civil=cast(Any, raw.vecindad_civil)
            if raw.vecindad_civil in ("comun", "catalana", "aragonesa", "navarra", "vasca", "gallega", "balear")
            else "desconocida",
            cuantia_estimada_eur=raw.cuantia_estimada_eur,
            alertas_plazo=[
                AlertaPlazo(
                    tipo_plazo_id=p,
                    fecha_inicio_computo=fecha_inicio,
                    evento_inicio=_campo_fecha(sub) if sub else "",
                )
                for p in (sub.plazos if sub else [])
            ],
            normas_boe_objetivo=[
                NormaObjetivo(id_norma=id_norma(n.norma), articulos=n.articulos, motivo=n.norma)
                for n in (normas_aplicables(sub, foral) if sub else [])
            ]
            # Toda demanda civil exige antes intentar negociar (arts. 5 y 10 LO 1/2025): el debate debe tener el
            # texto delante para no contradecir el aviso de postulación (benchmark, caso de la comisión bancaria).
            + (
                [NormaObjetivo(id_norma=id_norma("LOEFICIENCIA"), articulos=["5", "10"], motivo="LOEFICIENCIA")]
                if jur == Jurisdiccion.CIVIL and sub and not sub.fuera_alcance
                else []
            ),
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

    def _magistrado_doble(self, run: _Run) -> bool:
        catalogo = getattr(self.s.router, "catalog", None)
        perfil = getattr(catalogo, "profiles", {}).get(run.modo)
        return bool(getattr(perfil, "magistrado_doble", False))

    def _pedir_hechos_determinantes(self, run: _Run, debate: dict[str, Any]) -> bool:
        """Segunda ronda: si el Magistrado señala hechos no contados que cambiarían una estimación, se preguntan
        antes de dar el resultado (máximo dos rondas de aclaración por consulta). Devuelve True si se ha pausado."""
        c = self.s.store.get(run.consulta_id)
        if c.rondas >= 2:
            return False
        res = ResolucionMagistradoSchema.model_validate(debate["magistrado"])
        ya = {_fold(a.get("pregunta", "")) for a in c.aclaraciones}
        preguntas = [
            PreguntaAclaratoria(
                id=f"q_det_{i}",
                texto=h.pregunta,
                tipo_respuesta=h.tipo_respuesta,
                opciones=h.opciones,
                motivo=h.por_que or "puede cambiar el resultado",
            )
            for i, h in enumerate(res.hechos_determinantes[:4])
            if h.pregunta.strip() and _fold(h.pregunta) not in ya
        ]
        if not preguntas:
            return False
        self._estado(run, Estado.ESPERANDO_ACLARACION)
        self._emit(run, "clarification_needed", {"preguntas": [p.model_dump() for p in preguntas], "ronda": 2})
        return True

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
        articulos_ue: list[ArticuloUE] = []
        sub_ingesta = submaterias().get(triage.submateria_principal)
        for norma_ue in sub_ingesta.normas_ue if sub_ingesta else []:
            if self.s.eurlex is None:
                avisos.append(f"{norma_ue.titulo}: el conector de Derecho de la UE no está disponible.")
                break
            for art in norma_ue.articulos:
                try:
                    ue = await self.s.eurlex.get_articulo(norma_ue.celex, art)
                except EURLexError as exc:
                    avisos.append(f"No se pudo obtener el art. {art} de {norma_ue.titulo} de EUR-Lex: {exc}")
                    continue
                fuente_ue = ArticuloUE(
                    source_id=f"EUR:{ue.celex}:art{ue.articulo}",
                    titulo=f"Art. {ue.articulo} {norma_ue.titulo} ({ue.titulo})",
                    texto_verbatim=ue.texto[:MAX_FUENTE_CHARS],
                    url_oficial=ue.url,
                    celex=ue.celex,
                    articulo=ue.articulo,
                )
                articulos_ue.append(fuente_ue)
                self._emit(
                    run,
                    "source",
                    {
                        "source_id": fuente_ue.source_id,
                        "tipo": "ue",
                        "titulo": fuente_ue.titulo,
                        "url": fuente_ue.url_oficial,
                        "extracto": fuente_ue.texto_verbatim[:280],
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
            # Solo los términos jurídicos del triaje: el resumen de hechos («camarero», «Madrid»…) desplaza en BM25 a
            # los artículos pertinentes (faltas, sanciones) en favor de los de clasificación profesional.
            q_conv = " ".join(triage.terminos_cendoj) or query
            encontrados = self.s.convenios.buscar_en_vigentes(q_conv, fecha_ref, triage.convenio_aplicable, limit=4)
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
            "degradada_sin_boe"
            if not (articulos or articulos_ue)
            else "degradada_sin_jurisprudencia"
            if not sentencias
            else "completa"
        )
        total = sum(len(f.texto_verbatim) for f in [*articulos, *articulos_ue, *sentencias, *clausulas, *adjuntos])
        dossier = DossierIngestaSchema(
            consulta_id=run.consulta_id,
            articulos_boe=articulos,
            articulos_ue=articulos_ue,
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
        self,
        run: _Run,
        dossier: DossierIngestaSchema,
        feedback: str = "",
        previo: dict[str, Any] | None = None,
        modelo_magistrado: str | None = None,
    ) -> dict[str, Any]:
        self._estado(run, Estado.DEBATE)
        c = self.s.store.get(run.consulta_id)
        pregunta = c.texto_seudonimizado + "".join(
            f"\n- {a.get('pregunta', '')}: {a.get('respuesta', '')}" for a in c.aclaraciones
        )
        base = f"CONSULTA LITERAL DEL CIUDADANO (seudonimizada):\n{pregunta}\n\n" + self._dossier_texto(dossier)
        alegato_fmt = _prompt("_alegato")
        fuentes = dossier.fuentes()
        if previo is None:
            defensa = await self._llm_json(
                run,
                "defensa",
                _prompt_rol("defensa") + "\n\n" + alegato_fmt.replace("{rol}", "DEFENSA"),
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
                _prompt_rol("contraparte") + "\n\n" + alegato_fmt.replace("{rol}", "CONTRAPARTE"),
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
        llamada = self._llm_json(
            run,
            "magistrado",
            _prompt_rol("magistrado"),
            prompt,
            ResolucionMagistradoSchema,
            delta_rol="magistrado",
            modelo=modelo_magistrado,
        )
        if self._magistrado_doble(run) and not feedback:
            # Dos resoluciones independientes en paralelo; la segunda solo sirve para medir la estabilidad.
            magistrado, segunda = await asyncio.gather(
                llamada,
                self._llm_json(run, "magistrado", _prompt_rol("magistrado"), prompt, ResolucionMagistradoSchema),
                return_exceptions=False,
            )
            otra = {q.id: q.estimacion for q in segunda.cuestiones}
            run.discrepancias = [q.id for q in magistrado.cuestiones if q.id in otra and otra[q.id] != q.estimacion]
        else:
            magistrado = await llamada
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
        textos = [
            res.razonamiento_banda,
            *[a.texto for a in res.respuesta_directa + res.resumen_ciudadano],
            *[a.texto for a in res.fortalezas + res.riesgos_propios + res.pasos_inmediatos],
            *[a.afirmacion for q in res.cuestiones for a in q.fundamentos],
        ]
        for t in textos:
            for p in find_pronosticos(t):
                fallos.append(f"pronóstico porcentual prohibido: «{p}»")
        return fallos

    async def _cortafuegos(self, run: _Run, res: ResolucionMagistradoSchema, ctx: Contexto) -> ResultadoFirewall:
        """Cada afirmación para el ciudadano pasa por el cortafuegos (core/firewall.py): citas literales, NLI,
        hechos y escáner de referencias. Si la respuesta directa se queda vacía, eso también es un fallo."""
        secciones: list[tuple[Seccion, Any]] = [
            *(("respuesta", a) for a in res.respuesta_directa),
            *(("resumen", a) for a in res.resumen_ciudadano),
            *(("fortaleza", a) for a in res.fortalezas),
            *(("riesgo", a) for a in res.riesgos_propios),
            *(("paso", a) for a in res.pasos_inmediatos),
        ]
        return await verificar_afirmaciones(secciones, ctx, self.s.router, run.modo, consulta_id=run.consulta_id)

    @staticmethod
    def _fallos_cortafuegos(fw: ResultadoFirewall) -> list[str]:
        fallos = fw.fallos()
        if not fw.aceptadas("respuesta"):
            fallos.append(
                "respuesta_directa: ninguna afirmación verificada. Contesta lo que pregunta el ciudadano con "
                "afirmaciones tipadas y, si son jurídicas, con citas literales del dossier."
            )
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
        c = self.s.store.get(run.consulta_id)
        hechos_txt = c.texto_seudonimizado + "".join(f"\n{a.get('respuesta', '')}" for a in c.aclaraciones)
        # Los plazos se calculan antes: sus fechas y cifras son las únicas que el texto puede añadir.
        plazos, avisos_plazos = self._plazos(triage)
        sub = submaterias().get(triage.submateria_principal)
        postulacion = evaluar(
            CasoPostulacion(
                jurisdiccion=triage.jurisdiccion_principal.value,
                procedimiento=sub.procedimiento if sub else None,
                fase="instancia",
                cuantia_eur=triage.cuantia_estimada_eur,
            )
        )
        reglas = self.s.calendar.rules
        ctx = Contexto(
            fuentes=fuentes,
            hechos=hechos_txt,
            hoy=self.s.today(),
            plazos=plazos,
            numeros_plazos={float(reglas[p.tipo_plazo_id].duracion) for p in plazos if p.tipo_plazo_id in reglas},
            referencias_extra=[p.base_legal for p in plazos] + [postulacion.base_legal, postulacion.texto_usuario],
        )
        fw = await self._cortafuegos(run, res, ctx)
        fallos = self._fallos_magistrado(res, fuentes) + self._fallos_cortafuegos(fw)
        self._emit(run, "guardrail", {"id": "G2-G4", "ok": not fallos, "detalle": fallos[:10]})
        if fallos:  # 1 reintento del Magistrado con el informe de errores (§2.3)
            try:
                debate = await self._debate(run, dossier, feedback="\n".join(fallos[:20]), previo=debate)
            except ProviderError as exc:
                # Ya hay una resolución válida: se sigue con ella (lo no verificado se descarta más abajo)
                # en lugar de perder la consulta porque el reintento no llega a tiempo.
                run.avisos.append(f"No se pudo repetir la resolución para corregirla ({type(exc).__name__}).")
            else:
                res = ResolucionMagistradoSchema.model_validate(debate["magistrado"])
                fw = await self._cortafuegos(run, res, ctx)
                fallos = self._fallos_magistrado(res, fuentes) + self._fallos_cortafuegos(fw)
            resolver = getattr(self.s.router, "resolve", None)  # los routers simulados de los tests no lo tienen
            escalado = _ESCALADO.get(resolver(run.modo, "magistrado").model) if resolver else None
            if fallos and escalado and escalado in self.s.router.catalog.models:
                # Escalado: si el modelo rápido falla dos veces la verificación, se repite una vez con el más
                # capaz de la MISMA familia (no gasta cuota de la otra suscripción) y se avisa.
                try:
                    debate = await self._debate(
                        run, dossier, feedback="\n".join(fallos[:20]), previo=debate, modelo_magistrado=escalado
                    )
                except ProviderError as exc:
                    run.avisos.append(
                        f"No se pudo repetir la resolución con un modelo más capaz ({type(exc).__name__})."
                    )
                else:
                    run.avisos.append(
                        f"La resolución no superaba la verificación y se ha repetido con {escalado} (misma familia)."
                    )
                    res = ResolucionMagistradoSchema.model_validate(debate["magistrado"])
                    fw = await self._cortafuegos(run, res, ctx)
                    fallos = self._fallos_magistrado(res, fuentes) + self._fallos_cortafuegos(fw)
            self._estado(run, Estado.GUARDARRAILES)
            self._emit(run, "guardrail", {"id": "G2-G4 (reintento)", "ok": not fallos, "detalle": fallos[:10]})
        run.avisos.extend(fw.avisos)
        eliminadas = [v for v in fw.veredictos if v.tipo_final is None]
        if eliminadas:
            run.avisos.append(
                f"El cortafuegos ha eliminado {len(eliminadas)} afirmación(es) sin respaldo verificable "
                "(detalle en «Cómo se ha verificado»)."
            )

        # Construcción de fundamentos verificados (las citas que sigan fallando se descartan con aviso)
        fundamentos: list[Fundamento] = []
        pares: list[tuple[str, str]] = []
        ref: list[tuple[str, str, str, float, tuple[int, int], str]] = []
        descartadas = 0
        auditoria_fund: list[EntradaAuditoria] = []
        vistos: set[tuple[str, str]] = set()
        for q in res.cuestiones:
            for arg in q.fundamentos:
                for cita, v in zip(arg.citas, self._verificar_citas(arg.citas, fuentes), strict=True):
                    if not v["ok"] or v.get("offsets") is None:
                        descartadas += 1
                        continue
                    # La misma cita (o la misma afirmación con la misma fuente) no se repite en el dictamen.
                    clave_cita = (cita.source_id, " ".join(cita.verbatim_quote.lower().split()))
                    clave_afirm = (cita.source_id, " ".join(arg.afirmacion.lower().split()))
                    if clave_cita in vistos or clave_afirm in vistos:
                        continue
                    vistos.update({clave_cita, clave_afirm})
                    hallazgos = escanear(arg.afirmacion, ctx, citas=[cita.source_id])
                    if hallazgos:  # el fundamento menciona normas, cifras o fechas sin respaldo
                        descartadas += 1
                        auditoria_fund.append(
                            EntradaAuditoria(
                                seccion="fundamento",
                                texto=arg.afirmacion,
                                tipo_propuesto="norma",
                                resultado="eliminada",
                                motivos=[f"{h.motivo}: «{h.fragmento}»" for h in hallazgos],
                            )
                        )
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
        # El texto para el ciudadano se compone SOLO con afirmaciones que han superado el cortafuegos.
        respuesta_directa = " ".join(v.texto for v in fw.aceptadas("respuesta"))
        resumen = " ".join(v.texto for v in fw.aceptadas("resumen"))
        respuesta_parcial = not respuesta_directa
        if respuesta_parcial:
            respuesta_directa = (
                "No puedo contestar a tu pregunta con seguridad con las fuentes disponibles: abajo tienes solo lo que "
                "sí se ha podido verificar."
            )
        for t in (resumen, respuesta_directa):
            for p in find_pronosticos(t):
                resumen = resumen.replace(p, "[pronóstico eliminado]")
                respuesta_directa = respuesta_directa.replace(p, "[pronóstico eliminado]")

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

        roj_favor = {sid for (_, sid, _, _, _, est) in ref if sid.startswith("ROJ:") and est == "DEFENSA"}
        roj_contra = {sid for (_, sid, _, _, _, est) in ref if sid.startswith("ROJ:") and est == "CONTRAPARTE"}
        niveles = {f.source_id: getattr(f, "nivel", None) for f in dossier.sentencias}
        ev = EvidenciaBanda(
            # Normas verificadas: BOE y Derecho de la UE (EUR-Lex).
            citas_boe_verificadas=sum(1 for f in fundamentos if f.source_id.startswith(("BOE:", "EUR:"))),
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
        # Coherencia interna: la solidez no puede ser favorable si TODAS las cuestiones se estiman a favor de la
        # otra parte (o al revés sin avisarlo).
        a_favor = sum(1 for q in res.cuestiones if q.estimacion == "DEFENSA")
        favorables = (BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE, BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA)
        if res.cuestiones and a_favor == 0 and banda in favorables:
            banda = BandaSolidez.DISPARIDAD_DE_CRITERIO
            motivos.append(
                "Incoherencia: solidez favorable con todas las cuestiones estimadas a favor de la otra parte."
            )
            run.avisos.append(
                "La valoración era incoherente (todas las cuestiones a favor de la otra parte): "
                "se ha rebajado la solidez."
            )
        if run.discrepancias:
            if banda in favorables:
                banda = BandaSolidez.DISPARIDAD_DE_CRITERIO
            motivos.append("Dos resoluciones independientes discrepan en: " + ", ".join(run.discrepancias))
            run.avisos.append(
                "Dos resoluciones independientes no coinciden en "
                + ", ".join(run.discrepancias)
                + ": el resultado depende de cómo se interprete y la solidez se ha ajustado."
            )
        # La banda refleja lo que queda verificado: si el cortafuegos eliminó parte de la respuesta directa o al menos
        # un tercio de las afirmaciones jurídicas, la solidez propuesta no está respaldada y se rebaja un nivel.
        juridicas = [v for v in fw.veredictos if v.tipo_propuesto in ("norma", "razonamiento")]
        quitadas = [v for v in juridicas if v.tipo_final is None]
        if any(v.seccion == "respuesta" for v in quitadas) or (juridicas and 3 * len(quitadas) >= len(juridicas)):
            rebajada = lower_band(banda)
            if rebajada != banda:
                motivos.append(
                    f"El cortafuegos eliminó {len(quitadas)} de {len(juridicas)} afirmaciones jurídicas: "
                    "la solidez se rebaja un nivel."
                )
                run.avisos.append("La solidez se ha rebajado porque parte del razonamiento no superó la verificación.")
                banda = rebajada
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

        self._emit(run, "deadline", {"plazos": [p.model_dump(mode="json") for p in plazos], "avisos": avisos_plazos})
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

        notas = [sub.notas] if sub and sub.notas else []  # nota fija de la materia en el catálogo
        avisos = list(dict.fromkeys([*notas, *run.avisos, *dossier.avisos, *avisos_plazos, *motivos]))
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
        citadas = {f.source_id for f in fundamentos} | {
            c["source_id"] for v in fw.veredictos if v.tipo_final for c in v.citas
        }
        sello = SelloVerificacion(
            verificado_en=datetime.now(UTC),
            fuentes=[
                FuenteSellada(
                    source_id=sid,
                    titulo=fuentes[sid].titulo,
                    version=sid.rsplit(":", 1)[-1] if sid.startswith("BOE:") and sid.count(":") >= 3 else None,
                    sha256=hashlib.sha256(fuentes[sid].texto_verbatim.encode("utf-8")).hexdigest(),
                    url=getattr(fuentes[sid], "url_oficial", None),
                )
                for sid in sorted(citadas)
                if sid in fuentes
            ],
            afirmaciones_mostradas=sum(1 for v in fw.veredictos if v.tipo_final is not None),
            afirmaciones_eliminadas=sum(1 for v in fw.veredictos if v.tipo_final is None),
            modelos=dict(run.modelos),
        )
        dictamen = DictamenCertificadoSchema(
            consulta_id=run.consulta_id,
            modo=cast(Any, run.modo),
            modelos_usados=run.modelos,
            banda_solidez=banda,
            respuesta_directa=respuesta_directa,
            resumen_ciudadano=resumen,
            fundamentos=fundamentos,
            cuestiones=res.cuestiones,
            fortalezas=[v.texto for v in fw.aceptadas("fortaleza")],
            debilidades_contraparte=[],
            riesgos_propios=[v.texto for v in fw.aceptadas("riesgo")],
            pasos_inmediatos=[v.texto for v in fw.aceptadas("paso")][:8],
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
            afirmaciones=[
                AfirmacionVerificada(
                    seccion=cast(Any, v.seccion),
                    texto=v.texto,
                    tipo=cast(Any, v.tipo_final),
                    citas=[
                        CitaVerificada(
                            source_id=c["source_id"], verbatim_quote=c["verbatim_quote"], score=c.get("score")
                        )
                        for c in v.citas
                    ],
                )
                for v in fw.veredictos
                if v.tipo_final is not None
            ],
            auditoria=[
                EntradaAuditoria(
                    seccion=v.seccion,
                    texto=v.texto,
                    tipo_propuesto=v.tipo_propuesto,
                    resultado=v.estado,
                    tipo_final=v.tipo_final,
                    citas_verificadas=[c["source_id"] for c in v.citas],
                    nli=v.nli,
                    motivos=v.motivos,
                )
                for v in fw.veredictos
            ]
            + auditoria_fund,
            respuesta_parcial=respuesta_parcial,
            hechos_determinantes=[h.pregunta for h in res.hechos_determinantes][:6],
            sello=sello,
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
            if self._pedir_hechos_determinantes(run, debate):
                return
            await self._guardarrailes(run, triage, dossier, debate)
        except Exception as exc:  # noqa: BLE001 — cualquier fallo se comunica a la UI
            log.exception("consulta %s fallida", consulta_id)
            try:
                self.s.store.set_estado(consulta_id, Estado.ERROR, error=str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
            self._emit(run, "error", {"mensaje": str(exc)[:500], "tipo": type(exc).__name__})


# Datos que el triaje puede preguntar, reconocidos por el tipo de respuesta o por palabras clave sobre el texto
# plegado con `fold`. Tabla genérica: los datos críticos de cada submateria se añadirán aquí.
_DATOS_PREGUNTABLES: dict[str, tuple[str, re.Pattern[str]]] = {
    "municipio": ("municipio", re.compile(r"\b(municipio|localidad|ciudad|poblacion|pueblo)\b")),
    "fecha": ("fecha", re.compile(r"\b(fecha|cuando|que dia)\b")),
    "importe": ("importe", re.compile(r"\b(importe|cuantia|cantidad|cuanto dinero|euros)\b")),
}


def _dato_preguntado(texto: str, tipo_respuesta: str | None = None) -> str | None:
    """Qué dato pide una pregunta (o una entrada de `datos_criticos_faltantes`); None si no es uno de la tabla."""
    por_tipo = next((dato for dato, (tipo, _) in _DATOS_PREGUNTABLES.items() if tipo == tipo_respuesta), None)
    if por_tipo:
        return por_tipo
    t = _fold(texto)
    return next((dato for dato, (_, patron) in _DATOS_PREGUNTABLES.items() if patron.search(t)), None)


def _importe_consta(cuantia: float | None, texto: str) -> bool:
    """¿El importe que da el modelo está escrito en la consulta («900», «1.200», «1 200»)? Si no, no cuenta."""
    if not cuantia or cuantia != int(cuantia):
        return False
    plano = re.sub(r"(?<=\d)[.\s](?=\d{3}\b)", "", texto)
    return re.search(rf"(?<![\d.,]){int(cuantia)}(?![\d]|[.,]\d)", plano) is not None


# Escalado del Magistrado tras dos verificaciones fallidas: siempre dentro de la misma familia.
_ESCALADO = {"agy_gemini_flash": "agy_gemini_argon"}

_TIPO_DATO: dict[str, Literal["fecha", "importe"]] = {"fecha": "fecha", "importe": "importe"}
_SI_NO = re.compile(r"^¿(es|estas|estabas|has|hay|te|ya|se|tienes|eres|fue)\b", re.IGNORECASE)


def _preguntas_campos_criticos(
    sub: Submateria,
    constan: list[dict[str, Any]],
    hechos: str,
    conocido: dict[str, bool],
    ya: list[PreguntaAclaratoria],
) -> list[PreguntaAclaratoria]:
    """Pregunta cada campo crítico que no conste. «Consta» = el modelo cita una frase literal de la consulta que
    lo contiene (verificada aquí) o es un dato que el código ya conoce (fecha del plazo, municipio, importe)."""
    hechos_plano = " ".join(_fold(hechos).split())
    probados = {
        _fold(str(c.get("campo", "")))
        for c in constan
        if len(_fold(str(c.get("cita", "")))) >= 3 and " ".join(_fold(str(c["cita"])).split()) in hechos_plano
    }
    textos_ya = " ".join(_fold(p.texto) for p in ya)
    out = []
    for i, campo in enumerate(sub.campos_criticos):
        dato = _dato_preguntado(campo)
        if _fold(campo) in probados or (dato and conocido.get(dato)):
            continue
        if dato == "municipio" or (dato == "fecha" and any(p.tipo_respuesta == "fecha" for p in ya)):
            continue  # el municipio y la fecha del plazo tienen su pregunta canónica
        clave = next((w for w in _fold(campo).split() if len(w) > 4), _fold(campo))
        if clave in textos_ya:
            continue  # el modelo ya lo pregunta con otras palabras
        si_no = campo.startswith("¿") and _SI_NO.match(_fold(campo))
        out.append(
            PreguntaAclaratoria(
                id=f"q_campo_{i}",
                texto=campo if campo.startswith("¿") else f"Indica {campo}",
                tipo_respuesta="si_no" if si_no else _TIPO_DATO.get(dato or "", "texto"),
                motivo="dato necesario para valorar tu caso",
            )
        )
    return out


def _campo_fecha(sub: Submateria) -> str:
    """El dato de fecha que inicia el plazo (p. ej. «fecha de entrega de llaves»); nunca otro campo crítico."""
    return next((c for c in sub.campos_criticos if "fecha" in c.lower()), "fecha del hecho principal")


def render_markdown(d: DictamenCertificadoSchema) -> str:
    lines = [
        f"# Dictamen Desemppa — {BANDA_TEXTO[d.banda_solidez]}",
        "",
        d.respuesta_directa,
        "",
        d.resumen_ciudadano,
        "",
    ]
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
