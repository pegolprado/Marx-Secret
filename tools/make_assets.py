"""Gera os ativos de imagem a partir do logotipo vetorial (logo.svg).

Saídas (em marx_secret/assets e installer/):
  logo_256.png, logo_512.png, marx_secret.ico (16–256 px),
  installer/wizard_large.bmp (164×314) e installer/wizard_small.bmp (55×55).
Uso: python tools/make_assets.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from marx_secret.ui.icons import render_svg  # noqa: E402

ASSETS = ROOT / "marx_secret" / "assets"
INSTALLER = ROOT / "installer"


def svg_to_pil(size: int) -> Image.Image:
    pm = render_svg((ASSETS / "logo.svg").read_text(encoding="utf-8"), size)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    from io import BytesIO

    return Image.open(BytesIO(bytes(buf.data()))).convert("RGBA")


def font(size: int, bold: bool = True):
    for name in ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    _app = QGuiApplication.instance() or QGuiApplication([])
    big = svg_to_pil(512)
    big.save(ASSETS / "logo_512.png")
    svg_to_pil(256).save(ASSETS / "logo_256.png")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [svg_to_pil(s) for s in sizes]
    imgs[-1].save(ASSETS / "marx_secret.ico", format="ICO", sizes=[(s, s) for s in sizes],
                  append_images=imgs[:-1])

    INSTALLER.mkdir(exist_ok=True)
    # imagem lateral do assistente de instalação (164×314) – ×2 para telas de alta resolução
    w, h = 328, 628
    side = Image.new("RGB", (w, h), (8, 9, 11))
    d = ImageDraw.Draw(side)
    for y in range(h):
        g = int(20 + 30 * y / h)
        d.line([(0, y), (w, y)], fill=(6, g // 2, g // 3 + 4))
    for x in range(0, w, 22):
        for y in range(0, h, 22):
            if (x * 7 + y * 13) % 5 == 0:
                d.rectangle([x, y, x + 6, y + 6], fill=(14, 60, 44))
    logo = svg_to_pil(220)
    side.paste(logo, ((w - 220) // 2, 120), logo)
    f1, f2 = font(34), font(14)
    for text, f, y, color in (("MARX", f1, 370, (255, 255, 255)),
                              ("SECRET", f1, 410, (255, 255, 255)),
                              ("PROFESSIONAL", f2, 462, (52, 211, 153))):
        tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, y), text, font=f, fill=color)
    side.resize((164, 314), Image.LANCZOS).save(INSTALLER / "wizard_large.bmp")
    side.save(INSTALLER / "wizard_large_2x.bmp")
    small = Image.new("RGB", (110, 110), (255, 255, 255))
    sl = svg_to_pil(100)
    small.paste(sl, (5, 5), sl)
    small.resize((55, 55), Image.LANCZOS).save(INSTALLER / "wizard_small.bmp")
    small.save(INSTALLER / "wizard_small_2x.bmp")
    print("Ativos gerados.")


if __name__ == "__main__":
    main()
