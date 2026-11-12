# -*- mode: python ; coding: utf-8 -*-
# Especificação PyInstaller do MARX SECRET (modo pasta: inicialização rápida e
# menos falsos positivos de antivírus). Uso: pyinstaller installer/marx_secret.spec
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
IS_WIN = sys.platform == "win32"

a = Analysis(
    [str(ROOT / "run_marx_secret.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "marx_secret" / "assets"), "marx_secret/assets")],
    hiddenimports=["argon2", "_cffi_backend", "PySide6.QtSvg"],
    excludes=[
        "tkinter", "unittest", "pydoc_data", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtNetwork",
        "PySide6.QtPdf", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "pytest", "pytestqt",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MARX_SECRET",
    icon=str(ROOT / "marx_secret" / "assets" / "marx_secret.ico"),
    version=str(ROOT / "installer" / "version_info.txt") if IS_WIN else None,
    console=False,
    disable_windowed_traceback=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MARX_SECRET", upx=False)
