"""Configurações e personalização; tela Sobre."""

from __future__ import annotations

import platform
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ... import APP_COMMERCIAL_NAME, APP_DESCRIPTION, APP_NAME, APP_SLOGAN, __version__
from ...core import crypto, paths
from ...core.secure_delete import cleanup_stale_temp
from ..icons import logo_pixmap
from ..widgets import BannerLabel, Card, Page, PathSelector, button, confirm, label


class SettingsPage(Page):
    key = "settings"
    title = "Configurações"
    subtitle = "Personalize aparência, segurança e comportamento do MARX SECRET."
    icon_name = "settings"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        self._loading = False
        # aparência
        ap = Card("Aparência")
        f1 = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItem("Escuro (padrão)", "escuro")
        self.theme.addItem("Claro", "claro")
        f1.addRow("Tema:", self.theme)
        self.animations = QCheckBox("Animações discretas na navegação")
        f1.addRow("", self.animations)
        ap.add(layout=f1)
        self.body.addWidget(ap)

        # segurança
        sec = Card("Segurança")
        f2 = QFormLayout()
        self.kdf = QComboBox()
        for k, v in crypto.KDF_PROFILE_LABELS.items():
            self.kdf.addItem(v, k)
        f2.addRow("Derivação de chave (Argon2id):", self.kdf)
        self.require_password = QCheckBox("Exigir senha para ocultar conteúdos")
        f2.addRow("", self.require_password)
        self.min_len = QSpinBox()
        self.min_len.setRange(6, 64)
        f2.addRow("Tamanho mínimo da senha:", self.min_len)
        self.clip = QSpinBox()
        self.clip.setRange(0, 600)
        self.clip.setSuffix(" s")
        self.clip.setSpecialValueText("Nunca")
        f2.addRow("Limpar área de transferência após:", self.clip)
        self.passes = QSpinBox()
        self.passes.setRange(1, 7)
        f2.addRow("Passagens da exclusão segura:", self.passes)
        self.confirm_delete = QCheckBox("Confirmar antes da exclusão segura")
        f2.addRow("", self.confirm_delete)
        sec.add(layout=f2)
        self.body.addWidget(sec)

        # esteganografia
        st = Card("Esteganografia (padrões)")
        f3 = QFormLayout()
        self.bpc = QComboBox()
        for n in (1, 2, 3):
            self.bpc.addItem(f"{n} bit(s) por canal", n)
        f3.addRow("Densidade padrão:", self.bpc)
        self.scattered = QCheckBox("Distribuição dispersa guiada pela senha")
        f3.addRow("", self.scattered)
        self.compress = QCheckBox("Comprimir conteúdos")
        f3.addRow("", self.compress)
        self.max_mb = QSpinBox()
        self.max_mb.setRange(1, 256)
        self.max_mb.setSuffix(" MB")
        f3.addRow("Tamanho máximo do conteúdo:", self.max_mb)
        st.add(layout=f3)
        self.body.addWidget(st)

        # dados
        dt = Card("Arquivos e dados")
        dt.add(label("Pasta de saída padrão", "SectionTitle"))
        self.output_dir = PathSelector("dir", placeholder=str(paths.default_output_dir()))
        dt.add(self.output_dir)
        self.history = QCheckBox("Registrar operações no histórico (somente metadados)")
        dt.add(self.history)
        dt.add(label(f"Dados do aplicativo: {paths.data_dir()}"
                     f"{' · modo portátil' if paths.is_portable() else ''}", "Hint", wrap=True))
        row = QHBoxLayout()
        row.addWidget(button("Abrir pasta de dados", "folder",
                             on_click=lambda: QDesktopServices.openUrl(
                                 QUrl.fromLocalFile(str(paths.data_dir())))))
        row.addWidget(button("Limpar temporários", "trash", on_click=self._clean_tmp))
        row.addStretch()
        dt.add(layout=row)
        self.body.addWidget(dt)

        brow = QHBoxLayout()
        brow.addStretch()
        brow.addWidget(button("Restaurar padrões", "refresh", on_click=self.reset))
        brow.addWidget(button("Salvar configurações", "save", obj="Primary", on_click=self.save))
        self.body.addLayout(brow)
        self.body.addStretch()
        self.load()

    def load(self) -> None:
        s = self.ctx.db.all_settings()

        def set_combo(cb: QComboBox, value) -> None:
            i = cb.findData(value)
            cb.setCurrentIndex(max(0, i))

        set_combo(self.theme, s["theme"])
        self.animations.setChecked(bool(s["animations"]))
        set_combo(self.kdf, s["kdf_profile"])
        self.require_password.setChecked(bool(s["require_password"]))
        self.min_len.setValue(int(s["min_password_length"]))
        self.clip.setValue(int(s["clear_clipboard_seconds"]))
        self.passes.setValue(int(s["secure_delete_passes"]))
        self.confirm_delete.setChecked(bool(s["confirm_secure_delete"]))
        set_combo(self.bpc, int(s["bits_per_channel"]))
        self.scattered.setChecked(bool(s["scattered"]))
        self.compress.setChecked(bool(s["compress"]))
        self.max_mb.setValue(int(s["max_payload_mb"]))
        self.output_dir.set_path(s["output_dir"] or "")
        self.history.setChecked(bool(s["history_enabled"]))

    def save(self) -> None:
        out = self.output_dir.path()
        import os

        if out and not os.path.isdir(out):
            self.error("A pasta de saída informada não existe.")
            return
        values = {
            "theme": self.theme.currentData(),
            "animations": self.animations.isChecked(),
            "kdf_profile": self.kdf.currentData(),
            "require_password": self.require_password.isChecked(),
            "min_password_length": self.min_len.value(),
            "clear_clipboard_seconds": self.clip.value(),
            "secure_delete_passes": self.passes.value(),
            "confirm_secure_delete": self.confirm_delete.isChecked(),
            "bits_per_channel": self.bpc.currentData(),
            "scattered": self.scattered.isChecked(),
            "compress": self.compress.isChecked(),
            "max_payload_mb": self.max_mb.value(),
            "output_dir": out,
            "history_enabled": self.history.isChecked(),
        }
        old_theme = self.ctx.setting("theme")
        for k, v in values.items():
            self.ctx.db.set_setting(k, v)
        self.ctx.settings_changed.emit()
        if old_theme != values["theme"]:
            self.ctx.theme_changed.emit(self.ctx.palette)
        self.toast("Configurações salvas.")

    def reset(self) -> None:
        if confirm(self, "Restaurar padrões", "Restaurar todas as configurações padrão?"):
            old_theme = self.ctx.setting("theme")
            self.ctx.db.reset_settings()
            self.load()
            self.ctx.settings_changed.emit()
            if old_theme != self.ctx.setting("theme"):
                self.ctx.theme_changed.emit(self.ctx.palette)
            self.toast("Configurações restauradas.")

    def _clean_tmp(self) -> None:
        n = cleanup_stale_temp()
        self.toast(f"{n} pasta(s) temporária(s) removida(s) com segurança.")


