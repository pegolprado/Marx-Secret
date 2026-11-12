"""Janela principal do MARX SECRET."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_COMMERCIAL_NAME, APP_NAME, __version__
from . import icons, theme
from .context import AppContext
from .pages.analysis_pages import AnalysisPage, ComparePage
from .pages.crypto_page import CryptoPage
from .pages.dashboard import DashboardPage
from .pages.management_pages import FilesPage, HistoryPage, ReportsPage
from .pages.settings_pages import AboutPage, SettingsPage
from .pages.stego_pages import (
    ExtractMessagePage,
    HideFilePage,
    HideMessagePage,
    RecoverFilePage,
)

NAV = [
    ("VISÃO GERAL", [DashboardPage]),
    ("ESTEGANOGRAFIA", [HideMessagePage, ExtractMessagePage, HideFilePage, RecoverFilePage]),
    ("PROTEÇÃO", [CryptoPage]),
    ("INTELIGÊNCIA", [AnalysisPage, ComparePage]),
    ("GESTÃO", [HistoryPage, ReportsPage, FilesPage]),
    ("SISTEMA", [SettingsPage, AboutPage]),
]


def apply_theme(app: QApplication, palette: theme.Palette) -> None:
    app.setProperty("marx_theme", palette.name)
    app.setStyleSheet(theme.stylesheet(palette))


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_COMMERCIAL_NAME}")
        self.setWindowIcon(icons.app_icon())
        self.resize(1360, 860)
        self.setMinimumSize(QSize(1080, 680))

        root = QWidget()
        root.setObjectName("Root")
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.pages: dict[str, QWidget] = {}
        for _group, classes in NAV:
            for cls in classes:
                page = cls(ctx)
                self.pages[cls.key] = page
                self.stack.addWidget(page)

        ctx.navigate.connect(self.go)
        ctx.theme_changed.connect(self._on_theme)
        self._install_shortcuts()
        self.go("dashboard")

    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(250)
        v = QVBoxLayout(bar)
        v.setContentsMargins(0, 18, 0, 8)
        v.setSpacing(0)
        brand = QHBoxLayout()
        brand.setContentsMargins(18, 0, 18, 12)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(44))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        n = QLabel(APP_NAME)
        n.setObjectName("BrandName")
        names.addWidget(n)
        t = QLabel("PROFESSIONAL")
        t.setObjectName("BrandTag")
        names.addWidget(t)
        brand.addLayout(names)
        brand.addStretch()
        v.addLayout(brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for group, classes in NAV:
            g = QLabel(group)
            g.setObjectName("NavGroup")
            v.addWidget(g)
            for cls in classes:
                b = QPushButton("  " + cls.title)
                b.setObjectName("NavButton")
                b.setCheckable(True)
                b.setIcon(icons.icon(cls.icon_name, "#9AA5AD", "#34D399"))
                b.setIconSize(QSize(18, 18))
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _=False, k=cls.key: self.go(k))
                self.nav_group.addButton(b)
                self.nav_buttons[cls.key] = b
                v.addWidget(b)
        v.addStretch()
        footer = QLabel(f"v{__version__} · Processamento local e offline")
        footer.setObjectName("SidebarFooter")
        v.addWidget(footer)
        return bar

    def _install_shortcuts(self) -> None:
        keys = ["dashboard", "hide_message", "extract_message", "hide_file", "recover_file",
                "crypto", "analysis", "compare", "history"]
        for i, key in enumerate(keys, start=1):
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+{i}"))
            act.triggered.connect(lambda _=False, k=key: self.go(k))
            self.addAction(act)

    # ------------------------------------------------------------------
    def go(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.nav_buttons[key].setChecked(True)
        self.setWindowTitle(f"{APP_COMMERCIAL_NAME} — {page.title}")
        if self.stack.currentWidget() is page:
            return
        self.stack.setCurrentWidget(page)
        page.on_show()
        if self.ctx.setting("animations"):
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", page)
            anim.setDuration(180)
            anim.setStartValue(0.35)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.finished.connect(lambda: page.setGraphicsEffect(None))
            anim.start()

    def current_key(self) -> str:
        w = self.stack.currentWidget()
        return getattr(w, "key", "")

    def _on_theme(self, palette: theme.Palette) -> None:
        apply_theme(QApplication.instance(), palette)
        for page in self.pages.values():
            page.update()
