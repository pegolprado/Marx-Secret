"""Componentes visuais reutilizáveis do MARX SECRET."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core import crypto, imageio
from . import icons, theme


def current_palette() -> theme.Palette:
    app = QApplication.instance()
    name = app.property("marx_theme") if app else None
    return theme.palette(name or "escuro")


def fmt_bytes(n: int | float) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if v < 1024 or unit == "GB":
            return f"{int(v)} B" if unit == "B" else f"{v:.2f} {unit}".replace(".", ",")
        v /= 1024
    return str(n)


def pil_to_pixmap(img) -> QPixmap:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: rgba(127,127,127,0.25);")
    return f


def label(text: str = "", obj: str | None = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, icon_name: str | None = None, obj: str | None = None,
           on_click: Callable | None = None, tooltip: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if obj:
        b.setObjectName(obj)
    if icon_name:
        color = current_palette().on_accent if obj == "Primary" else current_palette().accent
        b.setIcon(icons.icon(icon_name, color))
        b.setIconSize(QSize(18, 18))
    if on_click:
        b.clicked.connect(on_click)
    if tooltip:
        b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Card(QFrame):
    def __init__(self, title: str | None = None, subtitle: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(20, 18, 20, 18)
        self.layout_.setSpacing(12)
        if title:
            self.layout_.addWidget(label(title, "SectionTitle"))
        if subtitle:
            self.layout_.addWidget(label(subtitle, "Hint", wrap=True))

    def add(self, w: QWidget | None = None, layout=None, stretch: int = 0):
        if w is not None:
            self.layout_.addWidget(w, stretch)
        if layout is not None:
            self.layout_.addLayout(layout, stretch)
        return self


class Page(QWidget):
    """Página com cabeçalho e corpo rolável."""

    key = ""
    title = ""
    subtitle = ""
    icon_name = "info"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QWidget()
        hl = QVBoxLayout(header)
        hl.setContentsMargins(32, 26, 32, 10)
        hl.setSpacing(2)
        hl.addWidget(label(self.title, "PageTitle"))
        if self.subtitle:
            hl.addWidget(label(self.subtitle, "PageSubtitle", wrap=True))
        outer.addWidget(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("PageBody")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(32, 12, 32, 32)
        self.body.setSpacing(18)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def on_show(self) -> None:
        """Chamado quando a página se torna visível."""

    def toast(self, text: str, kind: str = "ok") -> None:
        Toast.show_message(self.window(), text, kind)

    def error(self, text: str) -> None:
        Toast.show_message(self.window(), text, "error")
        error_box(self, text)


def error_box(parent: QWidget, text: str, title: str = "MARX SECRET") -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    if os.environ.get("MARX_SECRET_NO_DIALOGS"):
        return
    box.exec()


def confirm(parent: QWidget, title: str, text: str) -> bool:
    if os.environ.get("MARX_SECRET_NO_DIALOGS"):
        return True
    res = QMessageBox.question(parent, title, text,
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                               QMessageBox.StandardButton.No)
    return res == QMessageBox.StandardButton.Yes


# ---------------------------------------------------------------------------
# Seletores
# ---------------------------------------------------------------------------

class PathSelector(QWidget):
    changed = Signal(str)

    def __init__(self, mode: str = "open", file_filter: str = "Todos os arquivos (*)",
                 placeholder: str = "", default_dir: Callable[[], Path] | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.mode = mode
        self.file_filter = file_filter
        self.default_dir = default_dir
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.changed.emit)
        lay.addWidget(self.edit, 1)
        icon_name = "folder" if mode == "dir" else ("save" if mode == "save" else "upload")
        self.btn = button("Procurar…", icon_name, on_click=self.browse)
        lay.addWidget(self.btn)

    def browse(self) -> None:
        start = self.edit.text() or (str(self.default_dir()) if self.default_dir else "")
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Selecionar pasta", start)
        elif self.mode == "save":
            path, _ = QFileDialog.getSaveFileName(self, "Salvar como", start, self.file_filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", start,
                                                  self.file_filter)
        if path:
            self.edit.setText(path)

    def path(self) -> str:
        return self.edit.text().strip()

    def set_path(self, p: str) -> None:
        self.edit.setText(p)


class ImageDropZone(QFrame):
    """Área de seleção de imagem com arrastar e soltar e pré-visualização."""

    path_changed = Signal(str)

    def __init__(self, title: str = "Imagem", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(250)
        self._path = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.title = label(title, "SectionTitle")
        lay.addWidget(self.title)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(150)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.preview, 1)
        self.info = label("Arraste uma imagem aqui ou clique em Selecionar.\n"
                          "PNG, BMP, TIFF, JPEG, WEBP ou GIF.", "Hint", wrap=True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        row.addStretch()
        self.select_btn = button("Selecionar imagem", "image", on_click=self.browse)
        self.clear_btn = button("Limpar", "trash", on_click=self.clear)
        self.clear_btn.setEnabled(False)
        row.addWidget(self.select_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        lay.addLayout(row)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.preview.setPixmap(icons.render_svg(
            icons.svg_markup("image", current_palette().muted, 1.2), 72))

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar imagem", "", imageio.INPUT_FILTER)
        if path:
            self.set_path(path)

    def set_path(self, path: str) -> bool:
        try:
            info = imageio.image_info(path)
        except Exception as exc:  # noqa: BLE001
            self.info.setText(f"⚠ {exc}")
            return False
        self._path = path
        pm = QPixmap(path)
        if not pm.isNull():
            self.preview.setPixmap(pm.scaled(QSize(420, 220), Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        self.info.setText(f"{Path(path).name}\n{info.width} × {info.height} px · {info.format} · "
                          f"{info.mode} · {fmt_bytes(info.file_size)}")
        self.clear_btn.setEnabled(True)
        self.path_changed.emit(path)
        return True

    def clear(self) -> None:
        self._path = ""
        self._show_placeholder()
        self.info.setText("Arraste uma imagem aqui ou clique em Selecionar.")
        self.clear_btn.setEnabled(False)
        self.path_changed.emit("")

    def path(self) -> str:
        return self._path

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, e):  # noqa: N802
        self._set_active(False)

    def dropEvent(self, e):  # noqa: N802
        self._set_active(False)
        urls = e.mimeData().urls()
        if urls:
            self.set_path(urls[0].toLocalFile())


class PasswordField(QWidget):
    """Campo de senha com visualização, gerador, confirmação e medidor de força."""

    changed = Signal()

    def __init__(self, with_confirm: bool = False, with_generator: bool = False,
                 with_meter: bool = True, placeholder: str = "Senha",
                 parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self._update)
        row.addWidget(self.edit, 1)
        self.toggle = QPushButton()
        self.toggle.setObjectName("Ghost")
        self.toggle.setCheckable(True)
        self.toggle.setToolTip("Mostrar/ocultar senha")
        self.toggle.setIcon(icons.icon("eye", current_palette().muted))
        self.toggle.toggled.connect(self._toggle)
        row.addWidget(self.toggle)
        if with_generator:
            gen = button("", "dice", obj="Ghost", on_click=self.generate,
                         tooltip="Gerar senha forte")
            row.addWidget(gen)
        lay.addLayout(row)
        self.confirm = None
        if with_confirm:
            self.confirm = QLineEdit()
            self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm.setPlaceholderText("Confirmar senha")
            self.confirm.textChanged.connect(self._update)
            lay.addWidget(self.confirm)
        self.meter = None
        if with_meter:
            mrow = QHBoxLayout()
            self.meter = QProgressBar()
            self.meter.setRange(0, 4)
            self.meter.setTextVisible(False)
            self.meter.setFixedHeight(8)
            self.meter_label = label("", "Hint")
            mrow.addWidget(self.meter, 1)
            mrow.addWidget(self.meter_label)
            lay.addLayout(mrow)
        self._update()

    def _toggle(self, on: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        self.edit.setEchoMode(mode)
        if self.confirm:
            self.confirm.setEchoMode(mode)
        self.toggle.setIcon(icons.icon("eye_off" if on else "eye", current_palette().muted))

    def generate(self) -> None:
        pwd = crypto.generate_password(20)
        self.edit.setText(pwd)
        if self.confirm:
            self.confirm.setText(pwd)
        self.toggle.setChecked(True)

    def _update(self) -> None:
        if self.meter is not None:
            s = crypto.evaluate_password(self.edit.text())
            self.meter.setValue(s.score if self.edit.text() else 0)
            level = "danger" if s.score <= 1 else ("warn" if s.score == 2 else "ok")
            self.meter.setProperty("level", level)
            self.meter.style().unpolish(self.meter)
            self.meter.style().polish(self.meter)
            txt = s.label if self.edit.text() else ""
            if self.confirm and self.confirm.text() and self.confirm.text() != self.edit.text():
                txt = "As senhas não conferem"
            self.meter_label.setText(txt)
            if s.hints and self.edit.text():
                self.meter.setToolTip("\n".join(s.hints))
        self.changed.emit()

    def password(self) -> str:
        return self.edit.text()

    def matches(self) -> bool:
        return self.confirm is None or self.confirm.text() == self.edit.text()

    def clear(self) -> None:
        self.edit.clear()
        if self.confirm:
            self.confirm.clear()


class CapacityMeter(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.addWidget(label("Uso da capacidade", "StatLabel"))
        head.addStretch()
        self.text = label("—", "Hint")
        head.addWidget(self.text)
        lay.addLayout(head)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        lay.addWidget(self.bar)

    def set_usage(self, required: int, capacity: int) -> None:
        if capacity <= 0:
            self.bar.setValue(0)
            self.text.setText("Selecione uma imagem")
            return
        pct = required / capacity * 100
        self.bar.setValue(int(min(pct, 100) * 10))
        level = "ok" if pct <= 70 else ("warn" if pct <= 100 else "danger")
        self.bar.setProperty("level", level)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
        status = "excede a capacidade" if pct > 100 else "disponível"
        self.text.setText(f"{fmt_bytes(required)} de {fmt_bytes(capacity)} "
                          f"({pct:.1f}%) · {status}".replace(".", ",", 1))

    def set_extended(self, required: int, hard_max: int, configured_max: int) -> None:
        """Capacidade estendida: limite dado pelo tamanho máximo de conteúdo."""
        limit = min(hard_max, configured_max)
        pct = required / limit * 100 if limit else 100
        self.bar.setValue(int(min(pct, 100) * 10))
        level = "ok" if pct <= 100 else "danger"
        self.bar.setProperty("level", level)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
        status = ("excede o limite configurado" if pct > 100
                  else "capacidade estendida (bloco PNG)")
        self.text.setText(f"{fmt_bytes(required)} de {fmt_bytes(limit)} · {status}")

    def reset(self) -> None:
        self.set_usage(0, 0)


class StatCard(QFrame):
    def __init__(self, title: str, icon_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(108)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        top = QHBoxLayout()
        top.addWidget(label(title, "StatLabel"))
        top.addStretch()
        ic = QLabel()
        ic.setPixmap(icons.render_svg(icons.svg_markup(icon_name, current_palette().accent), 22))
        top.addWidget(ic)
        lay.addLayout(top)
        self.value = label("0", "StatValue")
        lay.addWidget(self.value)
        self.sub = label("", "Hint")
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


# ---------------------------------------------------------------------------
# Gráficos simples (QPainter, sem dependências externas)
# ---------------------------------------------------------------------------

class BarChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.data: list[tuple[str, int]] = []
        self.setMinimumHeight(180)

    def set_data(self, data: Sequence[tuple[str, int]]) -> None:
        self.data = list(data)
        self.update()

    def paintEvent(self, _):  # noqa: N802
        p = current_palette()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not self.data:
            return
        peak = max(1, max(v for _, v in self.data))
        n = len(self.data)
        gap = 14
        bw = (w - gap * (n + 1)) / n
        base = h - 26
        qp.setPen(QPen(QColor(p.border), 1))
        qp.drawLine(0, base, w, base)
        for i, (lbl, v) in enumerate(self.data):
            x = gap + i * (bw + gap)
            bh = (base - 18) * v / peak
            rect = QRectF(x, base - bh, bw, bh)
            path = QPainterPath()
            path.addRoundedRect(rect, 5, 5)
            qp.fillPath(path, QColor(p.accent if v else p.border))
            qp.setPen(QColor(p.muted))
            f = QFont(qp.font())
            f.setPointSizeF(8)
            qp.setFont(f)
            qp.drawText(QRectF(x - 6, base + 4, bw + 12, 18), Qt.AlignmentFlag.AlignCenter, lbl)
            if v:
                qp.setPen(QColor(p.text))
                qp.drawText(QRectF(x - 6, base - bh - 18, bw + 12, 16),
                            Qt.AlignmentFlag.AlignCenter, str(v))
        qp.end()


class LineChart(QWidget):
    """Gráfico de linhas: séries de (x, y) com cores."""

    def __init__(self, title: str = "", y_max: float | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self.series: list[tuple[np.ndarray, str]] = []
        self.y_max = y_max
        self.x_range = (0.0, 1.0)
        self.setMinimumHeight(200)

    def set_series(self, series: list[tuple[np.ndarray, str]], x_range: tuple[float, float]):
        self.series = series
        self.x_range = x_range
        self.update()

    def paintEvent(self, _):  # noqa: N802
        p = current_palette()
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, top, right, bottom = 10, 24, 10, 16
        qp.setPen(QColor(p.muted))
        qp.drawText(QRectF(left, 2, w, 18), Qt.AlignmentFlag.AlignLeft, self.title)
        qp.setPen(QPen(QColor(p.border), 1))
        qp.drawRect(QRectF(left, top, w - left - right, h - top - bottom))
        if not self.series:
            qp.end()
            return
        ymax = self.y_max or max(1.0, max(float(s[0][:, 1].max()) for s in self.series))
        x0, x1 = self.x_range
        pw, ph = w - left - right, h - top - bottom
        for arr, color in self.series:
            path = QPainterPath()
            for i, (x, y) in enumerate(arr):
                px = left + (x - x0) / (x1 - x0) * pw
                py = top + ph - (y / ymax) * ph
                if i == 0:
                    path.moveTo(QPointF(px, py))
                else:
                    path.lineTo(QPointF(px, py))
            qp.setPen(QPen(QColor(color), 1.6))
            qp.drawPath(path)
        qp.end()


# ---------------------------------------------------------------------------
# Notificações discretas
# ---------------------------------------------------------------------------

class Toast(QFrame):
    _current: "Toast | None" = None

    def __init__(self, parent: QWidget, text: str, kind: str):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        p = current_palette()
        color = {"error": p.danger, "warn": p.warning}.get(kind, p.accent)
        ic = QLabel()
        ic.setPixmap(icons.render_svg(icons.svg_markup(
            "alert" if kind in ("error", "warn") else "check", color), 20))
        lay.addWidget(ic)
        lb = QLabel(text)
        lb.setWordWrap(True)
        lb.setMaximumWidth(420)
        lb.setMinimumWidth(240)
        lay.addWidget(lb)
        self.adjustSize()
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @classmethod
    def show_message(cls, window: QWidget, text: str, kind: str = "ok") -> None:
        if window is None:
            return
        if cls._current is not None:
            try:
                cls._current.deleteLater()
            except RuntimeError:
                pass
        t = cls(window, text, kind)
        cls._current = t
        t.adjustSize()
        t.move(window.width() - t.width() - 24, window.height() - t.height() - 24)
        t.show()
        t.raise_()
        t.anim.setStartValue(0.0)
        t.anim.setEndValue(1.0)
        t.anim.start()
        QTimer.singleShot(4200, t._fade_out)

    def _fade_out(self) -> None:
        try:
            self.anim.setStartValue(1.0)
            self.anim.setEndValue(0.0)
            self.anim.finished.connect(self.deleteLater)
            self.anim.start()
        except RuntimeError:
            pass


class BannerLabel(QLabel):
    """Exibe o banner oficial ajustado à largura disponível (proporção preservada)."""

    def __init__(self, max_width: int = 1400, parent: QWidget | None = None):
        super().__init__(parent)
        self.max_width = max_width
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(200)
        self._update(600)

    def _update(self, width: int) -> None:
        w = max(200, min(width, self.max_width))
        pm = icons.banner_pixmap(w)
        if not pm.isNull():
            self.setPixmap(pm)
            self.setFixedHeight(pm.height())

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        target = min(self.width(), self.max_width)
        if self.pixmap() is None or abs(self.pixmap().width() - target) > 4:
            self._update(self.width())
