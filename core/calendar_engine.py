"""Motor de calendario judicial y cómputo de plazos (dossier §1.3.3 y §4.2).

Determinista: el LLM nunca calcula fechas. Principios:
- El calendario es el de la SEDE del órgano o de la Administración (municipio_ine), no el domicilio.
- Ante un día de carácter dudoso se cuenta como hábil (cómputo más corto) y se avisa.
- La "fecha límite segura" es el último día del plazo; el día de gracia (art. 135.5 LEC) solo se
  informa para escritos procesales y nunca se recomienda apurarlo.
"""

from __future__ import annotations

import calendar
import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from core.schemas import NaturalezaPlazo, PlazoCalculado, TipoComputo

ROOT = Path(__file__).resolve().parents[1]
PLAZOS_PATH = ROOT / "config" / "plazos.yaml"
FESTIVOS_DIR = ROOT / "data" / "festivos"
MUNICIPIOS_PATH = ROOT / "data" / "municipios_ine.csv"
MADRID_TZ = ZoneInfo("Europe/Madrid")
# Fiestas nacionales no sustituibles por las CCAA: se aplican en años sin resolución oficial cargada.
FIESTAS_FIJAS = {(1, 1), (5, 1), (10, 12), (12, 25)}


@dataclass(frozen=True)
class PlazoRule:
    id: str
    descripcion: str
    duracion: int
    computo: TipoComputo
    naturaleza: NaturalezaPlazo
    base_legal: str
    agosto_habil: bool = True
    dia_gracia: bool = False
    prorroga_inhabil_final: bool = True
    dias_dudosos: tuple[str, ...] = ()
    admite_suspension: bool = False
    doctrina_cambiante: bool = False
    notas: str = ""
    titular: Literal["usuario", "contraparte"] = "usuario"
    foral: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_rules(path: Path = PLAZOS_PATH) -> dict[str, PlazoRule]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["plazos"]
    rules: dict[str, PlazoRule] = {}
    for rid, r in raw.items():
        rules[rid] = PlazoRule(
            id=rid,
            descripcion=r["descripcion"],
            duracion=int(r["duracion"]),
            computo=TipoComputo(r["computo"]),
            naturaleza=NaturalezaPlazo(r["naturaleza"]),
            base_legal=r["base_legal"],
            agosto_habil=bool(r.get("agosto_habil", True)),
            dia_gracia=bool(r.get("dia_gracia", False)),
            prorroga_inhabil_final=bool(r.get("prorroga_inhabil_final", True)),
            dias_dudosos=tuple(r.get("dias_dudosos", [])),
            admite_suspension=bool(r.get("admite_suspension", False)),
            doctrina_cambiante=bool(r.get("doctrina_cambiante", False)),
            notas=r.get("notas", ""),
            titular="contraparte" if r.get("titular") == "contraparte" else "usuario",
            foral=r.get("foral", {}) or {},
        )
    return rules


@dataclass
class Municipio:
    codigo_ine: str
    nombre: str
    provincia: str
    ccaa: str


@dataclass
class Festivo:
    fecha: date
    ambito: str
    descripcion: str
    verificado: bool = True


