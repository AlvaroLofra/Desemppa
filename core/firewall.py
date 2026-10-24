"""Cortafuegos anti-invención (docs/cortafuegos.md).

Dos piezas:
1. `escanear`: escáner DETERMINISTA (sin LLM) de cada texto que se va a mostrar. Toda referencia a una norma
   (artículo, ley), a jurisprudencia, cifra (importe, porcentaje, duración) o fecha tiene que tener respaldo:
   - normas y artículos: deben estar en el dossier de la consulta;
   - jurisprudencia: solo si hay sentencias en el corpus de la consulta;
   - cifras y fechas: deben aparecer en lo que contó el ciudadano, en las fuentes o en los plazos calculados.
2. `verificar_afirmaciones`: cada afirmación del Magistrado llega con un tipo y sus citas y se acepta, reclasifica
   o elimina según reglas fijas (cita literal + NLI + hechos + escáner). Lo que no pasa no llega al ciudadano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from core.errors import ProviderError
from core.fechas_es import fechas_en_texto
from core.materias import normas
from core.nli import NLIChecker, hechos_no_constatados
from core.normalize import fold
from core.router import ModelRouter
from core.schemas import Afirmacion, ArticuloBOE, ArticuloUE, FragmentoFuente, PlazoCalculado
from core.validators import verify_quote

Seccion = Literal["respuesta", "resumen", "fortaleza", "riesgo", "paso", "fundamento"]

# Nombres habituales de las normas del catálogo (además de su alias y su número «29/1994»).
NOMBRES: dict[str, list[str]] = {
    "CE": ["constitucion espanola", "constitucion"],
    "CC": ["codigo civil"],
    "CP": ["codigo penal"],
    "LEC": ["ley de enjuiciamiento civil", "enjuiciamiento civil"],
    "ET": ["estatuto de los trabajadores"],
    "LRJS": ["ley reguladora de la jurisdiccion social", "jurisdiccion social"],
    "LGSS": ["ley general de la seguridad social"],
    "LETA": ["estatuto del trabajo autonomo"],
    "L15_2022": ["ley integral para la igualdad de trato"],
    "LAU": ["ley de arrendamientos urbanos", "arrendamientos urbanos"],
    "LPH": ["ley de propiedad horizontal", "ley sobre propiedad horizontal"],
    "TRLGDCU": [
        "ley general para la defensa de los consumidores",
        "ley de consumidores",
        "ley general de consumidores",
    ],
    "LCGC": ["ley de condiciones generales de la contratacion", "condiciones generales de la contratacion"],
    "LCCI": ["ley de contratos de credito inmobiliario", "credito inmobiliario"],
    "LCS": ["ley de contrato de seguro"],
    "LPAC": ["ley del procedimiento administrativo comun", "procedimiento administrativo comun"],
    "LRJSP": ["ley de regimen juridico del sector publico"],
    "LJCA": ["ley de la jurisdiccion contencioso"],
    "LSV": ["ley de trafico", "ley sobre trafico", "ley de seguridad vial"],
    "LGT": ["ley general tributaria"],
    "LOEFICIENCIA": ["ley de eficiencia del servicio publico de justicia", "ley organica 1/2025", "lo 1/2025"],
    "CCCAT_L1": ["codigo civil de cataluna", "codi civil de catalunya", "cccat"],
    "CCCAT_L2": ["codigo civil de cataluna", "codi civil de catalunya", "cccat"],
    "CCCAT_L4": ["codigo civil de cataluna", "codi civil de catalunya", "cccat"],
    "CCCAT_L5": ["codigo civil de cataluna", "codi civil de catalunya", "cccat"],
    "CCCAT_L6": ["codigo civil de cataluna", "codi civil de catalunya", "cccat"],
}
_ART = re.compile(
    r"\bart(?:[ií]culos?|s?\.)\s*(\d+(?:-\d+)?(?:\s?bis)?)(?:[.\d]*)((?:\s*(?:,|y)\s*\d+(?:-\d+)?(?:[.\d]*))*)", re.I
)
_LEY_NUM = re.compile(
    r"\b(?:ley(?:\s+org[aá]nica)?|lo|real\s+decreto(?:[\s-]+(?:legislativo|ley))?|rdleg|rdl|rd|"
    r"reglamento(?:\s*\((?:ce|ue|cee)\))?(?:\s*n\.?\s*[ºo°])?|directiva(?:\s*\((?:ce|ue|cee)\))?)\s*(\d+/\d{2,4})",
    re.I,
)
_JURIS_ID = re.compile(
    r"\b(?:SSTS|STS|STSJ|SAP|STC|ATS|STJUE)\s*(?:\d|de\s+\d)|\bC-\d+/\d{2}\b|\bECLI:[A-Z]{2}:|\bROJ:?\s*S[A-Z]{1,3}\s*\d+/\d{4}"
)
_JURIS_DOCTRINA = re.compile(
    r"\b(?:el|la|los)\s+(?:tribunal\s+supremo|supremo|tjue|tribunal\s+de\s+justicia(?:\s+de\s+la\s+uni[oó]n\s+europea)?|"
    r"tribunal\s+constitucional|audiencias?(?:\s+provinciales?)?)\s+(?:ya\s+)?(?:ha[n]?\s+)?"
    r"(?:establecido|declarado|dicho|resuelto|reconocido|considera|considerado|sostiene|sostenido|fijado|confirmado)",
    re.I,
)
_DINERO = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s*(?:€|euros?\b)", re.I)
_PORCENTAJE = re.compile(r"(\d+(?:,\d+)?)\s*(?:%|por\s+ciento)", re.I)
_DURACION = re.compile(r"\b(\d+|[a-záéíóúñ]+)\s+(d[ií]as?|semanas?|meses|mes|años?|horas?)\b", re.I)
_PALABRAS_NUM = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "quinientos": 500, "mil": 1000,
}  # fmt: skip
_TRIVIALES = {0.0, 1.0}  # «un mes», «una vez»: no aportan una cifra jurídica


@dataclass
class Hallazgo:
    tipo: Literal["norma", "jurisprudencia", "cifra", "fecha"]
    fragmento: str
    motivo: str


@dataclass
class Contexto:
    """Todo lo que respalda un texto: fuentes del dossier, lo que contó el ciudadano y los plazos calculados."""

    fuentes: dict[str, FragmentoFuente]
    hechos: str
    hoy: date
    plazos: list[PlazoCalculado] = field(default_factory=list)
    numeros_plazos: set[float] = field(default_factory=set)  # duraciones de las reglas de plazo aplicadas
    # Textos que genera el propio sistema de forma determinista (base legal de los plazos y de la postulación): sus
    # referencias y cifras también respaldan lo que se diga.
    referencias_extra: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.articulos: dict[str, set[str]] = {}  # clave de norma (alias, EUR:celex, CONV:código) -> artículos
        self.numeros_ley: dict[str, str] = {}  # «29/1994» -> clave
        for f in self.fuentes.values():
            for clave, art in _norma_y_articulo(f):
                self.articulos.setdefault(clave, set()).add(art)
        for alias, datos in normas().items():
            m = re.search(r"(\d+/\d{4})", str(datos["titulo"]))
            if m:
                self.numeros_ley[m.group(1)] = alias
        for f in self.fuentes.values():
            if isinstance(f, ArticuloUE):
                m = re.search(r"(\d+/\d{4})", f.titulo)
                if m:
                    self.numeros_ley[m.group(1)] = f"EUR:{f.celex}"
        self.leyes_extra: set[str] = set()
        for txt in self.referencias_extra:
            for tramo in txt.split(";"):
                for m in _ART.finditer(tramo):
                    numeros = [m.group(1), *re.findall(r"\d+(?:-\d+)?", m.group(2) or "")]
                    for clave in self.normas_mencionadas(tramo[m.end() : m.end() + 90]) or set():
                        self.articulos.setdefault(clave, set()).update(n.replace(" ", "") for n in numeros)
                self.leyes_extra.update(m.group(1) for m in _LEY_NUM.finditer(tramo))
            self.numeros_plazos |= numeros_en(txt)
        self.sentencias = {sid[4:] for sid in self.fuentes if sid.startswith("ROJ:")}
        self.numeros_hechos = numeros_en(self.hechos)
        self.numeros_fuentes = {sid: numeros_en(f.texto_verbatim) for sid, f in self.fuentes.items()}
        self.fechas_hechos = fechas_en_texto(self.hechos, self.hoy).exactas
        self.fechas_fuentes: set[date] = set()
        for f in self.fuentes.values():
            self.fechas_fuentes |= fechas_en_texto(f.texto_verbatim, self.hoy).exactas
        self.fechas_plazos: set[date] = set()
        for p in self.plazos:
            self.fechas_plazos |= {p.fecha_inicio, p.fecha_limite_segura}
            if p.dia_gracia_hasta:
                self.fechas_plazos.add(p.dia_gracia_hasta.date())
            restantes = (p.fecha_limite_segura - self.hoy).days
            self.numeros_plazos |= {float(abs(restantes))}
            if p.dias_habiles_restantes is not None:
                self.numeros_plazos.add(float(p.dias_habiles_restantes))

    def normas_mencionadas(self, ventana: str) -> set[str] | None:
        """Claves de norma nombradas en un fragmento («del Estatuto de los Trabajadores», «LAU», «Ley 29/1994»)."""
        t, claves = fold(ventana), set()
        for alias, nombres in NOMBRES.items():
            if any(n in t for n in nombres):
                claves.add(alias)
        for alias in normas():
            if len(alias) >= 2 and re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", ventana):
                claves.add(alias)
        for numero, clave in self.numeros_ley.items():
            if numero in ventana:
                claves.add(clave)
        if "reglamento" in t or "ce)" in t:
            claves |= {k for k in self.articulos if k.startswith("EUR:")}
        if "convenio" in t:
            claves |= {k for k in self.articulos if k.startswith("CONV:")}
        # «Código Civil de Cataluña» no es el Código Civil estatal
        if "codigo civil de catalu" in t or "codi civil" in t:
            claves.discard("CC")
        return claves or None


def _norma_y_articulo(f: FragmentoFuente) -> list[tuple[str, str]]:
    if isinstance(f, ArticuloUE):
        return [(f"EUR:{f.celex}", f.articulo)]
    if isinstance(f, ArticuloBOE) or f.source_id.startswith("BOE:"):
        id_norma = f.source_id.split(":")[1]
        claves = [a for a, d in normas().items() if d["id"] == id_norma] or [id_norma]
        art = _numero_articulo(f.titulo)
        return [(c, art) for c in claves] if art else []
    if f.source_id.startswith("CONV:"):
        partes = f.source_id.split(":")
        return [(f"CONV:{partes[1]}", partes[-1].removeprefix("art"))]
    return []


def _numero_articulo(titulo: str) -> str | None:
    from connectors.boe_client import _NUM_PALABRA

    m = re.search(r"art[ií]culo\s+(\d+(?:-\d+)?(?:\s?bis)?|[a-záéíóúü]+)", fold(titulo), re.I)
    if not m:
        m = re.search(r"\bart\.\s*(\d+(?:-\d+)?)", titulo, re.I)
        return m.group(1) if m else None
    valor = m.group(1)
    return valor.replace(" ", "") if valor[0].isdigit() else _NUM_PALABRA.get(valor)


def numeros_en(texto: str) -> set[float]:
    """Cifras de un texto, en número o en letra («veinte días», «2.000 €», «10 por ciento»)."""
    out: set[float] = set()
    for m in re.finditer(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", texto):
        out.add(_a_numero(m.group(0)))
    for palabra in re.findall(r"[a-záéíóúñ]+", fold(texto)):
        if palabra in _PALABRAS_NUM:
            out.add(float(_PALABRAS_NUM[palabra]))
    return out


def _a_numero(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def escanear(
    texto: str,
    ctx: Contexto,
    *,
    citas: list[str] | None = None,
    permite_referencias: bool = True,
) -> list[Hallazgo]:
    """Referencias sin respaldo en `texto`. `citas`: fuentes en las que se apoya (para cifras); None = todas.
    `permite_referencias=False` (consejos y límites): no puede nombrar normas ni sentencias."""
    hallazgos: list[Hallazgo] = []
    usados: list[tuple[int, int]] = []

    # 1) Artículos («art. 36 LAU», «artículos 1561 y 1562 del Código Civil»)
    for m in _ART.finditer(texto):
        usados.append(m.span())
        if not permite_referencias:
            hallazgos.append(Hallazgo("norma", m.group(0), "un consejo o límite no puede citar normas"))
            continue
        numeros = [m.group(1), *re.findall(r"\d+(?:-\d+)?", m.group(2) or "")]
        ventana = texto[m.end() : m.end() + 90]
        mencionadas = ctx.normas_mencionadas(ventana)
        for num in numeros:
            num = num.replace(" ", "")
            if mencionadas is not None:
                if not any(num in ctx.articulos.get(c, set()) for c in mencionadas):
                    hallazgos.append(
                        Hallazgo(
                            "norma", f"art. {num} ({', '.join(sorted(mencionadas))})", "artículo ausente del dossier"
                        )
                    )
            elif not any(num in arts for arts in ctx.articulos.values()):
                hallazgos.append(Hallazgo("norma", f"art. {num}", "artículo ausente del dossier"))

    # 2) Leyes por número («Ley 29/1994», «Reglamento (CE) 261/2004», «LO 1/2025»)
    for m in _LEY_NUM.finditer(texto):
        usados.append(m.span())
        if not permite_referencias:
            hallazgos.append(Hallazgo("norma", m.group(0), "un consejo o límite no puede citar normas"))
            continue
        clave = ctx.numeros_ley.get(m.group(1))
        if m.group(1) in ctx.leyes_extra:
            continue
        if clave is None or clave not in ctx.articulos:
            hallazgos.append(Hallazgo("norma", m.group(0), "norma ausente del dossier"))

    # 3) Jurisprudencia
    for patron in (_JURIS_ID, _JURIS_DOCTRINA):
        for m in patron.finditer(texto):
            if not permite_referencias or not ctx.sentencias:
                hallazgos.append(
                    Hallazgo("jurisprudencia", m.group(0), "no hay sentencias en el corpus de la consulta")
                )
            elif patron is _JURIS_ID and not any(s in texto for s in ctx.sentencias):
                hallazgos.append(Hallazgo("jurisprudencia", m.group(0), "sentencia ausente del corpus"))

    # 4) Cifras: importes, porcentajes y duraciones
    permitidas = set(ctx.numeros_hechos) | ctx.numeros_plazos | _TRIVIALES
    if permite_referencias:
        for sid in citas if citas is not None else list(ctx.numeros_fuentes):
            permitidas |= ctx.numeros_fuentes.get(sid, set())

    def dentro_de_referencia(pos: int) -> bool:
        return any(a <= pos < b for a, b in usados)

    for patron, nombre in ((_DINERO, "importe"), (_PORCENTAJE, "porcentaje"), (_DURACION, "duración")):
        for m in patron.finditer(texto):
            if dentro_de_referencia(m.start()):
                continue
            bruto = m.group(1)
            if bruto[0].isdigit():
                valor = _a_numero(bruto + ("," + m.group(2) if patron is _DINERO and m.group(2) else ""))
            elif fold(bruto) in _PALABRAS_NUM:
                valor = float(_PALABRAS_NUM[fold(bruto)])
            else:
                continue  # «varios días», «pocos meses»: no es una cifra
            if valor not in permitidas:
                hallazgos.append(
                    Hallazgo("cifra", m.group(0), f"{nombre} sin respaldo en la consulta, las fuentes o los plazos")
                )

    # 5) Fechas exactas
    for f in fechas_en_texto(texto, ctx.hoy).exactas:
        if f not in ctx.fechas_hechos | ctx.fechas_plazos | ctx.fechas_fuentes:
            hallazgos.append(
                Hallazgo("fecha", f.strftime("%d/%m/%Y"), "fecha que no consta ni sale del cálculo de plazos")
            )
    return hallazgos


# ---------- verificación de afirmaciones ----------


@dataclass
class Veredicto:
    seccion: Seccion
    texto: str
    tipo_propuesto: str
    tipo_final: str | None  # None = eliminada
    citas: list[dict[str, Any]] = field(default_factory=list)  # {source_id, verbatim_quote, ok, score, offsets}
    motivos: list[str] = field(default_factory=list)
    nli: str | None = None

    @property
    def estado(self) -> Literal["aceptada", "reclasificada", "eliminada"]:
        if self.tipo_final is None:
            return "eliminada"
        return "reclasificada" if self.tipo_final != self.tipo_propuesto else "aceptada"


@dataclass
class ResultadoFirewall:
    veredictos: list[Veredicto]
    avisos: list[str] = field(default_factory=list)

    def aceptadas(self, seccion: Seccion) -> list[Veredicto]:
        return [v for v in self.veredictos if v.seccion == seccion and v.tipo_final is not None]

    def fallos(self) -> list[str]:
        """Mensajes para el reintento del Magistrado (qué se eliminó y por qué)."""
        return [
            f"[{v.seccion}] «{v.texto[:140]}» eliminada: {'; '.join(v.motivos)}"
            for v in self.veredictos
            if v.tipo_final is None
        ]


def _verificar_citas(afirmacion: Afirmacion, fuentes: dict[str, FragmentoFuente]) -> list[dict[str, Any]]:
    out = []
    for c in afirmacion.citas:
        fuente = fuentes.get(c.source_id)
        if fuente is None:
            out.append(
                {
                    "source_id": c.source_id,
                    "verbatim_quote": c.verbatim_quote,
                    "ok": False,
                    "motivo": "fuente inexistente",
                }
            )
            continue
        chk = verify_quote(c.verbatim_quote, fuente.texto_verbatim)
        out.append(
            {
                "source_id": c.source_id,
                "verbatim_quote": c.verbatim_quote,
                "ok": chk.ok and chk.offsets is not None,
                "score": round(chk.score, 1),
                "offsets": chk.offsets,
                "motivo": chk.motivo,
            }
        )
    return out


async def verificar_afirmaciones(
    afirmaciones: list[tuple[Seccion, Afirmacion]],
    ctx: Contexto,
    router: ModelRouter,
    perfil: str,
    *,
    consulta_id: str | None = None,
) -> ResultadoFirewall:
    resultado = ResultadoFirewall([])
    pendientes_nli: list[Veredicto] = []
    for seccion, a in afirmaciones:
        v = Veredicto(seccion, a.texto.strip(), a.tipo, a.tipo)
        v.citas = _verificar_citas(a, ctx.fuentes)
        validas = [c for c in v.citas if c["ok"]]
        for c in v.citas:
            if not c["ok"]:
                v.motivos.append(f"cita a {c['source_id']} no literal ({c.get('motivo') or 'no encontrada'})")
        if a.tipo in ("norma", "razonamiento") and not validas:
            v.tipo_final = None
            v.motivos.append("afirmación jurídica sin ninguna cita verificada")
        hallazgos = escanear(
            v.texto,
            ctx,
            citas=[c["source_id"] for c in validas] if a.tipo in ("norma", "razonamiento") else [],
            permite_referencias=a.tipo in ("norma", "razonamiento"),
        )
        if hallazgos:
            v.tipo_final = None
            v.motivos += [f"{h.motivo}: «{h.fragmento}»" for h in hallazgos]
        v.citas = validas
        resultado.veredictos.append(v)
        if v.tipo_final is not None and a.tipo in ("norma", "razonamiento"):
            pendientes_nli.append(v)

    # NLI: ¿lo que afirma se deduce de lo que cita? (norma exige ENTAILS; NEUTRAL pasa a razonamiento)
    if pendientes_nli:
        pares = [(" […] ".join(c["verbatim_quote"] for c in v.citas), v.texto) for v in pendientes_nli]
        try:
            etiquetas = [r.label for r in await NLIChecker(router, perfil).check(pares, consulta_id=consulta_id)]
        except (ProviderError, ValueError) as exc:
            etiquetas = ["NEUTRAL"] * len(pares)
            resultado.avisos.append(
                f"No se pudo comprobar la inferencia de algunas afirmaciones ({type(exc).__name__})."
            )
        for v, etiqueta in zip(pendientes_nli, etiquetas, strict=False):
            v.nli = etiqueta
            if etiqueta == "CONTRADICTS":
                v.tipo_final = None
                v.motivos.append("la afirmación contradice la fuente que cita (NLI)")
            elif v.tipo_propuesto == "norma" and etiqueta != "ENTAILS":
                v.tipo_final = "razonamiento"
                v.motivos.append("la fuente no lo dice literalmente: se muestra como razonamiento")

    # Hechos: nada puede afirmar como ocurrido algo que el ciudadano no ha contado
    vivas = [v for v in resultado.veredictos if v.tipo_final is not None]
    try:
        inventadas = set(
            await hechos_no_constatados(router, perfil, [v.texto for v in vivas], ctx.hechos, consulta_id=consulta_id)
        )
    except (ProviderError, ValueError) as exc:
        inventadas = set()
        resultado.avisos.append(f"No se pudo comprobar que la respuesta no añade hechos ({type(exc).__name__}).")
    for v in vivas:
        if v.texto in inventadas:
            v.tipo_final = None
            v.motivos.append("atribuye un hecho que no consta en la consulta")
    return resultado
