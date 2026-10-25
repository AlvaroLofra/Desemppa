"""Expediente verificable de un caso: todo lo necesario para que una persona o cualquier LLM compruebe el resultado
SIN acceso a la app (consulta, respuesta, cada afirmación con su cita literal y el texto completo de la fuente,
razonamiento del Magistrado, alegatos, plazos, postulación, auditoría del cortafuegos y hoja de verdad)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _linea_cita(c: dict[str, Any]) -> str:
    return f"  - `{c['source_id']}`: «{c['verbatim_quote']}»"


def expediente_md(caso: dict[str, Any], hoja: dict[str, Any] | None, res: dict[str, Any]) -> str:
    d = res.get("dictamen") or {}
    final = d.get("dictamen") if isinstance(d.get("dictamen"), dict) else d
    debate = res.get("debate") or {}
    L: list[str] = [f"# Expediente {caso['id']} · {caso['categoria']} · {caso['materia_esperada']}", ""]
    L += ["## 1. Consulta", "", f"> {caso['consulta']}", ""]
    if res.get("aclaraciones"):
        L += [
            "**Aclaraciones respondidas:**",
            *[f"- {a['pregunta']} → {a['respuesta']}" for a in res["aclaraciones"]],
            "",
        ]
    L += [
        f"**Estado final:** {res.get('estado')} · **duración:** {res.get('duracion_s')} s · "
        f"**modo:** {res.get('modo')}",
        "",
    ]
    if final:
        L += ["## 2. Respuesta", "", f"**Respuesta directa:** {final.get('respuesta_directa', '')}", ""]
        if final.get("respuesta_parcial"):
            L += ["*(respuesta parcial: la respuesta directa no superó la verificación)*", ""]
        L += [f"**Solidez:** {final.get('banda_solidez')}", "", "### Afirmaciones mostradas (tras el cortafuegos)", ""]
        for a in final.get("afirmaciones", []):
            L.append(f"- [{a['seccion']} · {a['tipo']}] {a['texto']}")
            L += [_linea_cita(c) for c in a.get("citas", [])]
        L += ["", "### Fundamentos verificados", ""]
        for f in final.get("fundamentos", []):
            L += [f"- {f['texto']} (coincidencia {f['fuzzy_score']:.0f} %, NLI {f['nli']})", _linea_cita(f)]
        L += ["", "### Plazos (motor determinista)", ""]
        for p in final.get("plazos", []):
            L.append(
                f"- {p['tipo_plazo_id']}: desde {p['fecha_inicio']} hasta {p['fecha_limite_segura']} "
                f"({p['base_legal']})"
            )
        post = final.get("postulacion") or {}
        if post:
            L += [
                "",
                "### Postulación",
                "",
                f"- Abogado: {post.get('requiere_abogado')} · procurador: "
                f"{post.get('requiere_procurador')} ({post.get('base_legal')})",
                f"- {post.get('texto_usuario', '')}",
            ]
        L += ["", "### Avisos", "", *[f"- {a}" for a in final.get("avisos", [])], ""]
    elif res.get("mensaje"):
        L += ["## 2. Resultado", "", res["mensaje"], ""]
    mag = (debate or {}).get("magistrado") or {}
    if mag:
        L += ["## 3. Razonamiento del Magistrado", ""]
        for q in mag.get("cuestiones", []):
            L.append(f"### {q['id']}: {q['enunciado']} → estima **{q['estimacion']}**")
            for f in q.get("fundamentos", []):
                L.append(f"- {f['afirmacion']}")
                L += [_linea_cita(c) for c in f.get("citas", [])]
            L.append("")
        L += [f"Banda propuesta: {mag.get('banda_propuesta')} — {mag.get('razonamiento_banda', '')}", ""]
    for rol in ("defensa", "contraparte"):
        al = (debate or {}).get(rol) or {}
        if al:
            L += [f"## Alegato de {rol}", "", f"Pretensión: {al.get('pretension', '')}", ""]
            for q in al.get("cuestiones", []):
                for a in q.get("argumentos", []):
                    L.append(f"- ({q['id']}) {a['afirmacion']}")
            L.append("")
    if final and final.get("auditoria"):
        L += [
            "## 4. Auditoría del cortafuegos",
            "",
            "| Resultado | Sección | Tipo | Afirmación | Motivos |",
            "|---|---|---|---|---|",
        ]
        for e in final["auditoria"]:
            tipo = e["tipo_propuesto"] + (
                f" → {e['tipo_final']}" if e.get("tipo_final") not in (None, e["tipo_propuesto"]) else ""
            )
            texto = e["texto"].replace("|", "/")
            motivos = "; ".join(e["motivos"]).replace("|", "/")
            L.append(f"| {e['resultado']} | {e['seccion']} | {tipo} | {texto} | {motivos} |")
        L.append("")
    L += ["## 5. Texto completo de las fuentes citadas", ""]
    for sid, f in (res.get("fuentes") or {}).items():
        L += [
            f"### `{sid}` — {f.get('titulo', '')}",
            f"URL oficial: {f.get('url') or '—'}",
            "",
            "```text",
            f.get("texto", ""),
            "```",
            "",
        ]
    if hoja:
        v = caso["verdad"]
        L += [
            "## 6. Hoja de verdad (verificada contra la fuente oficial)",
            "",
            f"- Estado esperado: {v['estado_esperado']}",
            f"- Respuesta esperada: **{v['respuesta_esperada']}**",
            *[f"- Punto clave: {p}" for p in v["puntos_clave"]],
            *[f"- Prohibido decir: «{p}»" for p in v["prohibido"]],
        ]
        for p in hoja.get("plazos", []):
            L.append(f"- Plazo esperado {p['tipo']}: {p['inicio']} → {p['fecha_limite_segura']} ({p['base_legal']})")
        if hoja.get("postulacion"):
            pe = hoja["postulacion"]
            L.append(
                f"- Postulación esperada: abogado {pe['requiere_abogado']}, procurador {pe['requiere_procurador']}"
            )
        L.append("")
        for a in hoja.get("articulos", []):
            L += [
                f"### Artículo clave {a['norma']} {a['articulo']} (versión {a['version']}, sha256 {a['sha256'][:16]}…)",
                a["url"],
                "",
                "```text",
                a["texto"],
                "```",
                "",
            ]
    return "\n".join(L)


def guardar(directorio: Path, caso: dict[str, Any], hoja: dict[str, Any] | None, res: dict[str, Any]) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "expediente.json").write_text(
        json.dumps({"caso": caso, "hoja": hoja, "resultado": res}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (directorio / "expediente.md").write_text(expediente_md(caso, hoja, res), encoding="utf-8")
