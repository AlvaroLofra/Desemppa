"""Sincronización temporal (dossier §4 v2.1 y §1.2.1 v3): la ley aplicable es la vigente en la
fecha de los hechos, y una sentencia anterior a una reforma del precepto puede estar desfasada."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from connectors.boe_models import Bloque, BloqueVersion


@dataclass
class VersionAplicable:
    version: BloqueVersion | None
    vigente_a_fecha_hechos: bool
    reformado_tras_fecha_hechos: bool
    avisos: list[str] = field(default_factory=list)


def select_version(bloque: Bloque, fecha_hechos: date | None) -> VersionAplicable:
    actual = bloque.versiones[-1] if bloque.versiones else None
    ref = f"{bloque.titulo or bloque.id_bloque} ({bloque.id_norma})"
    if fecha_hechos is None:
        return VersionAplicable(
            version=actual,
            vigente_a_fecha_hechos=False,
            reformado_tras_fecha_hechos=False,
            avisos=[f"{ref}: se usa la redacción actual porque no consta la fecha de los hechos."],
        )
    version = bloque.version_at(fecha_hechos)
    if version is None:
        return VersionAplicable(
            version=None,
            vigente_a_fecha_hechos=False,
            reformado_tras_fecha_hechos=False,
            avisos=[f"{ref}: el precepto no estaba en vigor el {fecha_hechos:%d/%m/%Y}."],
        )
    reformado = version is not actual
    avisos = []
    if reformado:
        siguiente = next(v for v in bloque.versiones if v.vigencia_desde > fecha_hechos)
        avisos.append(
            f"{ref}: se aplica la redacción vigente el {fecha_hechos:%d/%m/%Y} "
            f"(desde {version.vigencia_desde:%d/%m/%Y}). Reformado después, por primera vez el "
            f"{siguiente.vigencia_desde:%d/%m/%Y} ({siguiente.id_norma_modificadora}). "
            "Revisar disposiciones transitorias."
        )
    return VersionAplicable(
        version=version, vigente_a_fecha_hechos=True, reformado_tras_fecha_hechos=reformado, avisos=avisos
    )


def sentencia_desfasada(bloque: Bloque, fecha_resolucion: date) -> str | None:
    """Aviso si el precepto se reformó después de la sentencia que lo interpreta."""
    posteriores = [v for v in bloque.versiones if v.vigencia_desde > fecha_resolucion]
    if not posteriores:
        return None
    return (
        f"La sentencia de {fecha_resolucion:%d/%m/%Y} interpreta {bloque.titulo or bloque.id_bloque} antes de "
        f"su reforma de {posteriores[0].vigencia_desde:%d/%m/%Y}: su doctrina puede no ser aplicable."
    )
