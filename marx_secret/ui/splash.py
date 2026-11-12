"""Tela de abertura."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from .. import APP_NAME, APP_SLOGAN, __version__
from .icons import logo_pixmap


def splash_pixmap(width: int = 640, height: int = 360) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0, QColor("#0D1513"))
    grad.setColorAt(0.6, QColor("#08090B"))
    grad.setColorAt(1, QColor("#05271B"))
    p.setBrush(grad)
    p.setPen(QColor("#10B981"))
    p.drawRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), 18, 18)
    # grade sutil de "pixels" (alusão à esteganografia)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(0, width, 22):
        for j in range(0, height, 22):
            if (i * 7 + j * 13) % 5 == 0:
                p.setBrush(QColor(16, 185, 129, 18))
                p.drawRect(i, j, 6, 6)
    p.drawPixmap(int(width / 2 - 64), 46, logo_pixmap(128))
    p.setPen(QColor("#FFFFFF"))
    f = QFont("Segoe UI", 30, QFont.Weight.Black)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
    p.setFont(f)
    p.drawText(QRectF(0, 186, width, 50), Qt.AlignmentFlag.AlignCenter, APP_NAME)
    p.setPen(QColor("#34D399"))
    f2 = QFont("Segoe UI", 10, QFont.Weight.Bold)
    f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
    p.setFont(f2)
    p.drawText(QRectF(0, 238, width, 24), Qt.AlignmentFlag.AlignCenter, APP_SLOGAN)
    p.setPen(QColor("#6B7780"))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(QRectF(0, height - 40, width, 20), Qt.AlignmentFlag.AlignCenter,
               f"Professional Steganography Suite · versão {__version__}")
    p.end()
    return pm


class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__(splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
