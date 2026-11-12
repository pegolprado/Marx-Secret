"""Identidade visual MARX SECRET: paletas (escura/clara) e folha de estilo Qt."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.paths import resource_dir


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    sidebar: str
    surface: str
    surface2: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    on_accent: str
    danger: str
    warning: str
    info: str
    selection: str


DARK = Palette(
    name="escuro",
    bg="#0B0D0F",
    sidebar="#08090B",
    surface="#14171B",
    surface2="#1B1F24",
    border="#272C33",
    text="#E7ECEA",
    muted="#8A949C",
    accent="#10B981",
    accent_hover="#34D399",
    accent_pressed="#059669",
    accent_soft="rgba(16, 185, 129, 0.14)",
    on_accent="#03140D",
    danger="#F05252",
    warning="#F5A524",
    info="#38BDF8",
    selection="#0E5E43",
)

LIGHT = Palette(
    name="claro",
    bg="#F3F6F4",
    sidebar="#101317",
    surface="#FFFFFF",
    surface2="#EDF2EF",
    border="#D3DBD6",
    text="#12171A",
    muted="#5A646C",
    accent="#059669",
    accent_hover="#10B981",
    accent_pressed="#047857",
    accent_soft="rgba(5, 150, 105, 0.12)",
    on_accent="#FFFFFF",
    danger="#DC2626",
    warning="#B45309",
    info="#0369A1",
    selection="#A7F3D0",
)

PALETTES = {"escuro": DARK, "claro": LIGHT}


def palette(name: str) -> Palette:
    return PALETTES.get(name, DARK)


def stylesheet(p: Palette) -> str:
    check = (resource_dir() / "check.svg").as_posix()
    # A barra lateral é sempre escura (marca), inclusive no tema claro.
    return f"""
* {{
    font-family: "Segoe UI", "Inter", "Noto Sans", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
    color: {p.text};
}}
QMainWindow, QWidget#Root, QStackedWidget, QScrollArea, QWidget#PageBody {{
    background: {p.bg};
}}
QToolTip {{
    background: {p.surface2}; color: {p.text}; border: 1px solid {p.border};
    padding: 6px; border-radius: 6px;
}}

/* ---------- Barra lateral ---------- */
QFrame#Sidebar {{ background: {p.sidebar}; border-right: 1px solid #1A1E23; }}
QLabel#BrandName {{ color: #FFFFFF; font-size: 13pt; font-weight: 800; letter-spacing: 1px; }}
QLabel#BrandTag {{ color: #10B981; font-size: 7pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#NavGroup {{
    color: #5E6A72; font-size: 7.5pt; font-weight: 700; letter-spacing: 1.5px;
    padding: 12px 18px 4px 18px;
}}
QPushButton#NavButton {{
    text-align: left; padding: 9px 14px; margin: 1px 10px; border: none; border-radius: 8px;
    color: #B7C1C7; background: transparent; font-weight: 500;
}}
QPushButton#NavButton:hover {{ background: #15191E; color: #FFFFFF; }}
QPushButton#NavButton:checked {{
    background: rgba(16, 185, 129, 0.16); color: #34D399; font-weight: 700;
    border-left: 3px solid #10B981;
}}
QLabel#SidebarFooter {{ color: #4B555D; font-size: 7.5pt; padding: 10px 18px; }}

/* ---------- Cabeçalho de página ---------- */
QLabel#PageTitle {{ font-size: 19pt; font-weight: 800; color: {p.text}; }}
QLabel#PageSubtitle {{ color: {p.muted}; font-size: 10pt; }}
QLabel#SectionTitle {{ font-size: 11.5pt; font-weight: 700; color: {p.text}; }}
QLabel#Muted {{ color: {p.muted}; }}
QLabel#Hint {{ color: {p.muted}; font-size: 8.5pt; }}
QLabel#Badge {{
    background: {p.accent_soft}; color: {p.accent}; border-radius: 9px; padding: 2px 10px;
    font-weight: 700; font-size: 8.5pt;
}}
QLabel#BadgeDanger {{
    background: rgba(240, 82, 82, 0.15); color: {p.danger}; border-radius: 9px;
    padding: 2px 10px; font-weight: 700; font-size: 8.5pt;
}}
QLabel#BadgeWarning {{
    background: rgba(245, 165, 36, 0.15); color: {p.warning}; border-radius: 9px;
    padding: 2px 10px; font-weight: 700; font-size: 8.5pt;
}}

