"""Contexto compartilhado da interface: banco, serviço, configurações e sinais."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from ..core import paths, payload
from ..data.database import DEFAULT_SETTINGS, Database
from ..services.operations import HideOptions, MarxSecretService
from . import theme


class AppContext(QObject):
    history_changed = Signal()
    settings_changed = Signal()
    theme_changed = Signal(object)  # Palette
    navigate = Signal(str)  # chave da página
    request_compare = Signal(str, str)  # original, processada
    request_analysis = Signal(str)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.service = MarxSecretService(db)

    # -- configurações ---------------------------------------------------
    def setting(self, key: str) -> Any:
        return self.db.get_setting(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key: str, value: Any) -> None:
        self.db.set_setting(key, value)
        self.settings_changed.emit()
        if key == "theme":
            self.theme_changed.emit(self.palette)

    @property
    def palette(self) -> theme.Palette:
        return theme.palette(self.setting("theme"))

    def output_dir(self) -> Path:
        configured = self.setting("output_dir")
        if configured and Path(configured).is_dir():
            return Path(configured)
        return paths.default_output_dir()

    def max_payload_bytes(self) -> int:
        mb = int(self.setting("max_payload_mb") or 64)
        return min(mb * 1024 * 1024, payload.HARD_MAX_PAYLOAD)

    def hide_options(self, password: str | None, bits_per_channel: int, scattered: bool,
                     compress: bool) -> HideOptions:
        return HideOptions(
            password=password or None,
            bits_per_channel=bits_per_channel,
            scattered=scattered and bool(password),
            compress=compress,
            kdf_profile=self.setting("kdf_profile"),
            max_payload_bytes=self.max_payload_bytes(),
            min_password_length=int(self.setting("min_password_length")),
            require_password=bool(self.setting("require_password")),
        )

    def notify_history(self) -> None:
        self.history_changed.emit()
