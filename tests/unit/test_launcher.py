"""Lanzador de escritorio: lógica sin interfaz gráfica (la ventana y la bandeja se prueban a mano)."""

import subprocess
import sys

from launcher import servidor


def test_comando_sin_reload_y_escuchando_en_la_red():
    cmd = servidor.comando_servidor("python.exe")
    assert "--reload" not in cmd  # en Windows rompe el ProactorEventLoop (CLAUDE.md, regla 3)
    assert cmd[:4] == ["python.exe", "-m", "uvicorn", "api.main:app"]
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0" and cmd[cmd.index("--port") + 1] == "8000"
    assert servidor.entorno()["IURIS_ESCUCHA_RED"] == "1"


def test_python_de_consola_para_el_servidor(monkeypatch, tmp_path):
    (tmp_path / "python.exe").write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))
    assert servidor.python_consola() == str(tmp_path / "python.exe")


def test_espera_y_detiene_un_servidor_real(tmp_path):
    """Arranca un servidor HTTP mínimo con /api/version, espera a que responda y lo para."""
    script = tmp_path / "srv.py"
    script.write_text(
        "import http.server\n"
        "class H(http.server.BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200 if self.path == '/api/version' else 404); self.end_headers()\n"
        "    def log_message(self, *a): pass\n"
        "http.server.HTTPServer(('127.0.0.1', 8765), H).serve_forever()\n"
    )
    p = subprocess.Popen([sys.executable, str(script)])
    try:
        assert servidor.esperar("http://127.0.0.1:8765", segundos=15, proceso=p)
    finally:
        servidor.detener(p)
    assert p.poll() is not None
    assert not servidor.responde("http://127.0.0.1:8765", timeout=0.5)


def test_no_espera_a_un_proceso_muerto():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert servidor.esperar("http://127.0.0.1:8766", segundos=5, proceso=p) is False


def test_generar_icono(tmp_path):
    from scripts import generar_icono

    assert generar_icono.main([str(tmp_path)]) == 0
    assert (tmp_path / "desemppa.ico").stat().st_size > 1000 and (tmp_path / "desemppa.png").exists()
