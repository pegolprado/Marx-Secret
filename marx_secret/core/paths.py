"""Diretórios da aplicação por plataforma (Windows, Linux e macOS).

Modo portátil: se existir um arquivo ``portable.flag`` ao lado do
executável (ou da raiz do projeto), todos os dados ficam em ``./dados``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .. import APP_ID, APP_NAME

PORTABLE_FLAG = "portable.flag"


def app_base_dir() -> Path:
    """Diretório do executável (PyInstaller) ou da raiz do projeto."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Diretório dos recursos empacotados (ícones, logotipo)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "marx_secret" / "assets"
    return Path(__file__).resolve().parents[1] / "assets"


def is_portable() -> bool:
    return (app_base_dir() / PORTABLE_FLAG).exists()


def data_dir() -> Path:
    override = os.environ.get("MARX_SECRET_DATA_DIR")
    if override:
        d = Path(override)
    elif is_portable():
        d = app_base_dir() / "dados"
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        d = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_output_dir() -> Path:
    if is_portable():
        d = app_base_dir() / "saida"
    else:
        docs = Path.home() / "Documents"
        if not docs.exists():
            docs = Path.home() / "Documentos" if (Path.home() / "Documentos").exists() else Path.home()
        d = docs / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = data_dir() / "saida"
        d.mkdir(parents=True, exist_ok=True)
    return d


def database_path() -> Path:
    return data_dir() / "marx_secret.db"


def log_path() -> Path:
    return data_dir() / "marx_secret.log"
