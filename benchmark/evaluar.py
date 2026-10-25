"""Evaluación automática (sin LLM) de un expediente contra su hoja de verdad.

Comprobaciones: estado esperado, cada cita literal en su fuente, escáner del cortafuegos sobre el texto final sin
hallazgos, artículos clave citados (norma Y artículo), plazos iguales a los del motor, postulación correcta y
ninguna frase prohibida. La «respuesta esperada» (sí/no/depende) la juzga el juez LLM (juez.py) o una persona.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from core.calendar_engine import CalendarEngine
from core.firewall import Contexto, escanear
from core.schemas import ArticuloUE, FragmentoFuente
from core.validators import verify_quote

_REGLAS = CalendarEngine().rules


def _fragmento(sid: str, f: dict[str, Any]) -> FragmentoFuente:
    if sid.startswith("EUR:"):
        _, celex, art = sid.split(":", 2)
        return ArticuloUE(
            source_id=sid,
            titulo=f.get("titulo", ""),
            texto_verbatim=f.get("texto", ""),
            celex=celex,
            articulo=art.removeprefix("art"),
        )
    tipo: Literal["boe", "sentencia", "convenio", "adjunto"] = (
        "boe"
        if sid.startswith("BOE:")
        else "sentencia"
        if sid.startswith("ROJ:")
        else "convenio"
        if sid.startswith("CONV:")
        else "adjunto"
    )
    return FragmentoFuente(source_id=sid, tipo=tipo, titulo=f.get("titulo", ""), texto_verbatim=f.get("texto", ""))


def _textos_finales(final: dict[str, Any]) -> list[str]:
    return [
        final.get("respuesta_directa", ""),
        final.get("resumen_ciudadano", ""),
        *final.get("pasos_inmediatos", []),
        *final.get("fortalezas", []),
        *final.get("riesgos_propios", []),
        *[f["texto"] for f in final.get("fundamentos", [])],
    ]


def evaluar(caso: dict[str, Any], hoja: dict[str, Any] | None, res: dict[str, Any]) -> dict[str, Any]:
    v = caso["verdad"]
    checks: dict[str, dict[str, Any]] = {}
    checks["estado"] = {
        "ok": res.get("estado") == v["estado_esperado"],
        "detalle": f"{res.get('estado')} (esperado {v['estado_esperado']})",
    }
    d = res.get("dictamen") or {}
    final = d.get("dictamen") if isinstance(d.get("dictamen"), dict) else {}
    fuentes = res.get("fuentes") or {}
    if final:
        # 1) citas literales (se vuelven a verificar contra el texto completo de la fuente)
        citas = [c for a in final.get("afirmaciones", []) for c in a.get("citas", [])] + [
            {"source_id": f["source_id"], "verbatim_quote": f["verbatim_quote"]} for f in final.get("fundamentos", [])
        ]
        malas = [
            c
            for c in citas
            if not verify_quote(c["verbatim_quote"], (fuentes.get(c["source_id"]) or {}).get("texto", "")).ok
        ]
        checks["citas_literales"] = {"ok": not malas, "detalle": f"{len(citas) - len(malas)}/{len(citas)} verificadas"}
        # 2) escáner del cortafuegos sobre el texto final
        ctx = Contexto(
            fuentes={sid: _fragmento(sid, f) for sid, f in fuentes.items()},
            hechos=caso["consulta"] + "\n" + "\n".join(a["respuesta"] for a in res.get("aclaraciones", [])),
            hoy=date.fromisoformat(res.get("fecha", date.today().isoformat())),
            referencias_extra=[p["base_legal"] for p in final.get("plazos", [])]
            + [
                (final.get("postulacion") or {}).get("base_legal", ""),
                (final.get("postulacion") or {}).get("texto_usuario", ""),
            ],
            numeros_plazos={
                float(_REGLAS[p["tipo_plazo_id"]].duracion)
                for p in final.get("plazos", [])
                if p["tipo_plazo_id"] in _REGLAS
            },
        )
        hallazgos = [f"{h.motivo}: {h.fragmento}" for t in _textos_finales(final) for h in escanear(t, ctx)]
        checks["escaner"] = {"ok": not hallazgos, "detalle": hallazgos[:8] or "sin hallazgos"}
        # 3) artículos clave citados
        citados = {c["source_id"] for c in citas}
        faltan = []
        for a in (hoja or {}).get("articulos", []):
            prefijo = ":".join(a["source_id"].split(":")[:3])
            if not any(s.startswith(prefijo) for s in citados):
                faltan.append(f"{a['norma']} {a['articulo']}")
        checks["articulos_clave"] = {
            "ok": not faltan,
            "detalle": f"faltan: {', '.join(faltan)}" if faltan else "todos citados",
        }
        # 4) plazos
        obtenidos = {p["tipo_plazo_id"]: p["fecha_limite_segura"] for p in final.get("plazos", [])}
        esperados = {p["tipo"]: p["fecha_limite_segura"] for p in (hoja or {}).get("plazos", [])}
        diferencias = {t: (obtenidos.get(t), f) for t, f in esperados.items() if obtenidos.get(t) != f}
        checks["plazos"] = {"ok": not diferencias, "detalle": diferencias or "coinciden"}
        # 5) postulación
        pe, po = (hoja or {}).get("postulacion"), final.get("postulacion") or {}
        if pe:
            ok = (po.get("requiere_abogado"), po.get("requiere_procurador")) == (
                pe["requiere_abogado"],
                pe["requiere_procurador"],
            )
            checks["postulacion"] = {
                "ok": ok,
                "detalle": f"obtenida {po.get('requiere_abogado')}/{po.get('requiere_procurador')}",
            }
    # 6) frases prohibidas (en todo lo que ve el ciudadano)
    texto = " ".join(_textos_finales(final)) if final else (res.get("mensaje") or "")
    vistas = [p for p in v["prohibido"] if re.search(re.escape(p.lower()), texto.lower())]
    checks["prohibido"] = {"ok": not vistas, "detalle": vistas or "ninguna"}
    aprobadas = sum(1 for c in checks.values() if c["ok"])
    return {"id": caso["id"], "aprobadas": aprobadas, "total": len(checks), "checks": checks}
