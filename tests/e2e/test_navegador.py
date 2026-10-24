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
