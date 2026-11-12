"""Tela de abertura."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from .. import APP_NAME, APP_SLOGAN, __version__
from .icons import banner_pixmap, logo_pixmap


def splash_pixmap(width: int = 820, height: int = 300) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setBrush(QColor("#030409"))
    p.setPen(QColor("#2A2F36"))
    p.drawRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), 18, 18)
    banner = banner_pixmap(width - 24)
    if not banner.isNull():
        p.drawPixmap(12, 24, banner)
        y = 24 + banner.height() + 18
    else:  # pragma: no cover - recurso ausente
        p.drawPixmap(int(width / 2 - 64), 30, logo_pixmap(128))
        y = 180
    p.setPen(QColor("#D4AF37"))
    f2 = QFont("Segoe UI", 10, QFont.Weight.Bold)
    f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
    p.setFont(f2)
    p.drawText(QRectF(0, y, width, 24), Qt.AlignmentFlag.AlignCenter, APP_SLOGAN)
    p.setPen(QColor("#6B7780"))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(QRectF(0, height - 36, width, 20), Qt.AlignmentFlag.AlignCenter,
               f"{APP_NAME} Professional Steganography Suite · versão {__version__}")
    p.end()
    return pm


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__(splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
