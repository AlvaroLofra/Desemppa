"""Dictamen en Word (.docx): el mismo contenido VERIFICADO que se ve en pantalla, con formato de informe.

Solo se usa lo que ya pasó el cortafuegos (afirmaciones aceptadas, fundamentos con cita literal, plazos del motor
determinista, sello SHA-256). Las afirmaciones eliminadas van aparte, en un anexo de auditoría claramente marcado.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from core.schemas import AVISO_LEGAL, BANDA_TEXTO, BandaSolidez

_GRIS = RGBColor(0x5F, 0x5B, 0x55)
_NATURALEZA = {
    "caducidad": "Caducidad: si vence sin actuar, se pierde el derecho",
    "prescripcion": "Prescripción: una reclamación formal puede reiniciar el plazo",
    "procesal": "Plazo procesal",
    "administrativo": "Plazo administrativo",
    "sustantivo": "Plazo legal",
}


def _fecha(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _nota(doc: Any, texto: str) -> None:
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.font.size = Pt(9)
    r.font.color.rgb = _GRIS


def _cita(doc: Any, quote: str, fuente: str) -> None:
    p = doc.add_paragraph(style="Quote")
    r = p.add_run(f"«{quote}»")
    r.italic = True
    r.font.name = "Cambria"
    p.add_run(f"  ({fuente})").font.size = Pt(8)


def _lista(doc: Any, items: list[str], *, numerada: bool = False) -> None:
    for it in items:
        doc.add_paragraph(it, style="List Number" if numerada else "List Bullet")


def _tabla(doc: Any, cabecera: list[str], filas: list[list[str]]) -> None:
    t = doc.add_table(rows=1, cols=len(cabecera))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for celda, texto in zip(t.rows[0].cells, cabecera, strict=True):
        celda.text = texto
        for r in celda.paragraphs[0].runs:
            r.bold = True
    for fila in filas:
        celdas = t.add_row().cells
        for celda, texto in zip(celdas, fila, strict=True):
            celda.text = texto


def _plazos(doc: Any, plazos: list[dict[str, Any]]) -> None:
    if not plazos:
        return
    doc.add_heading("Plazos", level=2)
    _tabla(
        doc,
        ["Plazo", "Fecha límite segura", "Naturaleza", "Base legal"],
        [
            [
                p.get("descripcion", "") + (" (de la otra parte)" if p.get("titular") == "contraparte" else ""),
                _fecha(p.get("fecha_limite_segura")),
                _NATURALEZA.get(str(p.get("naturaleza")), str(p.get("naturaleza", ""))),
                str(p.get("base_legal", "")),
            ]
            for p in plazos
        ],
    )
    _nota(
        doc,
        "Calculado por el motor determinista de plazos (sin modelos de lenguaje), pendiente de validación jurídica. "
        "No apures el plazo: la fecha indicada es la segura.",
    )


def _postulacion(doc: Any, post: dict[str, Any] | None) -> None:
    if not post:
        return
    doc.add_heading("Abogado y procurador", level=2)
    doc.add_paragraph(str(post.get("texto_usuario", "")))
    _nota(doc, str(post.get("base_legal", "")))


def dictamen_docx(consulta: dict[str, Any]) -> bytes:
    """`consulta`: lo que devuelve `GET /api/consultas/{id}` (texto, triage, debate y dictamen final)."""
    final = consulta.get("dictamen") or {}
    d: dict[str, Any] = final.get("dictamen") or {}
    triage = consulta.get("triage") or {}
    doc: Any = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    titulo = doc.add_heading("Dictamen de orientación jurídica", level=0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    materia = triage.get("submateria_descripcion") or triage.get("submateria_principal") or ""
    _nota(
        doc,
        f"Desemppa · generado el {datetime.now():%d/%m/%Y %H:%M}"
        + (f" · {materia}" if materia else "")
        + (f" · hechos del {_fecha(triage.get('fecha_hechos'))}" if triage.get("fecha_hechos") else ""),
    )
    doc.add_heading("Consulta", level=1)
    doc.add_paragraph(str(consulta.get("texto") or ""))

    if final.get("estado") != "CERTIFICADA" or not d:
        doc.add_heading("Resultado", level=1)
        doc.add_paragraph(str(final.get("mensaje") or "La consulta no tiene un dictamen certificado."))
        _plazos(doc, list(final.get("plazos") or []))
        _postulacion(doc, final.get("postulacion"))
        if final.get("avisos"):
            doc.add_heading("Avisos", level=2)
            _lista(doc, [str(a) for a in final["avisos"]])
        _nota(doc, str(final.get("aviso_legal") or AVISO_LEGAL))
        return _bytes(doc)

    doc.add_heading("Respuesta", level=1)
    resp = doc.add_paragraph()
    resp.add_run(str(d.get("respuesta_directa") or "")).bold = True
    banda = d.get("banda_solidez")
    if banda in {b.value for b in BandaSolidez}:
        p = doc.add_paragraph()
        p.add_run("Solidez de la posición: ").bold = True
        p.add_run(BANDA_TEXTO[BandaSolidez(banda)] + " (no es una probabilidad de ganar).")
        _lista(doc, [str(m) for m in d.get("motivos_banda") or []])
    if d.get("resumen_ciudadano"):
        doc.add_paragraph(str(d["resumen_ciudadano"]))

    cuestiones = d.get("cuestiones") or []
    if cuestiones:
        doc.add_heading("Cuestiones y decisión", level=1)
        for q in cuestiones:
            parte = "tu posición" if q.get("estimacion") == "DEFENSA" else "la otra parte"
            p = doc.add_paragraph()
            p.add_run(f"{q.get('id', '')}. {q.get('enunciado', '')}").bold = True
            p.add_run(f" — da la razón a {parte}.")
            for f in q.get("fundamentos") or []:
                doc.add_paragraph(str(f.get("afirmacion", "")), style="List Bullet")
                for c in f.get("citas") or []:
                    _cita(doc, str(c.get("verbatim_quote", "")), str(c.get("source_id", "")))

    debate = consulta.get("debate") or {}
    if debate.get("defensa") or debate.get("contraparte"):
        doc.add_heading("Argumentos de las partes", level=1)
        for rol, nombre in (("defensa", "A tu favor (defensa)"), ("contraparte", "De la otra parte")):
            al = debate.get(rol) or {}
            args = [a.get("afirmacion", "") for q in al.get("cuestiones") or [] for a in q.get("argumentos") or []]
            if args:
                doc.add_heading(nombre, level=3)
                _lista(doc, [str(a) for a in args])
        _nota(doc, "Los argumentos de las partes son el debate previo; lo que vale es la decisión y lo verificado.")

    for clave, rotulo, numerada in (
        ("pasos_inmediatos", "Qué hacer ahora", True),
        ("fortalezas", "A tu favor", False),
        ("riesgos_propios", "Puntos débiles", False),
    ):
        if d.get(clave):
            doc.add_heading(rotulo, level=2)
            _lista(doc, [str(x) for x in d[clave]], numerada=numerada)

    _plazos(doc, list(d.get("plazos") or []))
    _postulacion(doc, d.get("postulacion"))

    if d.get("fundamentos"):
        doc.add_heading("Fundamentos verificados", level=1)
        for i, f in enumerate(d["fundamentos"], start=1):
            doc.add_paragraph(f"[{i}] {f.get('texto', '')}")
            _cita(doc, str(f.get("verbatim_quote", "")), str(f.get("source_id", "")))
    if d.get("hechos_determinantes"):
        doc.add_heading("Lo que podría cambiar el resultado", level=2)
        _lista(doc, [str(h) for h in d["hechos_determinantes"]])
    if d.get("avisos"):
        doc.add_heading("Avisos", level=2)
        _lista(doc, [str(a) for a in d["avisos"]])

    sello = d.get("sello") or {}
    if sello.get("fuentes"):
        doc.add_heading("Sello de verificación", level=1)
        doc.add_paragraph(
            f"Verificado el {_fecha(sello.get('verificado_en'))}: {sello.get('afirmaciones_mostradas', 0)} "
            f"afirmaciones mostradas y {sello.get('afirmaciones_eliminadas', 0)} eliminadas por no estar verificadas."
        )
        _tabla(
            doc,
            ["Fuente", "Redacción vigente desde", "SHA-256 del texto verificado"],
            [
                [str(f.get("titulo", "")), str(f.get("version") or ""), str(f.get("sha256", ""))]
                for f in sello["fuentes"]
            ],
        )
        _nota(
            doc,
            "Cualquiera puede descargar el texto oficial, calcular su SHA-256 y comprobar que las citas salen de ese "
            "texto exacto.",
        )

    modelos = d.get("modelos_usados") or {}
    _nota(doc, str(d.get("aviso_legal") or AVISO_LEGAL))
    if modelos:
        _nota(doc, "Modelos usados: " + ", ".join(f"{r} {m}" for r, m in modelos.items()))

    eliminadas = [e for e in d.get("auditoria") or [] if e.get("resultado") == "eliminada"]
    if eliminadas:
        doc.add_page_break()
        doc.add_heading("Anexo · Afirmaciones descartadas por el cortafuegos", level=1)
        _nota(doc, "NO forman parte del dictamen: se muestran solo por transparencia, con el motivo del descarte.")
        _tabla(
            doc,
            ["Afirmación descartada", "Motivo"],
            [[str(e.get("texto", "")), "; ".join(str(m) for m in e.get("motivos") or [])] for e in eliminadas],
        )
    return _bytes(doc)


def _bytes(doc: Any) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
