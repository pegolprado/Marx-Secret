"""Páginas de ocultação e extração (mensagens e arquivos)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ...core import imageio, stego
from ...core.errors import MarxSecretError
from ...core.payload import Payload, PayloadKind
from ...services.operations import container_overhead
from ..widgets import (
    CapacityMeter,
    Card,
    ImageDropZone,
    Page,
    PasswordField,
    PathSelector,
    button,
    fmt_bytes,
    label,
)
from ..worker import run_task

BPC_LABELS = {
    1: "1 bit por canal – máxima discrição (recomendado)",
    2: "2 bits por canal – dobro da capacidade",
    3: "3 bits por canal – capacidade máxima, mais detectável",
}


def open_folder(path: str | Path) -> None:
    p = Path(path)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p if p.is_dir() else p.parent)))


def busy_bar() -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setFixedHeight(6)
    bar.setTextVisible(False)
    bar.hide()
    return bar


class HidePage(Page):
    kind = PayloadKind.TEXT

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(0, 5)
        grid.setColumnStretch(1, 6)

        # --- imagem portadora
        self.cover = ImageDropZone("Imagem portadora")
        self.cover.path_changed.connect(self._cover_changed)
        cover_card = Card()
        cover_card.add(self.cover)
        self.lossy_hint = label("", "BadgeWarning")
        self.lossy_hint.hide()
        cover_card.add(self.lossy_hint)
        grid.addWidget(cover_card, 0, 0, 2, 1)

        # --- conteúdo
        content = Card("Conteúdo a ocultar")
        if self.kind == PayloadKind.TEXT:
            self.message = QPlainTextEdit()
            self.message.setPlaceholderText("Digite a mensagem secreta…")
            self.message.setMinimumHeight(140)
            self.message.textChanged.connect(self._refresh)
            content.add(self.message)
            self.counter = label("0 caracteres · 0 B", "Hint")
            content.add(self.counter)
        else:
            self.secret_file = PathSelector("open", "Todos os arquivos (*)",
                                            "Selecione o arquivo a ocultar")
            self.secret_file.changed.connect(self._refresh)
            content.add(self.secret_file)
            self.counter = label("Nenhum arquivo selecionado", "Hint")
            content.add(self.counter)
        grid.addWidget(content, 0, 1)

        # --- proteção
        prot = Card("Proteção", "Criptografia AES-256-GCM com chave derivada por Argon2id.")
        self.encrypt = QCheckBox("Criptografar com senha (AES-256-GCM)")
        self.encrypt.setChecked(True)
        self.encrypt.toggled.connect(self._refresh)
        prot.add(self.encrypt)
        self.password = PasswordField(with_confirm=True, with_generator=True)
        self.password.changed.connect(self._refresh)
        prot.add(self.password)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.bpc = QComboBox()
        for k, v in BPC_LABELS.items():
            self.bpc.addItem(v, k)
        self.bpc.currentIndexChanged.connect(self._refresh)
        form.addRow("Densidade:", self.bpc)
        self.scattered = QCheckBox("Distribuição dispersa guiada pela senha")
        self.scattered.setToolTip("Espalha os bits em posições pseudoaleatórias derivadas da "
                                  "senha, dificultando a detecção estatística.")
        self.compress = QCheckBox("Comprimir conteúdo antes de ocultar")
        form.addRow("", self.scattered)
        form.addRow("", self.compress)
        prot.add(layout=form)
        grid.addWidget(prot, 1, 1)
        self.body.addLayout(grid)

        # --- saída
        out = Card("Saída")
        self.output = PathSelector("save", imageio.OUTPUT_FILTER,
                                   "Arquivo de saída (.png, .bmp ou .tiff)",
                                   default_dir=ctx.output_dir)
        out.add(self.output)
        self.meter = CapacityMeter()
        out.add(self.meter)
        row = QHBoxLayout()
        self.status = label("", "Hint", wrap=True)
        row.addWidget(self.status, 1)
        action_text = "Ocultar mensagem" if self.kind == PayloadKind.TEXT else "Ocultar arquivo"
        self.run_btn = button(action_text, "hide", obj="Primary", on_click=self.run)
        row.addWidget(self.run_btn)
        out.add(layout=row)
        self.busy = busy_bar()
        out.add(self.busy)
        self.body.addWidget(out)

        # --- resultado
        self.result = Card("Resultado")
        self.result_text = label("", wrap=True)
        self.result_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result.add(self.result_text)
        rrow = QHBoxLayout()
        rrow.addWidget(button("Abrir pasta", "folder", on_click=self._open_output))
        rrow.addWidget(button("Comparar com original", "compare", on_click=self._compare))
        rrow.addWidget(button("Copiar SHA-256", "hash", on_click=self._copy_hash))
        rrow.addStretch()
        self.result.add(layout=rrow)
        self.result.hide()
        self.body.addWidget(self.result)
        self.body.addStretch()
        self._last = None
        self.apply_settings()
        ctx.settings_changed.connect(self.apply_settings)

    # ------------------------------------------------------------------
    def apply_settings(self) -> None:
        bpc = int(self.ctx.setting("bits_per_channel") or 1)
        idx = self.bpc.findData(bpc)
        if idx >= 0:
            self.bpc.setCurrentIndex(idx)
        self.scattered.setChecked(bool(self.ctx.setting("scattered")))
        self.compress.setChecked(bool(self.ctx.setting("compress")))
        require = bool(self.ctx.setting("require_password"))
        if require:
            self.encrypt.setChecked(True)
        self.encrypt.setEnabled(not require)
        self.encrypt.setToolTip("A senha é obrigatória (altere em Configurações)." if require
                                else "")
        self._refresh()

    def _cover_changed(self, path: str) -> None:
        if path:
            stem = Path(path).stem
            self.output.set_path(str(self.ctx.output_dir() / f"{stem}_marx.png"))
            lossy = imageio.is_lossy_input(path)
            self.lossy_hint.setText("Imagem com compressão com perdas: a saída será gravada em "
                                    "formato sem perdas (PNG/BMP/TIFF).")
            self.lossy_hint.setWordWrap(True)
            self.lossy_hint.setVisible(lossy)
        else:
            self.lossy_hint.hide()
        self._refresh()

    def _payload_size(self) -> tuple[int, str]:
        if self.kind == PayloadKind.TEXT:
            n = len(self.message.toPlainText().encode("utf-8"))
            self.counter.setText(f"{len(self.message.toPlainText())} caracteres · {fmt_bytes(n)}")
            return n, ""
        p = self.secret_file.path()
        if p and os.path.isfile(p):
            size = os.path.getsize(p)
            self.counter.setText(f"{Path(p).name} · {fmt_bytes(size)}")
            return size, Path(p).name
        self.counter.setText("Nenhum arquivo selecionado" if not p else "Arquivo não encontrado")
        return 0, ""

    def _refresh(self) -> None:
        encrypted = self.encrypt.isChecked()
        self.password.setEnabled(encrypted)
        self.scattered.setEnabled(encrypted)
        size, name = self._payload_size()
        cover = self.cover.path()
        if cover:
            try:
                info = imageio.image_info(cover)
                cap = stego.capacity_for_size(info.width, info.height, self.bpc.currentData())
                self.meter.set_usage(size + container_overhead(encrypted, name), cap)
            except MarxSecretError:
                self.meter.reset()
        else:
            self.meter.reset()

    def _validate(self) -> str | None:
        if not self.cover.path():
            return "Selecione a imagem portadora."
        if self.kind == PayloadKind.TEXT and not self.message.toPlainText():
            return "Digite a mensagem a ocultar."
        if self.kind == PayloadKind.FILE and not os.path.isfile(self.secret_file.path()):
            return "Selecione um arquivo válido para ocultar."
        if not self.output.path():
            return "Informe o arquivo de saída."
        if self.encrypt.isChecked():
            if not self.password.password():
                return "Informe a senha."
            if not self.password.matches():
                return "A confirmação da senha não confere."
        if Path(self.output.path()).exists() and not _confirm_overwrite(self, self.output.path()):
            return ""
        return None

    def run(self) -> None:
        problem = self._validate()
        if problem is not None:
            if problem:
                self.error(problem)
            return
        pwd = self.password.password() if self.encrypt.isChecked() else None
        opts = self.ctx.hide_options(pwd, self.bpc.currentData(), self.scattered.isChecked(),
                                     self.compress.isChecked())
        cover, out = self.cover.path(), self.output.path()
        svc = self.ctx.service
        if self.kind == PayloadKind.TEXT:
            message = self.message.toPlainText()
            fn = lambda: svc.hide_message(cover, out, message, opts)  # noqa: E731
        else:
            secret = self.secret_file.path()
            fn = lambda: svc.hide_file(cover, out, secret, opts)  # noqa: E731
        self._set_busy(True)
        run_task(fn, self._done, self._failed)

    def _set_busy(self, busy: bool) -> None:
        self.run_btn.setEnabled(not busy)
        self.busy.setVisible(busy)
        self.status.setText("Derivando chave (Argon2id), criptografando e ocultando…" if busy
                            else "")

    def _done(self, res) -> None:
        self._set_busy(False)
        self._last = res
        self.ctx.notify_history()
        self.result_text.setText(
            f"<b>Conteúdo ocultado com sucesso.</b><br>"
            f"Arquivo: {res.output_path}<br>"
            f"Conteúdo: {fmt_bytes(res.payload_size)} · contêiner {fmt_bytes(res.container_size)}"
            f" · uso {res.usage_pct:.2f}% da capacidade<br>"
            f"Criptografia: {'AES-256-GCM + Argon2id' if res.encrypted else 'não'} · "
            f"Compressão: {'sim' if res.compressed else 'não'} · "
            f"{res.bits_per_channel} bit(s)/canal · "
            f"{'dispersa' if res.scattered else 'sequencial'}<br>"
            f"SHA-256 da imagem: <code>{res.output_sha256}</code><br>"
            f"Verificação pós-gravação: aprovada · {res.duration_ms} ms"
        )
        self.result.show()
        self.password.clear()
        if self.kind == PayloadKind.TEXT:
            self.message.clear()
        self.toast("Conteúdo ocultado e verificado com sucesso.")

    def _failed(self, msg: str) -> None:
        self._set_busy(False)
        self.ctx.notify_history()
        self.error(msg)

    def _open_output(self) -> None:
        if self._last:
            open_folder(self._last.output_path)

    def _compare(self) -> None:
        if self._last and self.cover.path():
            self.ctx.request_compare.emit(self.cover.path(), self._last.output_path)

    def _copy_hash(self) -> None:
        if self._last:
            QGuiApplication.clipboard().setText(self._last.output_sha256)
            self.toast("SHA-256 copiado.")


class HideMessagePage(HidePage):
    key = "hide_message"
    title = "Ocultar mensagem"
    subtitle = "Oculte uma mensagem de texto em uma imagem, protegida por AES-256-GCM."
    icon_name = "hide"
    kind = PayloadKind.TEXT


class HideFilePage(HidePage):
    key = "hide_file"
    title = "Ocultar arquivo"
    subtitle = "Oculte qualquer arquivo (documentos, planilhas, compactados…) dentro de uma imagem."
    icon_name = "file_hide"
    kind = PayloadKind.FILE


def _confirm_overwrite(parent, path: str) -> bool:
    from ..widgets import confirm

    return confirm(parent, "Substituir arquivo", f"O arquivo já existe:\n{path}\n\nSubstituir?")


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

class ExtractPage(Page):
    kind = PayloadKind.TEXT

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setColumnStretch(0, 5)
        grid.setColumnStretch(1, 6)
        left = Card()
        self.image = ImageDropZone("Imagem com conteúdo oculto")
        self.image.path_changed.connect(self._image_changed)
        left.add(self.image)
        self.signature = label("", "Badge")
        self.signature.hide()
        left.add(self.signature)
        grid.addWidget(left, 0, 0)

        right = QVBoxLayout()
        right.setSpacing(18)
        auth = Card("Autenticação", "Informe a senha usada na ocultação (se houver).")
        self.password = PasswordField(with_meter=False)
        self.password.edit.returnPressed.connect(self.run)
        auth.add(self.password)
        row = QHBoxLayout()
        self.status = label("", "Hint", wrap=True)
        row.addWidget(self.status, 1)
        text = "Extrair mensagem" if self.kind == PayloadKind.TEXT else "Recuperar arquivo"
        self.run_btn = button(text, "reveal", obj="Primary", on_click=self.run)
        row.addWidget(self.run_btn)
        auth.add(layout=row)
        self.busy = busy_bar()
        auth.add(self.busy)
        right.addWidget(auth)

        # resultado: texto
        self.text_card = Card("Mensagem recuperada")
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setMinimumHeight(160)
        self.text_card.add(self.text_view)
        trow = QHBoxLayout()
        trow.addWidget(button("Copiar", "copy", on_click=self._copy_text))
        trow.addWidget(button("Salvar como .txt", "save", on_click=self._save_text))
        trow.addWidget(button("Limpar da tela", "trash", on_click=self._clear_result))
        trow.addStretch()
        self.text_card.add(layout=trow)
        self.text_card.hide()
        right.addWidget(self.text_card)

        # resultado: arquivo
        self.file_card = Card("Arquivo recuperado")
        self.file_info = label("", wrap=True)
        self.file_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_card.add(self.file_info)
        self.dest = PathSelector("dir", placeholder="Pasta de destino",
                                 default_dir=ctx.output_dir)
        self.file_card.add(self.dest)
        frow = QHBoxLayout()
        frow.addWidget(button("Salvar arquivo", "save", obj="Primary", on_click=self._save_file))
        frow.addWidget(button("Descartar", "trash", on_click=self._clear_result))
        frow.addStretch()
        self.file_card.add(layout=frow)
        self.file_card.hide()
        right.addWidget(self.file_card)

        self.meta = label("", "Hint", wrap=True)
        right.addWidget(self.meta)
        right.addStretch()
        grid.addLayout(right, 0, 1)
        self.body.addLayout(grid)
        self.body.addStretch()
        self._payload: Payload | None = None
        self._clip_timer = QTimer(self)
        self._clip_timer.setSingleShot(True)
        self._clip_timer.timeout.connect(self._clear_clipboard)
        self._clip_value = ""

    def _image_changed(self, path: str) -> None:
        self._clear_result()
        if not path:
            self.signature.hide()
            return
        try:
            header = stego.read_header(imageio.load_image(path))
            mode = "dispersa – requer senha" if header.layout.scattered else "sequencial"
            self.signature.setObjectName("Badge")
            self.signature.setText(f"Assinatura MARX SECRET detectada · {fmt_bytes(header.length)}"
                                   f" · {header.layout.bits_per_channel} bit(s)/canal · {mode}")
        except MarxSecretError:
            self.signature.setObjectName("BadgeWarning")
            self.signature.setText("Nenhuma assinatura MARX SECRET encontrada nesta imagem.")
        self.signature.setWordWrap(True)
        self.signature.style().unpolish(self.signature)
        self.signature.style().polish(self.signature)
        self.signature.show()

    def run(self) -> None:
        path = self.image.path()
        if not path:
            self.error("Selecione a imagem.")
            return
        pwd = self.password.password() or None
        svc = self.ctx.service
        max_bytes = self.ctx.max_payload_bytes()
        self.run_btn.setEnabled(False)
        self.busy.show()
        self.status.setText("Lendo bits, verificando autenticação e integridade…")
        run_task(lambda: svc.extract(path, pwd, self.kind, max_bytes), self._done, self._failed)

    def _done(self, res) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.status.setText("")
        self.password.clear()
        self.ctx.notify_history()
        self._payload = res.payload
        self.meta.setText(
            f"Integridade SHA-256 verificada ✓ · Criptografia: "
            f"{'AES-256-GCM' if res.encrypted else 'nenhuma'} · "
            f"{res.bits_per_channel} bit(s)/canal · "
            f"{'dispersa' if res.scattered else 'sequencial'} · {res.duration_ms} ms")
        if res.payload.kind == PayloadKind.TEXT:
            self.text_view.setPlainText(res.payload.text)
            self.text_card.show()
            self.file_card.hide()
            if self.kind == PayloadKind.FILE:
                self.toast("A imagem continha uma mensagem de texto.", "warn")
            else:
                self.toast("Mensagem extraída com sucesso.")
        else:
            self.file_info.setText(
                f"<b>{res.payload.filename or 'arquivo_recuperado.bin'}</b><br>"
                f"Tamanho: {fmt_bytes(len(res.payload.data))}<br>"
                f"SHA-256: <code>{res.payload_sha256}</code>")
            if not self.dest.path():
                self.dest.set_path(str(self.ctx.output_dir()))
            self.file_card.show()
            self.text_card.hide()
            if self.kind == PayloadKind.TEXT:
                self.toast("A imagem continha um arquivo.", "warn")
            else:
                self.toast("Arquivo recuperado. Escolha onde salvar.")

    def _failed(self, msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.status.setText("")
        self.ctx.notify_history()
        self.error(msg)

    def _copy_text(self) -> None:
        text = self.text_view.toPlainText()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self._clip_value = text
        secs = int(self.ctx.setting("clear_clipboard_seconds") or 0)
        if secs > 0:
            self._clip_timer.start(secs * 1000)
            self.toast(f"Copiado. A área de transferência será limpa em {secs} s.")
        else:
            self.toast("Copiado para a área de transferência.")

    def _clear_clipboard(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb.text() == self._clip_value:
            cb.clear()
        self._clip_value = ""

    def _save_text(self) -> None:
        if not self._payload:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar mensagem",
                                              str(self.ctx.output_dir() / "mensagem.txt"),
                                              "Texto (*.txt)")
        if path:
            try:
                Path(path).write_text(self.text_view.toPlainText(), encoding="utf-8")
                self.toast("Mensagem salva.")
            except OSError as exc:
                self.error(f"Não foi possível salvar: {exc}")

    def save_file_to(self, directory: str) -> Path | None:
        if not self._payload:
            return None
        try:
            return self.ctx.service.save_payload(self._payload, directory)
        except (MarxSecretError, OSError) as exc:
            self.error(str(exc))
            return None

    def _save_file(self) -> None:
        d = self.dest.path()
        if not d or not os.path.isdir(d):
            self.error("Selecione uma pasta de destino válida.")
            return
        out = self.save_file_to(d)
        if out:
            self.toast(f"Arquivo salvo e verificado: {out.name}")
            open_folder(out)

    def _clear_result(self) -> None:
        self._payload = None
        self.text_view.clear()
        self.text_card.hide()
        self.file_card.hide()
        self.meta.setText("")


class ExtractMessagePage(ExtractPage):
    key = "extract_message"
    title = "Extrair mensagem"
    subtitle = "Recupere mensagens ocultas, com verificação de autenticidade e integridade."
    icon_name = "reveal"
    kind = PayloadKind.TEXT


class RecoverFilePage(ExtractPage):
    key = "recover_file"
    title = "Recuperar arquivo"
    subtitle = "Recupere arquivos ocultos em imagens e salve-os com verificação SHA-256."
    icon_name = "file_recover"
    kind = PayloadKind.FILE
