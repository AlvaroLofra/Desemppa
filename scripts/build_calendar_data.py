"""Genera los datasets del calendario (dossier §1.3.3) a partir de fuentes oficiales.

  uv run python scripts/build_calendar_data.py municipios <diccionarioAA.xlsx del INE>
  uv run python scripts/build_calendar_data.py festivos <año> [<HTML de la resolución del BOE> | BOE-A-AAAA-NNNNN]

- municipios: https://www.ine.es/daco/daco42/codmun/diccionarioAA.xlsx -> data/municipios_ine.csv
- festivos: resolución anual de la Dirección General de Trabajo ("relación de fiestas laborales para el año AAAA")
  -> data/festivos/AAAA.csv (nacionales y autonómicos). Los locales se añaden aparte (BOP / usuario).
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

import httpx
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Código INE de comunidad -> código ISO 3166-2:ES usado en todo el proyecto
INE_CCAA = {
    "01": "AN",
    "02": "AR",
    "03": "AS",
    "04": "IB",
    "05": "CN",
    "06": "CB",
    "07": "CL",
    "08": "CM",
    "09": "CT",
    "10": "VC",
    "11": "EX",
    "12": "GA",
    "13": "MD",
    "14": "MC",
    "15": "NC",
    "16": "PV",
    "17": "RI",
    "18": "CE",
    "19": "ML",
}
PROVINCIAS = {
    "01": "Araba/Álava",
    "02": "Albacete",
    "03": "Alicante/Alacant",
    "04": "Almería",
    "05": "Ávila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Cáceres",
    "11": "Cádiz",
    "12": "Castellón/Castelló",
    "13": "Ciudad Real",
    "14": "Córdoba",
    "15": "A Coruña",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Gipuzkoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaén",
    "24": "León",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Málaga",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Asturias",
    "34": "Palencia",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantabria",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia/València",
    "47": "Valladolid",
    "48": "Bizkaia",
    "49": "Zamora",
    "50": "Zaragoza",
    "51": "Ceuta",
    "52": "Melilla",
}
# Orden de columnas de la tabla de la resolución del BOE
BOE_COLUMNS = [
    "AN",
    "AR",
    "AS",
    "IB",
    "CN",
    "CB",
    "CM",
    "CL",
    "CT",
    "EX",
    "GA",
    "MD",
    "MC",
    "NC",
    "PV",
    "RI",
    "VC",
    "CE",
    "ML",
]
MESES = {
    m: i
    for i, m in enumerate(
        [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ],
        start=1,
    )
}


def build_municipios(xlsx: Path) -> int:
    import openpyxl

    ws = openpyxl.load_workbook(xlsx, read_only=True).active
    out = DATA / "municipios_ine.csv"
    count = 0
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["codigo_ine", "nombre", "provincia", "ccaa"])
        for row in ws.iter_rows(values_only=True):
            codauto, cpro, cmun, _dc, nombre = (row + (None,) * 5)[:5]
            if not (isinstance(cpro, str) and cpro.isdigit() and isinstance(cmun, str) and cmun.isdigit()):
                continue
            writer.writerow([f"{cpro}{cmun}", nombre, PROVINCIAS[cpro], INE_CCAA[str(codauto).zfill(2)]])
            count += 1
    return count


def parse_festivos_html(text: str, year: int, fuente_ref: str) -> list[dict[str, str]]:
    doc = html.fromstring(text)
    table = doc.xpath('//div[@id="textoxslt"]//table')[0]
    month = 0
    rows: list[dict[str, str]] = []
    for tr in table.xpath(".//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./th|./td")]
        if not cells:
            continue
        first = cells[0].lower()
        if first in MESES:
            month = MESES[first]
            continue
        m = re.match(r"^(\d{1,2})\s+(.+?)\.?$", cells[0])
        if not m or month == 0 or len(cells) < 1 + len(BOE_COLUMNS):
            continue
        day = date(year, month, int(m.group(1)))
        desc = m.group(2).strip()
        marks = cells[1 : 1 + len(BOE_COLUMNS)]
        if all(mark for mark in marks):
            rows.append(
                {
                    "fecha": day.isoformat(),
                    "ambito": "nacional",
                    "ccaa": "",
                    "descripcion": desc,
                    "fuente": "boe",
                    "fuente_ref": fuente_ref,
                }
            )
            continue
        for ccaa, mark in zip(BOE_COLUMNS, marks, strict=True):
            if mark:
                rows.append(
                    {
                        "fecha": day.isoformat(),
                        "ambito": "autonomico",
                        "ccaa": ccaa,
                        "descripcion": desc,
                        "fuente": "boe",
                        "fuente_ref": fuente_ref,
                    }
                )
    return rows


def build_festivos(year: int, source: str) -> int:
    if source.startswith("BOE-A-"):
        text = httpx.get(
            f"https://www.boe.es/buscar/doc.php?id={source}",
            headers={"User-Agent": "IurisIA/0.1 (uso personal)"},
            timeout=60,
        ).text
        ref = source
    else:
        text = Path(source).read_text(encoding="utf-8")
        ref = re.search(r"BOE-A-\d{4}-\d+", text).group(0) if re.search(r"BOE-A-\d{4}-\d+", text) else source
    rows = parse_festivos_html(text, year, ref)
    out = DATA / "festivos" / f"{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["fecha", "ambito", "ccaa", "descripcion", "fuente", "fuente_ref"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    if sys.argv[1] == "municipios":
        print("municipios:", build_municipios(Path(sys.argv[2])))
    elif sys.argv[1] == "festivos":
        print("festivos:", build_festivos(int(sys.argv[2]), sys.argv[3]))