/* ---------- Cartões ---------- */
QFrame#Card {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px;
}}
QFrame#StatCard {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px;
}}
QFrame#StatCard:hover {{ border-color: {p.accent}; }}
QLabel#StatValue {{ font-size: 22pt; font-weight: 800; color: {p.text}; }}
QLabel#StatLabel {{ color: {p.muted}; font-size: 9pt; font-weight: 600; }}
QFrame#HeroCard {{
    border-radius: 16px; border: 1px solid {p.border};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0F1A16, stop:0.55 #0B1210, stop:1 #06231A);
}}
QLabel#HeroTitle {{ color: #FFFFFF; font-size: 22pt; font-weight: 800; letter-spacing: 1px; }}
QLabel#HeroText {{ color: #A9B7B1; font-size: 10pt; }}
QLabel#HeroSlogan {{ color: #34D399; font-weight: 700; letter-spacing: 2px; font-size: 8.5pt; }}

/* ---------- Entradas ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QDateEdit {{
    background: {p.surface2}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 7px 10px; selection-background-color: {p.selection};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus,
QDateEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:read-only {{ color: {p.muted}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border}; selection-background-color: {p.accent_soft};
    selection-color: {p.text}; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px; height: 18px; border: 1px solid {p.border}; background: {p.surface2};
}}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.accent}; border-color: {p.accent};
}}
QCheckBox::indicator:checked {{ image: url("{check}"); }}
QCheckBox::indicator:disabled {{ background: {p.surface}; border-color: {p.border}; }}
QCheckBox::indicator:checked:disabled {{
    background: {p.accent_pressed}; border-color: {p.accent_pressed}; image: url("{check}");
}}

/* ---------- Botões ---------- */
QPushButton {{
    background: {p.surface2}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 8px 16px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {p.accent}; color: {p.accent}; }}
QPushButton:pressed {{ background: {p.accent_soft}; }}
QPushButton:disabled {{ color: {p.muted}; border-color: {p.border}; background: {p.surface}; }}
QPushButton#Primary {{
    background: {p.accent}; color: {p.on_accent}; border: 1px solid {p.accent}; font-weight: 700;
    padding: 10px 22px;
}}
QPushButton#Primary:hover {{ background: {p.accent_hover}; color: {p.on_accent}; }}
QPushButton#Primary:pressed {{ background: {p.accent_pressed}; }}
QPushButton#Primary:disabled {{ background: {p.surface2}; color: {p.muted}; border-color: {p.border}; }}
QPushButton#Danger {{ color: {p.danger}; }}
QPushButton#Danger:hover {{ border-color: {p.danger}; background: rgba(240, 82, 82, 0.1); }}
QPushButton#Ghost {{ background: transparent; border: none; padding: 6px; }}
QPushButton#Ghost:hover {{ background: {p.accent_soft}; }}

/* ---------- Tabelas ---------- */
QTableWidget, QTableView, QListWidget, QTreeView {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px;
    gridline-color: {p.border}; alternate-background-color: {p.surface2};
    selection-background-color: {p.accent_soft}; selection-color: {p.text};
}}
QHeaderView::section {{
    background: {p.surface2}; color: {p.muted}; padding: 8px; border: none;
    border-bottom: 1px solid {p.border}; font-weight: 700; font-size: 8.5pt;
}}
QTableCornerButton::section {{ background: {p.surface2}; border: none; }}

/* ---------- Barras ---------- */
QProgressBar {{
    background: {p.surface2}; border: 1px solid {p.border}; border-radius: 6px; height: 12px;
    text-align: center; font-size: 8pt; color: {p.text};
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 5px; }}
QProgressBar[level="warn"]::chunk {{ background: {p.warning}; }}
QProgressBar[level="danger"]::chunk {{ background: {p.danger}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.accent}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: 10px; background: {p.surface}; top: -1px; }}
QTabBar::tab {{
    background: transparent; padding: 8px 16px; color: {p.muted}; border: none;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {p.accent}; border-bottom: 2px solid {p.accent}; }}

/* ---------- Zona de imagem ---------- */
QFrame#DropZone {{
    background: {p.surface2}; border: 2px dashed {p.border}; border-radius: 14px;
}}
QFrame#DropZone[active="true"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}

QFrame#Toast {{
    background: {p.surface}; border: 1px solid {p.accent}; border-radius: 10px;
}}
QFrame#Toast[kind="error"] {{ border-color: {p.danger}; }}
QFrame#Toast[kind="warn"] {{ border-color: {p.warning}; }}

QMessageBox {{ background: {p.surface}; }}
QMenu {{ background: {p.surface}; border: 1px solid {p.border}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.accent_soft}; }}
QSplitter::handle {{ background: {p.border}; }}
"""
