"""Arnés de automatización con navegador real (Playwright) para Benchmark Live de Desemppa.

Ejecuta casos de prueba en navegador real contra el servidor local (127.0.0.1:8000)
en Modo Eco (Gemini 3.8 Flash), mide tiempos, captura pantallas de evidencia,
audita la interactividad de la UI (drawer de fuentes, selección de municipios, aclaraciones)
y extrae la telemetría del ledger SQLite.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "benchmark" / "cases_live"
REPORTS_DIR = ROOT / "benchmark" / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
DB_PATH = ROOT / "data" / "local" / "local_cache.db"
BASE_URL = os.environ.get("IURIS_BASE_URL", "http://127.0.0.1:8000")


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH))


def fetch_ledger_calls(con: sqlite3.Connection, consulta_id: str) -> list[dict[str, Any]]:
    rows = con.execute(
        """SELECT id, fase, rol, proveedor, modelo, effort, latencia_ms,
                  input_tokens, output_tokens, coste_equivalente_usd, ok, error_tipo, creado_en
           FROM llm_calls_ledger
           WHERE consulta_id = ?
           ORDER BY id ASC""",
        (consulta_id,),
    ).fetchall()
    calls = []
    for r in rows:
        calls.append(
            {
                "id": r[0],
                "fase": r[1],
                "rol": r[2],
                "proveedor": r[3],
                "modelo": r[4],
                "effort": r[5],
                "latencia_ms": r[6] or 0,
                "input_tokens": r[7] or 0,
                "output_tokens": r[8] or 0,
                "coste_usd": r[9] or 0.0,
                "ok": bool(r[10]),
                "error_tipo": r[11],
                "creado_en": r[12],
            }
        )
    return calls


def launch_browser(p: Any, headless: bool = True) -> Browser:
    # Intenta Chromium descargado por Playwright, o Chrome / Edge del sistema
    errors = []
    for kwargs in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return cast(Browser, p.chromium.launch(headless=headless, **kwargs))
        except Exception as e:
            errors.append(f"{kwargs}: {e}")
    raise RuntimeError(f"No se pudo iniciar ningún navegador Playwright. Errores: {errors}")


def configure_page(context: BrowserContext, modo: str = "eco") -> Page:
    page = context.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    return page


def ensure_eco_mode(page: Page) -> None:
    # Asegura que el modo Eco esté activo mediante localStorage o TopBar
    page.evaluate("() => localStorage.setItem('iuris-modo', 'eco')")
    # Si el botón de modo está visible, verificar su texto
    try:
        btn = page.locator("button[aria-label^='Modo de razonamiento:']")
        if btn.count() > 0 and "Eco" not in (btn.inner_text() or ""):
            btn.click()
            page.wait_for_timeout(300)
            eco_opt = page.locator("role=option[name*='Eco']")
            if eco_opt.count() > 0:
                eco_opt.click()
                page.wait_for_timeout(300)
    except Exception as e:
        print(f"  [aviso modo]: {e}")


def select_municipio(page: Page, municipio_nombre: str) -> bool:
    try:
        # Busca el botón de Municipio
        btn = page.get_by_role("button", name="Municipio")
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(300)

        inp = page.locator("input[aria-label='Municipio']")
        if inp.count() > 0:
            inp.first.fill(municipio_nombre)
            page.wait_for_timeout(800)  # debounce
            # Selecciona la primera opción de la lista
            opciones = page.locator("role=option")
            if opciones.count() > 0:
                opciones.first.click()
                page.wait_for_timeout(300)
                return True
    except Exception as e:
        print(f"  [aviso municipio]: {e}")
    return False


def handle_clarifications(page: Page, aclaraciones: list[dict[str, str]], max_wait_sec: int = 15) -> bool:
    """Detecta si la UI muestra 'Preguntas aclaratorias' y las responde."""
    try:
        sec = page.locator("section[aria-label='Preguntas aclaratorias']")
        if sec.count() == 0 or not sec.is_visible():
            return False

        print("  [aclaraciones] Detectadas preguntas aclaratorias de la IA...")
        labels = sec.locator("label").all()
        for label in labels:
            texto_label = label.inner_text().lower()
            # Buscar respuesta que coincida
            respuesta_texto = "Sí"
            for a in aclaraciones:
                if a.get("pregunta_contiene", "").lower() in texto_label:
                    respuesta_texto = a["respuesta"]
                    break

            # Determinar tipo de control
            inp_date = label.locator("input[type='date']")
            inp_num = label.locator("input[type='number']")
            inp_text = label.locator("input[type='text'], input:not([type])")
            btn_si = label.locator("button:has-text('Sí')")
            select = label.locator("select")

            if inp_date.count() > 0 and inp_date.is_visible():
                import re

                m = re.search(r"\d{4}-\d{2}-\d{2}", respuesta_texto)
                val_date = m.group(0) if m else "2026-09-30"
                inp_date.fill(val_date)
            elif inp_num.count() > 0 and inp_num.is_visible():
                import re

                m = re.search(r"\d+", respuesta_texto)
                val_num = m.group(0) if m else "100"
                inp_num.fill(val_num)
            elif inp_text.count() > 0 and inp_text.is_visible():
                inp_text.fill(respuesta_texto)
            elif btn_si.count() > 0 and btn_si.is_visible():
                if "no" in respuesta_texto.lower():
                    label.locator("button:has-text('No')").click()
                else:
                    btn_si.click()
            elif select.count() > 0 and select.is_visible():
                select.select_option(index=1)

        page.wait_for_timeout(400)
        btn_cont = sec.get_by_role("button", name="Continuar")
        if btn_cont.count() > 0 and btn_cont.is_enabled():
            btn_cont.click()
            print("  [aclaraciones] Respuestas enviadas con éxito.")
            return True
    except Exception as e:
        print(f"  [aviso aclaraciones]: {e}")
    return False


def run_single_case(
    page: Page,
    case_path: Path,
    screenshots_dir: Path,
    timeout_sec: int = 240,
) -> dict[str, Any]:
    with open(case_path, encoding="utf-8") as f:
        case_data = json.load(f)

    case_id = case_data.get("id", case_path.stem)
    print("\n=======================================================")
    print(f"EJECUTANDO: {case_id} — {case_data.get('titulo', '')}")
    print(f"Materia esperada: {case_data.get('materia_esperada')}")
    print("=======================================================")

    result: dict[str, Any] = {
        "case_id": case_id,
        "titulo": case_data.get("titulo"),
        "tipo": case_data.get("tipo"),
        "materia_esperada": case_data.get("materia_esperada"),
        "consulta": case_data.get("consulta"),
        "municipio": case_data.get("municipio_nombre"),
        "t_inicio": time.time(),
        "t_fin": 0.0,
        "duracion_total_s": 0.0,
        "estado_final": "TIMEOUT",
        "consulta_id": None,
        "aclaraciones_requeridas": False,
        "drawer_interactivo_ok": False,
        "screenshot_path": None,
        "screenshot_drawer_path": None,
        "dictamen": None,
        "evaluacion": {},
        "ledger_calls": [],
        "ledger_resumen": {},
        "errores": [],
    }

    # Interceptar peticiones para capturar consulta_id
    consulta_ids_capturados: list[str] = []

    def on_response(response: Any) -> None:
        if "/api/consultas" in response.url and response.request.method == "POST":
            try:
                data = response.json()
                if "consulta_id" in data:
                    consulta_ids_capturados.append(data["consulta_id"])
            except Exception:
                pass

    page.on("response", on_response)

    # 1. Navegar a la página de inicio
    t0 = time.time()
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_timeout(500)

    # 2. Configurar modo Eco
    ensure_eco_mode(page)

    # 3. Rellenar municipio si aplica
    if case_data.get("municipio_nombre"):
        select_municipio(page, case_data["municipio_nombre"])

    # 4. Escribir la consulta
    textarea = page.get_by_label("Describe tu caso")
    textarea.fill(case_data["consulta"])
    page.wait_for_timeout(300)

    # 5. Enviar consulta
    btn_analizar = page.get_by_role("button", name="Analizar")
    btn_analizar.click()
    print("  [1/5] Consulta enviada. Esperando pipeline de razonamiento...")

    # 6. Monitoreo del pipeline con bucle reactivo
    deadline = time.time() + timeout_sec
    dictamen_encontrado = False

    while time.time() < deadline:
        page.wait_for_timeout(1000)

        # Detectar aclaraciones
        if not result["aclaraciones_requeridas"]:
            sec_aclar = page.locator("section[aria-label='Preguntas aclaratorias']")
            if sec_aclar.count() > 0 and sec_aclar.is_visible():
                if handle_clarifications(page, case_data.get("aclaraciones_simuladas", [])):
                    result["aclaraciones_requeridas"] = True

        # Detectar si hay dictamen o resultado final
        dictamen_elem = page.locator("article[aria-label='Dictamen']")
        resultado_elem = page.locator("section[aria-label='Resultado']")
        fundamentos_elem = page.locator("section[aria-label='Fundamentos verificados']")

        if dictamen_elem.count() > 0 and dictamen_elem.is_visible():
            result["estado_final"] = "CERTIFICADA"
            dictamen_encontrado = True
            break
        elif resultado_elem.count() > 0 and resultado_elem.is_visible():
            # Caso bloqueado o fuera de alcance
            texto_res = resultado_elem.inner_text()
            if "bloqueada" in texto_res.lower() or "no puedo darte" in texto_res.lower():
                result["estado_final"] = "BLOQUEADA"
            else:
                result["estado_final"] = "FUERA_DE_ALCANCE"
            dictamen_encontrado = True
            break
        elif fundamentos_elem.count() > 0 and fundamentos_elem.is_visible():
            result["estado_final"] = "CERTIFICADA"
            dictamen_encontrado = True
            break

    t1 = time.time()
    result["t_fin"] = t1
    result["duracion_total_s"] = round(t1 - t0, 2)
    print(f"  [2/5] Pipeline finalizado en {result['duracion_total_s']}s con estado: {result['estado_final']}")

    if not dictamen_encontrado:
        print("  [ERROR] Timeout alcanzado sin dictamen final.")
        result["errores"].append("Timeout alcanzado sin dictamen final.")

    # Guardar ID de consulta
    if consulta_ids_capturados:
        result["consulta_id"] = consulta_ids_capturados[-1]

    # 7. Probar interactividad de la UI: abrir drawer de fuentes
    try:
        citas = page.locator("button[aria-label*='Abrir fuente']")
        if citas.count() > 0:
            print(f"  [3/5] Probando apertura del Drawer de Fuentes ({citas.count()} citas disponibles)...")
            citas.first.click()
            page.wait_for_timeout(800)

            # Verificar que el SourceViewer se ha abierto
            viewer = page.locator("aside[aria-label='Visor de fuentes'], aside")
            if viewer.count() > 0:
                result["drawer_interactivo_ok"] = True
                print("  [3/5] -> Drawer de fuentes abierto y verificado correctamente.")

            # Pantallazo con el drawer abierto
            shot_drawer = screenshots_dir / f"{case_id}_drawer.png"
            page.screenshot(path=str(shot_drawer), full_page=True)
            result["screenshot_drawer_path"] = str(shot_drawer)
    except Exception as e:
        print(f"  [aviso drawer]: {e}")
        result["errores"].append(f"Fallo interactividad drawer: {e}")

    # Pantallazo general del resultado
    shot_main = screenshots_dir / f"{case_id}.png"
    page.screenshot(path=str(shot_main), full_page=True)
    result["screenshot_path"] = str(shot_main)
    print(f"  [4/5] Pantallazo guardado en: {shot_main.name}")

    # 8. Extraer datos estructurados de la API si tenemos consulta_id
    if result["consulta_id"]:
        try:
            api_data = page.evaluate(f"() => fetch('/api/consultas/{result['consulta_id']}').then(r => r.json())")
            result["dictamen_completo"] = api_data
        except Exception as e:
            print(f"  [aviso api datos]: {e}")

    # 9. Consultar el ledger SQLite para auditoría de tokens y latencias reales
    try:
        con = get_db_connection()
        if result["consulta_id"]:
            calls = fetch_ledger_calls(con, result["consulta_id"])
            result["ledger_calls"] = calls
            total_in = sum(c["input_tokens"] for c in calls)
            total_out = sum(c["output_tokens"] for c in calls)
            total_lat = sum(c["latencia_ms"] for c in calls)
            result["ledger_resumen"] = {
                "total_llamadas": len(calls),
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_tokens": total_in + total_out,
                "latencia_acumulada_ms": total_lat,
                "modelos": list({c["modelo"] for c in calls}),
            }
            print(f"  [5/5] Ledger auditado: {len(calls)} llamadas LLM, {total_in + total_out} tokens totales.")
        con.close()
    except Exception as e:
        print(f"  [aviso sqlite ledger]: {e}")
        result["errores"].append(f"Fallo ledger: {e}")

    # 10. Auditoría Jurídica Automatizada contra criterios del caso
    crit = case_data.get("criterios_evaluacion", {})
    eval_juridica: dict[str, Any] = {
        "estimacion_esperada": crit.get("estimacion_principal"),
        "estimacion_obtenida": None,
        "estimacion_coincide": False,
        "normas_verificadas": [],
        "postulacion_coincide": False,
        "postulacion_esperada": crit.get("postulacion_esperada"),
        "postulacion_obtenida": None,
        "score_calidad": 0.0,
    }

    if result.get("dictamen_completo"):
        d_comp = result["dictamen_completo"]
        dictamen_obj: dict[str, Any] = d_comp.get("dictamen") or {}
        inner_dict = dictamen_obj.get("dictamen")
        dictamen: dict[str, Any] = inner_dict if isinstance(inner_dict, dict) else dictamen_obj
        debate_obj: dict[str, Any] = d_comp.get("debate") or {}
        inner_mag = debate_obj.get("magistrado")
        resolucion: dict[str, Any] = inner_mag if isinstance(inner_mag, dict) else (d_comp.get("resolucion") or {})
        post: dict[str, Any] = dictamen.get("postulacion") or d_comp.get("postulacion") or {}

        # Estimación
        cuestiones = resolucion.get("cuestiones", [])
        if cuestiones:
            est = cuestiones[0].get("estimacion")
            eval_juridica["estimacion_obtenida"] = est
            eval_juridica["estimacion_coincide"] = est == crit.get("estimacion_principal")

        # Postulación
        req_abog = post.get("requiere_abogado")
        req_proc = post.get("requiere_procurador")
        post_esp = crit.get("postulacion_esperada", {})
        eval_juridica["postulacion_obtenida"] = {
            "abogado_obligatorio": req_abog,
            "procurador_obligatorio": req_proc,
            "base_legal": post.get("base_legal"),
        }
        if post_esp:
            eval_juridica["postulacion_coincide"] = req_abog == post_esp.get(
                "abogado_obligatorio"
            ) and req_proc == post_esp.get("procurador_obligatorio")

        # Normas requeridas citadas
        fundamentos = dictamen.get("fundamentos", [])
        source_ids = [f.get("source_id", "") for f in fundamentos]
        for n_req in crit.get("normas_requeridas", []):
            req_id = n_req.get("id", "")
            req_art = str(n_req.get("articulo", ""))
            # Norma Y artículo: el bloque del BOE puede ser a36, art36 o a12121 (para 121-21); en la UE, art7.
            bloques = {f"a{req_art}", f"art{req_art}", f"a{req_art.replace('-', '')}"}
            encontrado = any(req_id in sid and any(f":{b}:" in f"{sid}:" for b in bloques) for sid in source_ids)
            eval_juridica["normas_verificadas"].append(
                {
                    "norma": req_id,
                    "articulo": req_art,
                    "descripcion": n_req.get("descripcion"),
                    "encontrado": encontrado,
                }
            )

        # Puntuación global del caso (0 a 10)
        # Puntuación automática (0-10) SOLO de lo comprobable por máquina; los `puntos_clave` del caso se
        # revisan a mano (ver «Lista de comprobación manual» en el informe).
        score = 0.0
        if result["estado_final"] == "CERTIFICADA":
            normas_ok = sum(1 for n in eval_juridica["normas_verificadas"] if n["encontrado"])
            total_normas = max(1, len(eval_juridica["normas_verificadas"]))
            esperada = crit.get("estimacion_principal")
            if esperada:
                score += 4.0 if eval_juridica["estimacion_coincide"] else 0.0
                score += 2.0 if eval_juridica["postulacion_coincide"] else 0.0
                score += 4.0 * (normas_ok / total_normas)
            else:  # caso de decisión sin parte «ganadora» esperada: se reparte entre postulación y normas
                score += 4.0 if eval_juridica["postulacion_coincide"] else 0.0
                score += 6.0 * (normas_ok / total_normas)
        eval_juridica["score_calidad"] = round(score, 1)
        eval_juridica["puntos_clave"] = crit.get("puntos_clave", [])

    result["evaluacion"] = eval_juridica
    print(f"  Calidad jurídica estimada: {eval_juridica['score_calidad']}/10.0")

    return result


def generate_benchmark_reports(
    results: list[dict[str, Any]],
    timestamp_str: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"benchmark_38_flash_{timestamp_str}.json"
    md_path = output_dir / f"benchmark_38_flash_{timestamp_str}.md"

    # Guardar JSON completo
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Calcular estadísticas globales
    total_casos = len(results)
    certificadas = sum(1 for r in results if r["estado_final"] == "CERTIFICADA")
    timeouts = sum(1 for r in results if r["estado_final"] == "TIMEOUT")
    duracion_media = sum(r["duracion_total_s"] for r in results) / max(1, total_casos)
    score_medio = sum(r["evaluacion"].get("score_calidad", 0.0) for r in results) / max(1, total_casos)
    total_tokens = sum(r.get("ledger_resumen", {}).get("total_tokens", 0) for r in results)
    drawer_ok = sum(1 for r in results if r.get("drawer_interactivo_ok"))

    # Generar Markdown estructurado
    lines: list[str] = [
        f"# Informe de Benchmark en Modo Eco: Gemini 3.8 Flash ({timestamp_str})",
        "",
        "> Ejecución automática con navegador real (Playwright). Este informe solo contiene datos medidos: la",
        "> «calidad jurídica» automática comprueba estimación, postulación y normas citadas (norma y artículo);",
        "> la corrección de fondo se revisa a mano con la lista de comprobación de cada caso.",
        "",
        "## 1. Métricas Clave Globales",
        "",
        "| Métrica | Valor Obtenido | Objetivo de Calidad |",
        "| :--- | :--- | :--- |",
        f"| **Casos Totales Evaluados** | **{total_casos}** (4 típicos + 4 raros) | 8 casos representativos |",
        (
            f"| **Tasa de Certificación Exitosa** | "
            f"**{certificadas}/{total_casos} ({certificadas / max(1, total_casos) * 100:.1f} %)** | "
            r"$\ge 85\%$ sin errores fatales |"
        ),
        rf"| **Tiempo Medio de Respuesta E2E** | **{duracion_media:.1f} s** por consulta | $\le 90$ s en Modo Eco |",
        rf"| **Puntuación automática media** | **{score_medio:.1f} / 10.0** | no sustituye la revisión manual |",
        (
            f"| **Interactividad Drawer Fuentes** | "
            f"**{drawer_ok}/{total_casos} ({drawer_ok / max(1, total_casos) * 100:.1f} %)** | "
            "100 % apertura con resaltado |"
        ),
        (
            f"| **Consumo Total de Tokens** | **{total_tokens:,} tokens** (0 € extra, Google AI Pro) | "
            "Cuota plana suscripción |"
        ),
        f"| **Timeouts / Fallos de Red** | **{timeouts}** | 0 cuelgues o timeouts |",
        "",
        "---",
        "",
        "## 2. Resumen Detallado por Caso de Prueba",
        "",
        "| ID | Caso | Tipo | Estado | Duración | Calidad Jurídica | Estimación | Postulación | Drawer |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        ev = r.get("evaluacion", {})
        est_icon = "✅" if ev.get("estimacion_coincide") else "❌"
        post_icon = "✅" if ev.get("postulacion_coincide") else "⚠️"
        draw_icon = "✅" if r.get("drawer_interactivo_ok") else "❌"
        line_item = (
            f"| `{r['case_id']}` | **{r.get('titulo', '')}** | {r.get('tipo', '')} | `{r['estado_final']}` | "
            f"{r['duracion_total_s']}s | **{ev.get('score_calidad', 0.0)}/10** | "
            f"{est_icon} `{ev.get('estimacion_obtenida')}` | {post_icon} | {draw_icon} |"
        )
        lines.append(line_item)

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Evidencias Gráficas (Screenshots E2E)",
            "",
        ]
    )

    lines.extend(["## 3. Lista de comprobación manual (puntos clave de cada caso)", ""])
    for r in results:
        ev = r.get("evaluacion", {})
        dic = (r.get("dictamen_completo") or {}).get("dictamen") or {}
        dic = dic.get("dictamen", dic) if isinstance(dic, dict) else {}
        lines.append(f"### `{r['case_id']}` · {r.get('titulo')}")
        if dic.get("respuesta_directa"):
            lines.append(f"> {dic['respuesta_directa']}")
        degradado = sum(1 for a in dic.get("avisos", []) if "no disponible" in a)
        if degradado:
            lines.append(f"- ⚠️ {degradado} paso(s) usaron el modelo alternativo")
        for n in ev.get("normas_verificadas", []):
            lines.append(f"- {'✅' if n['encontrado'] else '❌'} cita {n['norma']} art. {n['articulo']}")
        for punto in ev.get("puntos_clave", []):
            lines.append(f"- [ ] {punto}")
        lines.append("")
    lines.extend(["## 4. Capturas", ""])
    for r in results:
        case_id = r["case_id"]
        lines.append(f"### Caso `{case_id}`: {r.get('titulo')}")
        lines.append(
            f"- **Materia:** `{r.get('materia_esperada')}` | **Duración:** {r['duracion_total_s']} s | "
            f"**Puntuación:** {r['evaluacion'].get('score_calidad', 0.0)}/10"
        )
        if r.get("screenshot_path"):
            shot_rel = Path(r["screenshot_path"]).name
            lines.append(f"- Vista Dictamen: `benchmark/reports/screenshots/{shot_rel}`")
        if r.get("screenshot_drawer_path"):
            shot_d_rel = Path(r["screenshot_drawer_path"]).name
            lines.append(f"- Vista Drawer Fuentes: `benchmark/reports/screenshots/{shot_d_rel}`")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Browser Runner para Benchmark Live de Desemppa")
    parser.add_argument("--modo", default="eco", help="Modo de ejecución (eco, equilibrado, pro)")
    parser.add_argument("--case", default=None, help="ID o nombre de fichero de un caso específico")
    parser.add_argument("--no-headless", action="store_true", help="Ejecutar mostrando el navegador en pantalla")
    parser.add_argument("--timeout", type=int, default=240, help="Timeout por caso en segundos")
    args = parser.parse_args()

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Identificar casos a ejecutar
    case_files = sorted(CASES_DIR.glob("*.json"))
    if args.case:
        case_files = [
            c for c in case_files if args.case.lower() in c.name.lower() or args.case.lower() in c.stem.lower()
        ]

    if not case_files:
        print(f"No se encontraron casos en {CASES_DIR} coincidentes con {args.case}")
        sys.exit(1)

    print(f"Iniciando Benchmark Live con {len(case_files)} caso(s) en Modo '{args.modo}'...")
    print(f"Servidor destino: {BASE_URL}")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    results = []

    with sync_playwright() as p:
        browser = launch_browser(p, headless=not args.no_headless)
        context = browser.new_context()

        for c_file in case_files:
            page = configure_page(context, modo=args.modo)
            try:
                res = run_single_case(page, c_file, SCREENSHOTS_DIR, timeout_sec=args.timeout)
                results.append(res)
            except Exception as e:
                print(f"[FATAL] Error ejecutando caso {c_file.name}: {e}")
                results.append(
                    {
                        "case_id": c_file.stem,
                        "estado_final": "ERROR_FATAL",
                        "errores": [str(e)],
                        "duracion_total_s": 0.0,
                        "evaluacion": {"score_calidad": 0.0},
                    }
                )
            finally:
                page.close()

        context.close()
        browser.close()

    # Generar informes
    json_path, md_path = generate_benchmark_reports(results, timestamp_str, REPORTS_DIR)
    print("\n=======================================================")
    print("BENCHMARK FINALIZADO CON ÉXITO")
    print(f"Informe JSON: {json_path}")
    print(f"Informe MD:   {md_path}")
    print("=======================================================")


if __name__ == "__main__":
    main()
