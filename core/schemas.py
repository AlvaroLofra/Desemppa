"""Contratos de datos entre fases (dossier Bloque 3.1). Pydantic v2."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Jurisdiccion(StrEnum):
    CIVIL = "civil"
    SOCIAL = "social"
    CONTENCIOSO = "contencioso"
    ADMINISTRATIVA_PREVIA = "administrativa_previa"
    PENAL = "penal"
    FUERA_ALCANCE = "fuera_alcance"


class Modo(StrEnum):
    ECO = "eco"
    EQUILIBRADO = "equilibrado"
    PRO = "pro"
    AUDITORIA = "auditoria"


class TipoComputo(StrEnum):
    HABILES_PROCESAL = "habiles_procesal"
    HABILES_ADMINISTRATIVO = "habiles_administrativo"
    HABILES_SOCIAL_CADUCIDAD = "habiles_social_caducidad"
    NATURALES = "naturales"
    MESES_FECHA_A_FECHA = "meses_fecha_a_fecha"
    ANIOS_FECHA_A_FECHA = "anios_fecha_a_fecha"


class NaturalezaPlazo(StrEnum):
    CADUCIDAD = "caducidad"
    PRESCRIPCION = "prescripcion"
    PROCESAL = "procesal"
    ADMINISTRATIVO = "administrativo"
    SUSTANTIVO = "sustantivo"


class BandaSolidez(StrEnum):
    CRITERIO_CONSOLIDADO_FAVORABLE = "criterio_consolidado_favorable"
    ARGUMENTO_SOLIDO_SIN_DOCTRINA = "argumento_solido_sin_doctrina"
    DISPARIDAD_DE_CRITERIO = "disparidad_de_criterio"
    RIESGO_PROBATORIO_ALTO = "riesgo_probatorio_alto"
    CRITERIO_CONSOLIDADO_DESFAVORABLE = "criterio_consolidado_desfavorable"
    NO_DETERMINABLE = "no_determinable"


# Orden de "solidez" para poder bajar de banda (nunca subir) en los guardarraíles.
BANDA_ORDEN = [
    BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE,
    BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA,
    BandaSolidez.DISPARIDAD_DE_CRITERIO,
    BandaSolidez.RIESGO_PROBATORIO_ALTO,
    BandaSolidez.NO_DETERMINABLE,
]
BANDA_TEXTO = {
    BandaSolidez.CRITERIO_CONSOLIDADO_FAVORABLE: "Criterio consolidado favorable",
    BandaSolidez.ARGUMENTO_SOLIDO_SIN_DOCTRINA: "Argumento sólido, sin doctrina consolidada",
    BandaSolidez.DISPARIDAD_DE_CRITERIO: "Disparidad de criterio entre tribunales",
    BandaSolidez.RIESGO_PROBATORIO_ALTO: "Depende de pruebas que quizá no tengas",
    BandaSolidez.CRITERIO_CONSOLIDADO_DESFAVORABLE: "Criterio consolidado desfavorable",
    BandaSolidez.NO_DETERMINABLE: "No es posible valorar",
}

SourceId = Annotated[str, Field(pattern=r"^(BOE|ROJ|CONV|DOC|EUR):.+")]
IdNormaBOE = Annotated[str, Field(pattern=r"^BOE-A-\d{4}-\d{1,6}$")]
CodigoINE = Annotated[str, Field(pattern=r"^\d{5}$")]
VecindadCivil = Literal["comun", "catalana", "aragonesa", "navarra", "vasca", "gallega", "balear", "desconocida"]

# G4: un porcentaje cerca de vocabulario de pronóstico (éxito, ganar, probabilidad...). Los porcentajes
# normativos ("reducción del 50 %", "interés del 3 %") están permitidos.
_PERCENT = r"\d+(?:[.,]\d+)?\s*(?:%|por\s*ciento)"
_PRONOSTICO = (
    r"(?:probabilidad|posibilidad|opci[óo]n|[ée]xito|ganar|ganes|ganar[íi]a|prosperar|prosper[ae]|viabilidad|"
    r"victoria|perder|pierdas|probable|seguro\s+que|garant)"
)
PRONOSTICO_PORCENTUAL_RE = re.compile(
    rf"{_PRONOSTICO}[^.\n]{{0,60}}?{_PERCENT}|{_PERCENT}[^.\n]{{0,60}}?{_PRONOSTICO}", re.I
)
_PERCENT_RE = PRONOSTICO_PORCENTUAL_RE


# ---------- Fase 1 ----------
class RamaCandidata(BaseModel):
    submateria: str
    jurisdiccion: Jurisdiccion
    peso_enrutamiento: float = Field(ge=0, le=1)  # interno; nunca se muestra como pronóstico
    justificacion: str = Field(max_length=400)


class PreguntaAclaratoria(BaseModel):
    id: str
    texto: str = Field(max_length=300)
    tipo_respuesta: Literal["si_no", "fecha", "importe", "opcion", "texto", "municipio"]
    opciones: list[str] | None = None
    motivo: str = ""


class AlertaPlazo(BaseModel):
    tipo_plazo_id: str
    fecha_inicio_computo: date | None = None
    evento_inicio: str = ""


class NormaObjetivo(BaseModel):
    id_norma: IdNormaBOE
    articulos: list[str] = Field(min_length=1)
    motivo: str = ""


class TriageOutputSchema(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    consulta_id: str
    jurisdiccion_principal: Jurisdiccion
    submateria_principal: str
    ramas: list[RamaCandidata] = Field(min_length=1, max_length=4)
    grado_ambiguedad: float = Field(ge=0, le=1)
    requiere_aclaracion: bool = False
    preguntas_aclaracion: list[PreguntaAclaratoria] = Field(default_factory=list, max_length=5)
    datos_criticos_faltantes: list[str] = Field(default_factory=list)
    fecha_hechos: date | None = None
    municipio_ine_organo: CodigoINE | None = None
    vecindad_civil: VecindadCivil = "desconocida"
    cuantia_estimada_eur: float | None = Field(default=None, ge=0)
    alertas_plazo: list[AlertaPlazo] = Field(default_factory=list)
    normas_boe_objetivo: list[NormaObjetivo] = Field(default_factory=list)
    terminos_cendoj: list[str] = Field(default_factory=list, max_length=8)
    convenio_aplicable: str | None = None
    competencia_local: bool = False

    @model_validator(mode="after")
    def _coherencia(self) -> TriageOutputSchema:
        if self.grado_ambiguedad >= 0.35 and not self.preguntas_aclaracion:
            raise ValueError("ambigüedad alta sin preguntas aclaratorias")
        self.requiere_aclaracion = bool(self.preguntas_aclaracion) or bool(self.datos_criticos_faltantes)
        return self


# ---------- Fase 2 ----------
class FragmentoFuente(BaseModel):
    source_id: SourceId
    tipo: Literal["boe", "sentencia", "convenio", "adjunto", "ue"]
    titulo: str
    texto_verbatim: str
    url_oficial: str | None = None


class ArticuloBOE(FragmentoFuente):
    tipo: Literal["boe"] = "boe"
    id_norma: IdNormaBOE
    id_bloque: str
    version_fecha_vigencia: date
    vigente_a_fecha_hechos: bool
    reformado_tras_fecha_hechos: bool = False


class ArticuloUE(FragmentoFuente):
    """Artículo de una norma de la UE (texto del Diario Oficial vía Cellar/EUR-Lex)."""

    tipo: Literal["ue"] = "ue"
    celex: str
    articulo: str


class ExtractoSentencia(FragmentoFuente):
    tipo: Literal["sentencia"] = "sentencia"
    roj: str
    ecli: str | None = None
    tribunal: str
    nivel: Literal["TS", "AN", "TSJ", "AP", "JUZGADO"]
    fecha_resolucion: date
    seccion: Literal["fundamentos_mayoria", "fallo"]
    sentido_respecto_usuario: Literal["favorable", "desfavorable", "neutro", "no_determinado"] = "no_determinado"


class ClausulaConvenio(FragmentoFuente):
    tipo: Literal["convenio"] = "convenio"
    codigo_convenio: str
    version_id: str
    articulo: str
    vigencia_desde: date
    vigencia_hasta: date | None = None


class DossierIngestaSchema(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    consulta_id: str
    articulos_boe: list[ArticuloBOE]
    articulos_ue: list[ArticuloUE] = Field(default_factory=list)
    sentencias: list[ExtractoSentencia] = Field(default_factory=list, max_length=8)
    clausulas_convenio: list[ClausulaConvenio] = Field(default_factory=list)
    extractos_adjuntos: list[FragmentoFuente] = Field(default_factory=list)
    resumen_hechos: str = Field(max_length=2500)
    cobertura: Literal["completa", "degradada_sin_jurisprudencia", "degradada_sin_boe"]
    tokens_estimados: int = Field(le=12000)
    avisos: list[str] = Field(default_factory=list)

    @field_validator("sentencias")
    @classmethod
    def _sin_duplicados(cls, v: list[ExtractoSentencia]) -> list[ExtractoSentencia]:
        if len({s.roj for s in v}) != len(v):
            raise ValueError("ROJ duplicado")
        return v

    def fuentes(self) -> dict[str, FragmentoFuente]:
        items: list[FragmentoFuente] = [
            *self.articulos_boe,
            *self.articulos_ue,
            *self.sentencias,
            *self.clausulas_convenio,
            *self.extractos_adjuntos,
        ]
        return {f.source_id: f for f in items}


# ---------- Fase 3 ----------
class Cita(BaseModel):
    source_id: SourceId
    verbatim_quote: str = Field(min_length=20, max_length=1500)


class Argumento(BaseModel):
    afirmacion: str = Field(max_length=1200)
    citas: list[Cita] = Field(min_length=1)


TipoAfirmacion = Literal["norma", "razonamiento", "hecho", "consejo", "limite"]


class Afirmacion(BaseModel):
    """Una frase del texto para el ciudadano, con su tipo y sus citas (docs/cortafuegos.md).

    norma: lo que dice la ley (cita obligatoria; debe deducirse literalmente). razonamiento: inferencia apoyada en
    citas. hecho: lo que contó el ciudadano. consejo: acción práctica. limite: lo que no se sabe o falta."""

    texto: str = Field(min_length=3, max_length=900)
    tipo: TipoAfirmacion
    citas: list[Cita] = Field(default_factory=list)


def _como_afirmaciones(valor: Any, tipo_por_defecto: str) -> Any:
    """Compatibilidad: un texto suelto se trata como afirmación sin citas (el cortafuegos la eliminará si es
    jurídica). Así una salida en el formato antiguo no rompe la consulta, pero tampoco cuela sin verificar."""
    if isinstance(valor, str):
        return [{"texto": valor, "tipo": tipo_por_defecto}] if valor.strip() else []
    if isinstance(valor, list):
        return [{"texto": v, "tipo": tipo_por_defecto} if isinstance(v, str) else v for v in valor if v]
    return valor


class CuestionAlegada(BaseModel):
    id: str
    argumentos: list[Argumento] = Field(min_length=1)


class AlegatoSchema(BaseModel):
    rol: Literal["DEFENSA", "CONTRAPARTE"]
    pretension: str
    cuestiones: list[CuestionAlegada] = Field(min_length=1)
    importe_reclamado_eur: float | None = None


class CuestionLitigiosa(BaseModel):
    id: str
    enunciado: str
    tipo: Literal["calificacion_juridica", "plazo", "competencia", "legitimacion", "cuantia"]
    estimacion: Literal["DEFENSA", "CONTRAPARTE"]  # disyuntiva estricta: no existe "PARCIAL"
    fundamentos: list[Argumento] = Field(min_length=1)
    importe_estimado_eur: float | None = None
    fundamento_cuantia: Cita | None = None

    @model_validator(mode="after")
    def _cuantia(self) -> CuestionLitigiosa:
        # Solo las cuestiones de cuantía admiten importe. Se descarta en vez de rechazar la resolución entera:
        # el benchmark en vivo mostró que el modelo a veces lo rellena en otras cuestiones y obligaba a reintentar.
        if self.tipo != "cuantia":
            self.importe_estimado_eur = None
            self.fundamento_cuantia = None
        elif self.fundamento_cuantia is None:
            # Un importe sin sentencia que lo respalde no se muestra (antes forzaba un reintento que, en el
            # benchmark, acabó en tres timeouts seguidos y en una consulta fallida).
            self.importe_estimado_eur = None
        return self


class HechoDeterminante(BaseModel):
    """Hecho que el ciudadano no ha contado y que cambiaría la estimación de una cuestión."""

    pregunta: str = Field(max_length=300)
    tipo_respuesta: Literal["si_no", "fecha", "importe", "opcion", "texto"] = "texto"
    opciones: list[str] | None = None
    cuestion_id: str = ""
    por_que: str = Field(default="", max_length=300)


class ResolucionMagistradoSchema(BaseModel):
    cuestiones: list[CuestionLitigiosa] = Field(min_length=1)
    banda_propuesta: BandaSolidez
    razonamiento_banda: str
    # Texto para el ciudadano en afirmaciones tipadas y citadas: el cortafuegos verifica cada una.
    respuesta_directa: list[Afirmacion] = Field(default_factory=list, max_length=4)
    resumen_ciudadano: list[Afirmacion] = Field(default_factory=list, max_length=12)
    fortalezas: list[Afirmacion] = Field(default_factory=list, max_length=8)
    debilidades_contraparte: list[str] = Field(default_factory=list)
    riesgos_propios: list[Afirmacion] = Field(default_factory=list, max_length=8)
    pasos_inmediatos: list[Afirmacion] = Field(default_factory=list, max_length=8)
    hechos_determinantes: list[HechoDeterminante] = Field(default_factory=list, max_length=6)

    @field_validator("respuesta_directa", "resumen_ciudadano", "fortalezas", "riesgos_propios", mode="before")
    @classmethod
    def _texto_suelto(cls, v: Any) -> Any:
        return _como_afirmaciones(v, "razonamiento")

    @field_validator("pasos_inmediatos", mode="before")
    @classmethod
    def _pasos_sueltos(cls, v: Any) -> Any:
        return _como_afirmaciones(v, "consejo")


# ---------- Fase 4 / salida final ----------
class Fundamento(BaseModel):
    texto: str
    source_id: SourceId
    verbatim_quote: str
    fuzzy_score: float = Field(ge=95, le=100)
    nli: Literal["ENTAILS", "NEUTRAL"]
    offsets: tuple[int, int]


class PlazoCalculado(BaseModel):
    tipo_plazo_id: str
    descripcion: str
    naturaleza: NaturalezaPlazo
    tipo_computo: TipoComputo
    titular: Literal["usuario", "contraparte"] = "usuario"
    fecha_inicio: date
    fecha_limite_segura: date
    dia_gracia_hasta: datetime | None = None
    dias_habiles_restantes: int | None = None
    festivos_no_verificados: list[date] = Field(default_factory=list)
    municipio_ine: str | None = None
    base_legal: str
    suspensiones: list[str] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    validado_juridicamente: bool = False


class AdvertenciaPostulacion(BaseModel):
    requiere_abogado: bool
    requiere_procurador: bool
    bloquea_escritos: bool
    base_legal: str
    texto_usuario: str


class CitaVerificada(BaseModel):
    source_id: str
    verbatim_quote: str
    score: float | None = None


class AfirmacionVerificada(BaseModel):
    """Afirmación que ha superado el cortafuegos, tal como se muestra (con su tipo final y su base)."""

    seccion: Literal["respuesta", "resumen", "fortaleza", "riesgo", "paso"]
    texto: str
    tipo: TipoAfirmacion
    citas: list[CitaVerificada] = Field(default_factory=list)


class EntradaAuditoria(BaseModel):
    """Qué hizo el cortafuegos con cada afirmación del Magistrado (también las eliminadas)."""

    seccion: str
    texto: str
    tipo_propuesto: str
    resultado: Literal["aceptada", "reclasificada", "eliminada"]
    tipo_final: str | None = None
    citas_verificadas: list[str] = Field(default_factory=list)
    nli: str | None = None
    motivos: list[str] = Field(default_factory=list)


class FuenteSellada(BaseModel):
    source_id: str
    titulo: str
    version: str | None = None  # redacción vigente desde (BOE)
    sha256: str  # del texto exacto contra el que se verificaron las citas
    url: str | None = None


class SelloVerificacion(BaseModel):
    """Lo necesario para que un tercero recompruebe el dictamen (benchmark/instrucciones_verificador.md)."""

    verificado_en: datetime
    fuentes: list[FuenteSellada] = Field(default_factory=list)
    afirmaciones_mostradas: int = 0
    afirmaciones_eliminadas: int = 0
    modelos: dict[str, str] = Field(default_factory=dict)


class DictamenCertificadoSchema(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    consulta_id: str
    modo: Modo
    modelos_usados: dict[str, str]
    banda_solidez: BandaSolidez
    respuesta_directa: str = ""
    resumen_ciudadano: str = Field(max_length=2000)
    fundamentos: list[Fundamento]
    cuestiones: list[CuestionLitigiosa] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    debilidades_contraparte: list[str] = Field(default_factory=list)
    riesgos_propios: list[str] = Field(default_factory=list)
    pasos_inmediatos: list[str] = Field(default_factory=list, max_length=8)
    plazos: list[PlazoCalculado] = Field(default_factory=list)
    postulacion: AdvertenciaPostulacion | None = None
    avisos: list[str] = Field(default_factory=list)
    guardarrailes: dict[str, bool] = Field(default_factory=dict)
    afirmaciones: list[AfirmacionVerificada] = Field(default_factory=list)
    auditoria: list[EntradaAuditoria] = Field(default_factory=list)
    respuesta_parcial: bool = False  # la respuesta directa no superó la verificación: se dice lo que no se sabe
    hechos_determinantes: list[str] = Field(default_factory=list)  # hechos sin aclarar que cambiarían el resultado
    sello: SelloVerificacion | None = None
    aviso_legal: str
    generado_en: datetime

    @field_validator("resumen_ciudadano", "respuesta_directa")
    @classmethod
    def _sin_porcentajes(cls, v: str) -> str:
        if _PERCENT_RE.search(v):
            raise ValueError("prohibido expresar porcentajes en el resumen")
        return v


AVISO_LEGAL = (
    "Desemppa es una herramienta personal de información jurídica y apoyo a la autodefensa. No es "
    "asesoramiento profesional ni sustituye a un abogado colegiado. Verifica los plazos y las citas en las "
    "fuentes oficiales enlazadas antes de actuar. Si no tienes recursos, puedes solicitar asistencia "
    "jurídica gratuita (Ley 1/1996) en el Colegio de Abogados de tu partido judicial."
)
