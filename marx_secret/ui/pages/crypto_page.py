"""Criptografia e proteção por senha: arquivos .mxs, gerador de senhas e hashes."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import crypto, payload
from ..widgets import Card, Page, PasswordField, PathSelector, button, fmt_bytes, label
from ..worker import run_task
from .stego_pages import busy_bar, open_folder


class CryptoPage(Page):
    key = "crypto"
    title = "Criptografia e senhas"
    subtitle = ("Criptografe arquivos com AES-256-GCM (formato .mxs), gere senhas fortes e "
                "verifique hashes SHA-256.")
    icon_name = "lock"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        tabs = QTabWidget()
        tabs.addTab(self._encrypt_tab(), "Criptografar arquivo")
        tabs.addTab(self._decrypt_tab(), "Descriptografar arquivo")
        tabs.addTab(self._password_tab(), "Gerador de senhas")
        tabs.addTab(self._hash_tab(), "Hash SHA-256")
        self.tabs = tabs
        self.body.addWidget(tabs)
        self.body.addStretch()

    # ------------------------------------------------------------------
    def _encrypt_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.addWidget(label("Arquivo de origem", "SectionTitle"))
        self.enc_src = PathSelector("open", placeholder="Arquivo a criptografar")
        self.enc_src.changed.connect(self._suggest_enc_dst)
        lay.addWidget(self.enc_src)
        lay.addWidget(label("Destino (.mxs)", "SectionTitle"))
        self.enc_dst = PathSelector("save", "Arquivo MARX SECRET (*.mxs)",
                                    "Arquivo criptografado de saída")
        lay.addWidget(self.enc_dst)
        lay.addWidget(label("Senha", "SectionTitle"))
        self.enc_pwd = PasswordField(with_confirm=True, with_generator=True)
        lay.addWidget(self.enc_pwd)
        self.enc_compress = QCheckBox("Comprimir antes de criptografar")
        self.enc_compress.setChecked(True)
        lay.addWidget(self.enc_compress)
        self.enc_wipe = QCheckBox("Excluir o original com segurança após criptografar")
        lay.addWidget(self.enc_wipe)
        row = QHBoxLayout()
        self.enc_status = label("", "Hint", wrap=True)
        row.addWidget(self.enc_status, 1)
        self.enc_btn = button("Criptografar", "lock", obj="Primary", on_click=self.encrypt)
        row.addWidget(self.enc_btn)
        lay.addLayout(row)
        self.enc_busy = busy_bar()
        lay.addWidget(self.enc_busy)
        return w

    def _suggest_enc_dst(self, src: str) -> None:
        if src and not self.enc_dst.path():
            self.enc_dst.set_path(src + payload.ENCRYPTED_FILE_EXT)

    def encrypt(self) -> None:
        src, dst, pwd = self.enc_src.path(), self.enc_dst.path(), self.enc_pwd.password()
        if not os.path.isfile(src):
            self.error("Selecione um arquivo de origem válido.")
            return
        if not dst:
            self.error("Informe o arquivo de destino.")
            return
        if not pwd:
            self.error("Informe a senha.")
            return
        if not self.enc_pwd.matches():
            self.error("A confirmação da senha não confere.")
            return
        svc = self.ctx.service
        profile = self.ctx.setting("kdf_profile")
        compress = self.enc_compress.isChecked()
        wipe = self.enc_wipe.isChecked()
        min_len = int(self.ctx.setting("min_password_length"))
        max_bytes = self.ctx.max_payload_bytes()
        passes = int(self.ctx.setting("secure_delete_passes"))

        def work():
            out = svc.encrypt_file(src, dst, pwd, profile, compress, min_len, max_bytes)
            if wipe:
                svc.secure_delete(src, passes)
            return out

        self.enc_btn.setEnabled(False)
        self.enc_busy.show()
        run_task(work, self._enc_done, self._enc_failed)

    def _enc_done(self, out) -> None:
        self.enc_btn.setEnabled(True)
        self.enc_busy.hide()
        self.enc_pwd.clear()
        self.ctx.notify_history()
        self.enc_status.setText(f"Criptografado: {out} ({fmt_bytes(os.path.getsize(out))})")
        self.toast("Arquivo criptografado com AES-256-GCM.")

    def _enc_failed(self, msg: str) -> None:
        self.enc_btn.setEnabled(True)
        self.enc_busy.hide()
        self.ctx.notify_history()
        self.error(msg)

    # ------------------------------------------------------------------
    def _decrypt_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.addWidget(label("Arquivo criptografado (.mxs)", "SectionTitle"))
        self.dec_src = PathSelector("open", "Arquivo MARX SECRET (*.mxs);;Todos os arquivos (*)",
                                    "Arquivo .mxs")
        lay.addWidget(self.dec_src)
        lay.addWidget(label("Pasta de destino", "SectionTitle"))
        self.dec_dst = PathSelector("dir", placeholder="Pasta onde o arquivo será restaurado",
                                    default_dir=self.ctx.output_dir)
        lay.addWidget(self.dec_dst)
        lay.addWidget(label("Senha", "SectionTitle"))
        self.dec_pwd = PasswordField(with_meter=False)
        lay.addWidget(self.dec_pwd)
        row = QHBoxLayout()
        self.dec_status = label("", "Hint", wrap=True)
        row.addWidget(self.dec_status, 1)
        self.dec_btn = button("Descriptografar", "key", obj="Primary", on_click=self.decrypt)
        row.addWidget(self.dec_btn)
        lay.addLayout(row)
        self.dec_busy = busy_bar()
        lay.addWidget(self.dec_busy)
        return w

    def decrypt(self) -> None:
        src, dst, pwd = self.dec_src.path(), self.dec_dst.path(), self.dec_pwd.password()
        if not os.path.isfile(src):
            self.error("Selecione o arquivo .mxs.")
            return
        if not dst or not os.path.isdir(dst):
            self.error("Selecione uma pasta de destino válida.")
            return
        if not pwd:
            self.error("Informe a senha.")
            return
        svc = self.ctx.service
        max_bytes = self.ctx.max_payload_bytes()
        self.dec_btn.setEnabled(False)
        self.dec_busy.show()
        run_task(lambda: svc.decrypt_file(src, dst, pwd, max_bytes), self._dec_done,
                 self._dec_failed)

    def _dec_done(self, out: Path) -> None:
        self.dec_btn.setEnabled(True)
        self.dec_busy.hide()
        self.dec_pwd.clear()
        self.ctx.notify_history()
        self.dec_status.setText(f"Restaurado e verificado (SHA-256): {out}")
        self.toast("Arquivo descriptografado com sucesso.")
        open_folder(out)

    def _dec_failed(self, msg: str) -> None:
        self.dec_btn.setEnabled(True)
        self.dec_busy.hide()
        self.ctx.notify_history()
        self.error(msg)

    # ------------------------------------------------------------------
    def _password_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(label("Tamanho:"))
        self.gen_len = QSpinBox()
        self.gen_len.setRange(8, 128)
        self.gen_len.setValue(20)
        row.addWidget(self.gen_len)
        self.gen_symbols = QCheckBox("Incluir símbolos")
        self.gen_symbols.setChecked(True)
        row.addWidget(self.gen_symbols)
        row.addStretch()
        lay.addLayout(row)
        self.gen_out = QLineEdit()
        self.gen_out.setReadOnly(True)
        self.gen_out.setStyleSheet("font-family: Consolas, 'DejaVu Sans Mono', monospace; "
                                   "font-size: 13pt;")
        lay.addWidget(self.gen_out)
        self.gen_info = label("", "Hint")
        lay.addWidget(self.gen_info)
        brow = QHBoxLayout()
        brow.addWidget(button("Gerar senha", "dice", obj="Primary", on_click=self.generate))
        brow.addWidget(button("Copiar", "copy", on_click=self._copy_generated))
        brow.addStretch()
        lay.addLayout(brow)
        lay.addSpacing(10)
        lay.addWidget(label("Avaliar uma senha", "SectionTitle"))
        self.eval_pwd = PasswordField()
        lay.addWidget(self.eval_pwd)
        lay.addWidget(label("A avaliação é feita localmente; nenhuma senha é armazenada.", "Hint"))
        lay.addStretch()
        return w

    def generate(self) -> None:
        pwd = crypto.generate_password(self.gen_len.value(), self.gen_symbols.isChecked())
        self.gen_out.setText(pwd)
        s = crypto.evaluate_password(pwd)
        self.gen_info.setText(f"Força: {s.label} · entropia estimada {s.entropy_bits:.0f} bits")

    def _copy_generated(self) -> None:
        if self.gen_out.text():
            QGuiApplication.clipboard().setText(self.gen_out.text())
            self.toast("Senha copiada.")

    # ------------------------------------------------------------------
    def _hash_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.addWidget(label("Arquivo", "SectionTitle"))
        self.hash_src = PathSelector("open", placeholder="Arquivo para calcular o SHA-256")
        lay.addWidget(self.hash_src)
        lay.addWidget(label("Hash esperado (opcional, para verificação)", "SectionTitle"))
        self.hash_expected = QLineEdit()
        self.hash_expected.setPlaceholderText("Cole aqui o SHA-256 esperado")
        lay.addWidget(self.hash_expected)
        self.hash_out = QLineEdit()
        self.hash_out.setReadOnly(True)
        lay.addWidget(self.hash_out)
        self.hash_result = label("", "Hint")
        self.hash_result.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.hash_result)
        brow = QHBoxLayout()
        brow.addWidget(button("Calcular / verificar", "hash", obj="Primary",
                              on_click=self.compute_hash))
        brow.addWidget(button("Copiar hash", "copy", on_click=self._copy_hash))
        brow.addStretch()
        lay.addLayout(brow)
        lay.addStretch()
        return w

    def compute_hash(self) -> None:
        src = self.hash_src.path()
        if not os.path.isfile(src):
            self.error("Selecione um arquivo válido.")
            return
        expected = self.hash_expected.text().strip()
        svc = self.ctx.service

        def work():
            digest = crypto.sha256_file(src)
            ok = svc.verify_integrity(src, expected) if expected else None
            return digest, ok

        run_task(work, self._hash_done, self.error)

    def _hash_done(self, res) -> None:
        digest, ok = res
        self.hash_out.setText(digest)
        p = self.ctx.palette
        if ok is None:
            self.hash_result.setText("SHA-256 calculado.")
        elif ok:
            self.hash_result.setText(f"<span style='color:{p.accent}'><b>✓ Integridade "
                                     f"confirmada: os hashes conferem.</b></span>")
        else:
            self.hash_result.setText(f"<span style='color:{p.danger}'><b>✗ Os hashes NÃO "
                                     f"conferem: o arquivo foi alterado.</b></span>")
        self.ctx.notify_history()

    def _copy_hash(self) -> None:
        if self.hash_out.text():
            QGuiApplication.clipboard().setText(self.hash_out.text())
            self.toast("Hash copiado.")