class AboutPage(Page):
    key = "about"
    title = "Sobre"
    subtitle = APP_COMMERCIAL_NAME
    icon_name = "info"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        banner_card = QFrame()
        banner_card.setObjectName("HeroCard")
        bl = QVBoxLayout(banner_card)
        bl.setContentsMargins(1, 1, 1, 1)
        bl.addWidget(BannerLabel(1200))
        self.body.addWidget(banner_card)
        card = Card()
        row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(120))
        row.addWidget(logo)
        col = QVBoxLayout()
        col.addWidget(label(APP_NAME, "PageTitle"))
        col.addWidget(label(APP_SLOGAN, "Badge"))
        col.addWidget(label(f"Versão {__version__}", "Muted"))
        col.addWidget(label(APP_DESCRIPTION, wrap=True))
        col.addStretch()
        row.addLayout(col, 1)
        card.add(layout=row)
        self.body.addWidget(card)

        tech = Card("Tecnologia e segurança")
        txt = label("", wrap=True)
        txt.setTextFormat(Qt.TextFormat.RichText)
        try:
            from PySide6 import __version__ as qt_ver
        except ImportError:  # pragma: no cover
            qt_ver = "?"
        from importlib.metadata import version as _pkg_version

        import cryptography
        import numpy
        import PIL

        txt.setText(
            "<b>Esteganografia:</b> LSB em canais RGB, 1–3 bits por canal, distribuição "
            "sequencial ou dispersa (pseudoaleatória derivada da senha via SHA-256).<br>"
            "<b>Criptografia:</b> AES-256-GCM (autenticada; cabeçalho como dado adicional).<br>"
            "<b>Derivação de chave:</b> Argon2id com sal aleatório de 128 bits.<br>"
            "<b>Integridade:</b> SHA-256 do conteúdo original verificado em toda recuperação.<br>"
            "<b>Privacidade:</b> processamento 100% local e offline; sem telemetria; histórico "
            "e relatórios sem senhas nem conteúdos.<br><br>"
            f"Python {platform.python_version()} · PySide6 {qt_ver} · Pillow {PIL.__version__} · "
            f"NumPy {numpy.__version__} · cryptography {cryptography.__version__} · "
            f"argon2-cffi {_pkg_version('argon2-cffi')} · SQLite<br>"
            f"Sistema: {platform.system()} {platform.release()} ({platform.machine()}) · "
            f"{'executável' if getattr(sys, 'frozen', False) else 'código-fonte'}"
        )
        tech.add(txt)
        self.body.addWidget(tech)
        self.body.addStretch()
