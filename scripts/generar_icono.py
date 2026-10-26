"""Genera el icono de Windows (`assets/desemppa.ico`) y el de la bandeja (`assets/desemppa.png`) a partir del mismo
dibujo que `web/public/icon.svg` (balanza blanca sobre fondo azul redondeado), con Pillow y sin dependencias extra.

Uso:
    uv run python scripts/generar_icono.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
AZUL = "#0B57D0"
TAMANOS_ICO = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def dibujar(lado: int = 512) -> Image.Image:
    """Mismas coordenadas que icon.svg (viewBox 512), escaladas a `lado` con 4x de sobremuestreo."""
    k = 4 * lado / 512
    img = Image.new("RGBA", (round(512 * k), round(512 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 512 * k - 1, 512 * k - 1), radius=128 * k, fill=AZUL)
    w = round(20 * k)

    def linea(*puntos: tuple[float, float]) -> None:
        d.line([(x * k, y * k) for x, y in puntos], fill="white", width=w, joint="curve")
        for x, y in (puntos[0], puntos[-1]):  # extremos redondeados (stroke-linecap="round")
            d.ellipse((x * k - w / 2, y * k - w / 2, x * k + w / 2, y * k + w / 2), fill="white")

    linea((256, 128), (256, 392))
    linea((184, 392), (328, 392))
    linea((144, 176), (368, 176))
    linea((144, 176), (96, 280), (192, 280), (144, 176))
    linea((368, 176), (320, 280), (416, 280), (368, 176))
    return img.resize((lado, lado), Image.Resampling.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    destino = Path(argv[0]) if argv else ASSETS
    destino.mkdir(parents=True, exist_ok=True)
    grande = dibujar(256)
    grande.save(destino / "desemppa.ico", sizes=TAMANOS_ICO)
    dibujar(64).save(destino / "desemppa.png")
    print(f"Iconos generados en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