class CalendarioFestivos:
    """Festivos nacionales/autonómicos (CSV del BOE) + locales (CSV y tabla `municipios_festivos`)."""

    def __init__(
        self,
        *,
        festivos_dir: Path = FESTIVOS_DIR,
        municipios_path: Path = MUNICIPIOS_PATH,
        con: sqlite3.Connection | None = None,
    ) -> None:
        self.municipios: dict[str, Municipio] = {}
        if municipios_path.exists():
            with municipios_path.open(encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    self.municipios[row["codigo_ine"]] = Municipio(**row)
        self._nacionales: dict[date, Festivo] = {}
        self._autonomicos: dict[tuple[str, date], Festivo] = {}
        self._locales: dict[tuple[str, date], Festivo] = {}
        self.years_nacional: set[int] = set()
        self.years_local: dict[str, set[int]] = {}
        for path in sorted(festivos_dir.glob("*.csv")):
            self._load_csv(path)
        if con is not None:
            self._load_db(con)

    def _add(self, fecha: date, ambito: str, ccaa: str | None, ine: str | None, desc: str, ok: bool) -> None:
        fest = Festivo(fecha, ambito, desc, ok)
        if ambito == "nacional":
            self._nacionales[fecha] = fest
            self.years_nacional.add(fecha.year)
        elif ambito == "autonomico" and ccaa:
            self._autonomicos[(ccaa, fecha)] = fest
        elif ambito == "local" and ine:
            self._locales[(ine, fecha)] = fest
            self.years_local.setdefault(ine, set()).add(fecha.year)

    def _load_csv(self, path: Path) -> None:
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self._add(
                    date.fromisoformat(row["fecha"]),
                    row["ambito"],
                    row.get("ccaa") or None,
                    row.get("codigo_ine") or None,
                    row["descripcion"],
                    True,
                )

    def _load_db(self, con: sqlite3.Connection) -> None:
        for r in con.execute(
            "SELECT fecha, ambito, ccaa, codigo_ine, descripcion, verificado FROM municipios_festivos"
        ):
            self._add(date.fromisoformat(r[0]), r[1], r[2], r[3], r[4], bool(r[5]))

    def add_local(self, codigo_ine: str, fecha: date, descripcion: str, *, verificado: bool = False) -> None:
        self._add(fecha, "local", None, codigo_ine, descripcion, verificado)

    def festivo(self, d: date, ccaa: str | None, ine: str | None) -> Festivo | None:
        return (
            self._nacionales.get(d)
            or (self._autonomicos.get((ccaa, d)) if ccaa else None)
            or (self._locales.get((ine, d)) if ine else None)
        )

    def ccaa_de(self, ine: str | None) -> str | None:
        return self.municipios[ine].ccaa if ine and ine in self.municipios else None


class PlazoError(ValueError):
    pass


def _add_months(d: date, months: int) -> date:
    """Fecha a fecha; si el mes de vencimiento no tiene ese día, el último día del mes (art. 30.4 Ley 39/2015)."""
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass
class _Ctx:
    rule: PlazoRule
    ccaa: str | None
    ine: str | None
    avisos: list[str]
    no_verificados: set[date]


class CalendarEngine:
    def __init__(self, festivos: CalendarioFestivos | None = None, rules: dict[str, PlazoRule] | None = None):
        self.festivos = festivos or CalendarioFestivos()
        self.rules = rules or load_rules()

    # ---------- carácter de un día ----------
    def _es_inhabil(self, d: date, ctx: _Ctx, computo: TipoComputo) -> bool:
        if computo == TipoComputo.NATURALES:
            return False
        dudoso = d.strftime("%d-%m") in ctx.rule.dias_dudosos or (d.month == 8 and "agosto" in ctx.rule.dias_dudosos)
        if d.weekday() >= 5:
            return True
        if computo == TipoComputo.HABILES_PROCESAL:
            if (d.month, d.day) in ((12, 24), (12, 31)):
                return True
            if d.month == 8 and not ctx.rule.agosto_habil:
                return True
        if self._festivo(d, ctx) is not None:
            return True
        if dudoso:
            ctx.avisos.append(
                f"El {d:%d/%m/%Y} se ha contado como hábil aunque su carácter es discutido (cómputo prudente)."
            )
        return False

    def _festivo(self, d: date, ctx: _Ctx) -> Any:
        if d.year not in self.festivos.years_nacional:
            ctx.avisos.append(
                f"No hay calendario oficial de festivos cargado para {d.year}: solo se han descontado las fiestas "
                "nacionales fijas (1-ene, 1-may, 12-oct, 25-dic)."
            )
            if (d.month, d.day) in FIESTAS_FIJAS:
                return Festivo(d, "nacional", "fiesta nacional fija")
            ctx.no_verificados.add(d)
            return None
        fest = self.festivos.festivo(d, ctx.ccaa, ctx.ine)
        if fest is not None and not fest.verificado:
            ctx.no_verificados.add(d)
        return fest

    def _es_inhabil_final(self, d: date, ctx: _Ctx) -> bool:
        """Carácter del último día a efectos de prórroga (meses/años/naturales usan el calendario de la sede)."""
        base = ctx.rule.computo
        if base in (TipoComputo.MESES_FECHA_A_FECHA, TipoComputo.ANIOS_FECHA_A_FECHA, TipoComputo.NATURALES):
            base = (
                TipoComputo.HABILES_PROCESAL
                if ctx.rule.naturaleza == NaturalezaPlazo.PROCESAL
                else TipoComputo.HABILES_ADMINISTRATIVO
            )
        return self._es_inhabil(d, ctx, base)

    def siguiente_habil(self, d: date, ctx: _Ctx) -> date:
        d += timedelta(days=1)
        while self._es_inhabil_final(d, ctx):
            d += timedelta(days=1)
        return d

    # ---------- cálculo ----------
    def compute(
        self,
        rule_id: str,
        fecha_inicio: date,
        *,
        municipio_ine: str | None = None,
        suspensiones: list[tuple[date, date]] | None = None,
        territorio_foral: str | None = None,
        hoy: date | None = None,
    ) -> PlazoCalculado:
        if rule_id not in self.rules:
            raise PlazoError(f"plazo desconocido: {rule_id}")
        rule = self.rules[rule_id]
        duracion, base_legal = rule.duracion, rule.base_legal
        if territorio_foral and territorio_foral in rule.foral:
            duracion = int(rule.foral[territorio_foral].get("duracion", duracion))
            base_legal = rule.foral[territorio_foral].get("base_legal", base_legal)
        avisos: list[str] = []
        ctx = _Ctx(rule, self.festivos.ccaa_de(municipio_ine), municipio_ine, avisos, set())
        if municipio_ine is None:
            avisos.append("Sin municipio de la sede: solo se han tenido en cuenta los festivos nacionales.")
        elif municipio_ine not in self.festivos.municipios:
            raise PlazoError(f"municipio INE desconocido: {municipio_ine}")
        elif rule.computo != TipoComputo.NATURALES and fecha_inicio.year not in self.festivos.years_local.get(
            municipio_ine, set()
        ):
            avisos.append(
                "Festivos locales del municipio no cargados para ese año: confirma las 2 fiestas locales en el "
                "boletín oficial de la provincia."
            )
        suspensiones = suspensiones or []
        if suspensiones and not rule.admite_suspension:
            raise PlazoError(f"el plazo {rule_id} no admite suspensiones en este motor")

        if rule.computo in (TipoComputo.MESES_FECHA_A_FECHA, TipoComputo.ANIOS_FECHA_A_FECHA):
            months = duracion * (12 if rule.computo == TipoComputo.ANIOS_FECHA_A_FECHA else 1)
            fin = _add_months(fecha_inicio, months)
            if not rule.agosto_habil:
                # Agosto no computa (p. ej. art. 128.2 LJCA): se añade un mes por cada agosto atravesado.
                contados_agosto: set[int] = set()
                while True:
                    nuevos = {
                        y
                        for y in range(fecha_inicio.year, fin.year + 1)
                        if date(y, 8, 1) <= fin and date(y, 8, 31) > fecha_inicio
                    } - contados_agosto
                    if not nuevos:
                        break
                    contados_agosto |= nuevos
                    fin = _add_months(fin, len(nuevos))
                if contados_agosto:
                    avisos.append("Agosto no computa en este plazo: se ha excluido del cómputo.")
        else:
            computo = rule.computo
            fin = fecha_inicio
            contados = 0
            while contados < duracion:
                fin += timedelta(days=1)
                if any(a <= fin <= b for a, b in suspensiones):
                    continue
                if not self._es_inhabil(fin, ctx, computo):
                    contados += 1
        if rule.prorroga_inhabil_final and self._es_inhabil_final(fin, ctx):
            fin_original = fin
            fin = self.siguiente_habil(fin, ctx)
            avisos.append(f"El {fin_original:%d/%m/%Y} es inhábil: el plazo se prorroga al {fin:%d/%m/%Y}.")

        gracia = None
        if rule.dia_gracia:
            gracia = datetime.combine(self.siguiente_habil(fin, ctx), time(15, 0), tzinfo=MADRID_TZ)
            avisos.append(
                "Día de gracia (art. 135.5 LEC): solo para presentar escritos ante el juzgado hasta las 15:00 del "
                "día hábil siguiente. No lo apures: la fecha recomendada es la fecha límite segura."
            )
        restantes = None
        if hoy is not None:
            restantes = self.dias_habiles_entre(hoy, fin, ctx) if hoy <= fin else 0
        if rule.doctrina_cambiante:
            avisos.append("🔎 Criterio con jurisprudencia cambiante: confírmalo con un profesional.")
        if rule.notas:
            avisos.append(rule.notas)
        return PlazoCalculado(
            tipo_plazo_id=rule.id,
            descripcion=rule.descripcion,
            naturaleza=rule.naturaleza,
            tipo_computo=rule.computo,
            titular=rule.titular,
            fecha_inicio=fecha_inicio,
            fecha_limite_segura=fin,
            dia_gracia_hasta=gracia,
            dias_habiles_restantes=restantes,
            festivos_no_verificados=sorted(ctx.no_verificados),
            municipio_ine=municipio_ine,
            base_legal=base_legal,
            suspensiones=[f"{a:%d/%m/%Y}–{b:%d/%m/%Y}" for a, b in suspensiones],
            avisos=list(dict.fromkeys(avisos)),
        )

    def dias_habiles_entre(self, desde: date, hasta: date, ctx: _Ctx) -> int:
        computo = ctx.rule.computo
        if computo in (TipoComputo.MESES_FECHA_A_FECHA, TipoComputo.ANIOS_FECHA_A_FECHA, TipoComputo.NATURALES):
            return (hasta - desde).days
        n, d = 0, desde
        while d < hasta:
            d += timedelta(days=1)
            if not self._es_inhabil(d, ctx, computo):
                n += 1
        return n
