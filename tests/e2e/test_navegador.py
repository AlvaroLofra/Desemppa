"""E2E con navegador real (Chromium) contra el servidor real con service worker activo.

Reproduce lo que fallaba al usuario: reinicio del servidor con un token distinto mientras la pestaña sigue abierta,
recarga, y copia antigua de la interfaz. LLM y BOE simulados (tests/e2e/fake_server.py), sin consumir cuota.

  uv run pytest -m e2e -v
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]
ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "web" / "dist"
CONSULTA = (
    "Entregué las llaves el 1 de junio de 2026 y el casero no me devuelve la fianza de 900 euros porque dice que "
    "tiene que pintar el piso."
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Server:
    def __init__(self, data_dir: Path, dist: Path) -> None:
        self.port = _free_port()
        self.data_dir = data_dir
        self.dist = dist
        self.proc: subprocess.Popen[bytes] | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = {
            **os.environ,
            "IURIS_DATA_DIR": str(self.data_dir),
            "IURIS_WEB_DIST": str(self.dist),
            "GEMINI_API_KEY": "",
        }
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "tests" / "e2e" / "fake_server.py"), str(self.port)], cwd=ROOT, env=env
        )
        for _ in range(100):
            try:
                if httpx.get(f"{self.url}/api/version", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("el servidor de pruebas no arrancó")

    def stop(self) -> None:
        if self.proc is not None:
            self.proc.terminate()
            self.proc.wait(timeout=20)
            self.proc = None

    def rotate_token(self) -> None:
        """Simula el escenario del fallo: el servidor vuelve con un token distinto."""
        (self.data_dir / "local_token.txt").unlink(missing_ok=True)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    if not (DIST / "index.html").exists():
        pytest.skip("falta web/dist: ejecuta `npm run build` en web/")
    dist = tmp_path / "dist"
    shutil.copytree(DIST, dist)
    srv = Server(tmp_path / "data", dist)
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture
def page(server: Server) -> Iterator[object]:
    with playwright_sync.sync_playwright() as p:
        browser = None
        for kwargs in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
            try:
                browser = p.chromium.launch(**kwargs)
                break
            except Exception:
                continue
        if browser is None:
            pytest.skip("No hay navegador Chromium/Edge/Chrome disponible para Playwright")
        context = browser.new_context()
        pg = context.new_page()
        pg.on("console", lambda m: print(f"[consola] {m.type}: {m.text}"))
        yield pg
        context.close()
        browser.close()


def _abrir(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    page.goto(server.url)
    page.get_by_role("heading", name="¿En qué te puedo ayudar?").wait_for(timeout=20_000)
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")  # service worker instalado y activo


def _consultar_y_esperar_dictamen(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_label("Describe tu caso").fill(CONSULTA)
    page.get_by_role("button", name="Analizar").click()
    page.get_by_text("Fundamentos verificados").wait_for(timeout=90_000)
    assert page.get_by_text("token local inválido").count() == 0


def test_consulta_completa_desde_el_navegador(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    assert page.get_by_text("Puedes actuar sin abogado").count() >= 1


def test_servidor_reiniciado_con_otro_token_sin_recargar(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    page.evaluate("fetch('/api/token').then(r => r.json())")  # la pestaña ya conoce el token antiguo
    server.stop()
    server.rotate_token()
    server.start()
    _consultar_y_esperar_dictamen(page)  # 403 -> token nuevo -> reintento, sin que el usuario lo note


def test_recarga_tras_reinicio_usa_el_token_nuevo(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    server.stop()
    server.rotate_token()
    server.start()
    page.reload()
    page.get_by_role("heading", name="¿En qué te puedo ayudar?").wait_for(timeout=20_000)
    _consultar_y_esperar_dictamen(page)


def test_copia_antigua_de_la_interfaz_se_autorrepara(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    # El servidor pasa a anunciar otro build: el JS que tiene la pestaña (y el service worker) es "antiguo".
    (server.dist / "version.json").write_text('{"build": "build-nuevo"}', encoding="utf-8")
    page.reload()
    page.get_by_role("heading", name="¿En qué te puedo ayudar?").wait_for(timeout=20_000)
    assert page.evaluate("sessionStorage.getItem('iuris-selfheal')") == "build-nuevo"  # limpió y recargó una vez
    _consultar_y_esperar_dictamen(page)


# ---------- mejoras de interfaz: citas en línea, exportar, calendario, lectura, biblioteca, comparar ----------


def test_dictamen_con_citas_en_linea_exportar_y_modo_lectura(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    assert page.get_by_role("button", name="Ver fuente 1:").count() >= 1  # superíndice [1] en el texto
    with page.expect_download() as dl:
        page.get_by_role("button", name="Exportar el expediente en Markdown").click()
    md = Path(dl.value.path()).read_text(encoding="utf-8")
    assert md.startswith("# Expediente de Desemppa") and "## Fundamentos verificados" in md and "[1]" in md
    page.get_by_role("button", name="Modo lectura").click()
    page.get_by_text("Modo lectura", exact=True).wait_for()
    assert page.get_by_role("complementary", name="Historial").count() == 0
    page.keyboard.press("Escape")
    page.get_by_role("complementary", name="Historial").wait_for()


def test_atajos_de_teclado(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    page.get_by_role("heading", name="¿En qué te puedo ayudar?").click()
    page.keyboard.press("?")
    page.get_by_role("dialog", name="Atajos de teclado").wait_for()
    page.keyboard.press("Escape")
    page.keyboard.press("/")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == "Describe tu caso"


def test_biblioteca_guardar_y_usar_en_una_consulta(page, server: Server, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    doc = tmp_path / "sentencia.txt"
    doc.write_text("SENTENCIA. El arrendatario no responde del desgaste por el uso ordinario de la vivienda.", "utf-8")
    page.get_by_role("button", name="Biblioteca", exact=True).click()
    page.locator("input[type=file]").set_input_files(str(doc))
    page.get_by_text("sentencia.txt").wait_for()
    page.get_by_role("button", name="Nueva consulta").click()
    page.get_by_role("button", name="Añadir desde tu biblioteca").click()
    page.get_by_role("menuitem", name="sentencia.txt").click()
    page.get_by_role("button", name="Quitar sentencia.txt").wait_for()  # ya es un adjunto de la consulta


def test_comparar_dos_consultas(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    page.get_by_role("button", name="Nueva consulta").click()
    _consultar_y_esperar_dictamen(page)
    page.get_by_role("button", name="Comparar consultas").click()
    page.get_by_role("heading", name="Comparar consultas").wait_for()
    page.get_by_text("En las dos (").wait_for()


# ---------- accesibilidad automática ----------

AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"


def _axe(page) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    if not AXE.exists():
        pytest.skip("falta axe-core: ejecuta `npm install` en web/")
    page.add_script_tag(path=str(AXE))
    res = page.evaluate("axe.run(document, {resultTypes: ['violations']})")
    graves = [v for v in res["violations"] if v["impact"] in ("serious", "critical")]
    for v in graves:
        print(f"[axe] {v['id']} ({v['impact']}): {v['help']} -> {[n['target'] for n in v['nodes']][:5]}")
    return graves


def test_axe_sin_errores_graves_en_inicio_y_dictamen(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    assert _axe(page) == []
    _consultar_y_esperar_dictamen(page)
    assert _axe(page) == []


def test_lighthouse_accesibilidad_y_buenas_practicas(server: Server, tmp_path: Path) -> None:
    cli = ROOT / "web" / "node_modules" / "lighthouse" / "cli" / "index.js"
    node = shutil.which("node")
    if not cli.exists() or node is None:
        pytest.skip("falta lighthouse o node: ejecuta `npm install` en web/")
    with playwright_sync.sync_playwright() as p:
        chrome = p.chromium.executable_path
    salida = tmp_path / "lh.json"
    r = subprocess.run(
        [
            node,
            str(cli),
            server.url,
            "--only-categories=accessibility,best-practices",
            "--output=json",
            f"--output-path={salida}",
            "--quiet",
            "--chrome-flags=--headless=new --no-sandbox",
        ],
        env={**os.environ, "CHROME_PATH": chrome},
        capture_output=True,
        text=True,
        timeout=180,
    )
    if not salida.exists():
        pytest.fail(f"lighthouse no generó informe: {r.stderr[-2000:]}")
    import json

    cats = json.loads(salida.read_text(encoding="utf-8"))["categories"]
    puntos = {k: round(v["score"] * 100) for k, v in cats.items()}
    print(f"[lighthouse] {puntos}")
    assert puntos["accessibility"] >= 95 and puntos["best-practices"] >= 90, puntos


# ---------- fin del análisis, PDF sin texto interno y selector de fechas ----------


def test_al_terminar_lleva_a_la_respuesta_y_avisa(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    page.get_by_role("status").get_by_text("Ya tienes la respuesta").wait_for()
    page.wait_for_timeout(800)  # desplazamiento suave
    arriba = page.evaluate("document.querySelector('article[aria-label=Dictamen]').getBoundingClientRect().top")
    assert 0 <= arriba < page.viewport_size["height"] / 2, arriba


def test_pdf_sin_json_ni_texto_interno(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    page.emulate_media(media="print")
    texto = page.locator("body").inner_text()
    assert "Cómo se ha analizado" in texto and "Razonamiento del Magistrado" in texto
    for interno in ('{"', '"cuestiones"', '"afirmacion"', '"verbatim_quote"'):
        assert interno not in texto, interno


def test_selector_de_fechas_en_las_aclaraciones(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    page.get_by_label("Describe tu caso").fill(
        "El casero no me devuelve la fianza de 900 euros porque dice que hay que pintar."
    )
    page.get_by_role("button", name="Analizar").click()
    page.get_by_role("button", name="Abrir calendario").click()
    dialogo = page.get_by_role("dialog", name="Elegir")
    dialogo.wait_for()
    dialogo.get_by_role("button", name="Mes anterior").click()
    assert dialogo.get_by_role("columnheader").first.get_attribute("aria-label") == "lunes"
    page.keyboard.press("Escape")
    campo = page.get_by_role("textbox", name="Indica la fecha exacta")
    campo.fill("31/02/2026")
    campo.press("Enter")
    page.get_by_text("Escribe la fecha como día/mes/año").wait_for()
    campo.fill("01/06/2026")
    campo.press("Enter")
    assert page.get_by_role("alert").filter(has_text="día/mes/año").count() == 0


def test_hoja_de_ruta_escrito_y_modo_profesional(page, server: Server) -> None:  # type: ignore[no-untyped-def]
    _abrir(page, server)
    _consultar_y_esperar_dictamen(page)
    hoja = page.get_by_role("region", name="Qué hacer a continuación")
    hoja.wait_for()
    assert hoja.get_by_text("Intentar negociar antes de demandar").count() == 1
    hoja.get_by_role("button", name="Base legal").first.click()
    assert hoja.get_by_text("Artículo 36 · LAU").count() >= 1
    borrador = hoja.get_by_role("button", name="Borrador del escrito")
    if borrador.count():  # solo con solidez favorable o sólida
        borrador.first.click()
        texto = page.get_by_label("Texto del escrito").input_value()
        assert "HECHOS" in texto and "FUNDAMENTOS" in texto and "[NOMBRE Y APELLIDOS]" in texto
        page.keyboard.press("Escape")
    page.get_by_role("button", name="Modo profesional").click()
    page.get_by_role("region", name="Vista profesional").get_by_text("Esquema de escrito").wait_for()
