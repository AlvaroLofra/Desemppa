"""Desemppa en su propia ventana, con icono en la bandeja del sistema (junto al reloj).

Doble clic en el acceso directo «Desemppa» (lo crea INSTALAR_DESEMPPA.bat) o:
    uv run pythonw launcher/desemppa.pyw

- Muestra una pantalla de carga mientras arranca el servidor (sin --reload) y abre la app en una ventana propia.
- Al cerrar la ventana, Desemppa sigue en la bandeja; «Salir» en el menú del icono lo cierra todo.
- Si ya había un Desemppa en marcha con el código actual, lo usa y no lo para al salir.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pystray  # noqa: E402
import webview  # noqa: E402
from PIL import Image  # noqa: E402

from launcher import servidor  # noqa: E402

ICONO_ICO = ROOT / "assets" / "desemppa.ico"
ICONO_PNG = ROOT / "assets" / "desemppa.png"
LOGO_SVG = (ROOT / "web" / "public" / "icon.svg").read_text(encoding="utf-8")

CARGA = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center;
         font-family:"Segoe UI",system-ui,sans-serif; background:#F8FAFD; color:#1B1B1F; }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#131314; color:#E3E3E3; }} }}
  .logo svg {{ width:96px; height:96px; border-radius:24px; box-shadow:0 8px 24px rgba(11,87,208,.25);
              animation:latido 2.4s ease-in-out infinite; }}
  h1 {{ font-weight:400; font-size:32px; margin:24px 0 8px; letter-spacing:-.5px; }}
  #estado {{ font-size:14px; opacity:.7; min-height:20px; text-align:center; max-width:520px; padding:0 16px; }}
  .barra {{ width:220px; height:4px; border-radius:2px; background:rgba(11,87,208,.15); overflow:hidden; margin-top:20px; }}
  .barra::after {{ content:""; display:block; width:40%; height:100%; background:#0B57D0; border-radius:2px;
                  animation:avance 1.2s ease-in-out infinite; }}
  .error #estado {{ color:#B3261E; opacity:1; }} .error .barra {{ display:none; }}
  @keyframes avance {{ 0% {{ transform:translateX(-100%); }} 100% {{ transform:translateX(250%); }} }}
  @keyframes latido {{ 50% {{ transform:scale(1.04); }} }}
</style></head><body><div class="logo">{LOGO_SVG}</div><h1>Desemppa</h1>
<div id="estado">Preparando…</div><div class="barra"></div></body></html>"""


class Lanzador:
    def __init__(self) -> None:
        self.proceso: Any = None  # servidor arrancado por este lanzador (None si ya estaba en marcha)
        self.saliendo = False
        self.avisado_bandeja = False
        self.ventana = webview.create_window(
            "Desemppa", html=CARGA, width=1280, height=860, min_size=(420, 560), background_color="#F8FAFD"
        )
        self.ventana.events.closing += self._al_cerrar
        self.icono = pystray.Icon(
            "Desemppa",
            Image.open(ICONO_PNG),
            "Desemppa",
            menu=pystray.Menu(
                pystray.MenuItem("Abrir Desemppa", self._mostrar, default=True),
                pystray.MenuItem("Abrir en el navegador", lambda: webbrowser.open(servidor.URL)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", self._salir),
            ),
        )

    def _estado(self, texto: str, error: bool = False) -> None:
        js = f"document.getElementById('estado').textContent = {json.dumps(texto)};"
        if error:
            js += "document.body.classList.add('error');"
        self.ventana.evaluate_js(js)

    def arrancar(self) -> None:
        """Se ejecuta en un hilo aparte cuando la ventana ya está abierta."""
        threading.Thread(target=self.icono.run, daemon=True).start()
        try:
            self._estado("Comprobando si Desemppa ya está en marcha…")
            codigo = servidor.comprobar()
            if codigo == 3:
                self._estado(
                    f"El puerto {servidor.PUERTO} lo está usando otro programa. Ciérralo y vuelve a abrir Desemppa.", True
                )
                return
            if codigo != 2:
                servidor.preparar(self._estado)
                self._estado("Arrancando el servidor…")
                self.proceso = servidor.arrancar()
            if not servidor.esperar(proceso=self.proceso):
                self._estado(f"El servidor no ha arrancado. Revisa {servidor.LOG}", True)
                return
            self.ventana.load_url(servidor.URL)
        except Exception as exc:  # noqa: BLE001 — cualquier fallo se muestra en la pantalla de carga
            self._estado(f"No se ha podido arrancar: {exc}", True)

    def _al_cerrar(self) -> bool:
        if self.saliendo:
            return True
        self.ventana.hide()  # sigue en la bandeja
        if not self.avisado_bandeja:
            self.avisado_bandeja = True
            try:
                self.icono.notify("Desemppa sigue abierto aquí. Para cerrarlo del todo: clic derecho → Salir.", "Desemppa")
            except Exception:  # noqa: BLE001 — las notificaciones son opcionales
                pass
        return False

    def _mostrar(self) -> None:
        self.ventana.show()
        self.ventana.restore()

    def _salir(self) -> None:
        self.saliendo = True
        self.icono.stop()
        servidor.detener(self.proceso)
        self.ventana.destroy()


def main() -> None:
    webview.settings["ALLOW_DOWNLOADS"] = True  # exportar el expediente, el PDF y el .ics
    lanzador = Lanzador()
    # private_mode=False y almacenamiento propio: se conservan el tema, el modo y demás preferencias entre arranques.
    webview.start(
        lanzador.arrancar,
        private_mode=False,
        storage_path=str(ROOT / "data" / "local" / "webview"),
        icon=str(ICONO_ICO),
    )
    if not lanzador.saliendo:  # la ventana se cerró por otra vía (p. ej. fin de sesión de Windows)
        lanzador.icono.stop()
        servidor.detener(lanzador.proceso)


if __name__ == "__main__":
    main()
