"""Histórico, relatórios e gerenciamento de arquivos."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ...core import crypto, imageio, stego
from ...core.errors import MarxSecretError
from ...data.database import OPERATION_LABELS
from ...reports import csv_report, pdf_report
from ..widgets import Card, Page, PathSelector, button, confirm, fmt_bytes, label
from ..worker import run_task

HISTORY_COLUMNS = ["#", "Data/Hora", "Operação", "Status", "Entrada", "Saída", "Tamanho",
                   "Cripto", "Duração", "Observação"]


def _table(cols: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setSortingEnabled(True)
    return t


class HistoryPage(Page):
    key = "history"
    title = "Histórico de operações"
    subtitle = ("Registro local de todas as operações. Senhas e conteúdos secretos nunca são "
                "armazenados.")
    icon_name = "history"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        filters = Card()
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar por arquivo ou observação…")
        self.search.textChanged.connect(self.refresh)
        row.addWidget(self.search, 2)
        self.op_filter = QComboBox()
        self.op_filter.addItem("Todas as operações", "")
        for k, v in OPERATION_LABELS.items():
            self.op_filter.addItem(v, k)
        self.op_filter.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.op_filter, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        self.status_filter.addItem("Sucesso", "sucesso")
        self.status_filter.addItem("Falha", "falha")
        self.status_filter.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.status_filter, 1)
        filters.add(layout=row)
        self.body.addWidget(filters)

        card = Card()
        self.count = label("", "Hint")
        card.add(self.count)
        self.table = _table(HISTORY_COLUMNS)
        self.table.setMinimumHeight(420)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        card.add(self.table)
        brow = QHBoxLayout()
        brow.addWidget(button("Atualizar", "refresh", on_click=self.refresh))
        brow.addWidget(button("Exportar CSV", "csv", on_click=self.export_csv))
        brow.addWidget(button("Exportar PDF", "pdf", on_click=self.export_pdf))
        brow.addStretch()
        brow.addWidget(button("Excluir selecionado", "trash", on_click=self.delete_selected))
        brow.addWidget(button("Limpar histórico", "trash", obj="Danger", on_click=self.clear))
        card.add(layout=brow)
        self.body.addWidget(card)
        self.records = []
        ctx.history_changed.connect(self.refresh)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.records = self.ctx.db.list_operations(
            operation=self.op_filter.currentData() or None,
            status=self.status_filter.currentData() or None,
            search=self.search.text().strip() or None,
        )
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.records))
        p = self.ctx.palette
        for i, r in enumerate(self.records):
            vals = [r.id, r.timestamp.replace("T", " "), r.operation_label, r.status_label,
                    r.input_path, r.output_path,
                    fmt_bytes(r.payload_size) if r.payload_size else "—",
                    "Sim" if r.encrypted else "Não", f"{r.duration_ms} ms", r.message]
            for j, v in enumerate(vals):
                it = QTableWidgetItem()
                if j == 0:
                    it.setData(Qt.ItemDataRole.DisplayRole, int(v))
                else:
                    it.setText(str(v))
                if j == 3:
                    from PySide6.QtGui import QColor

                    it.setForeground(QColor(p.accent if r.status == "sucesso" else p.danger))
                if j in (4, 5):
                    it.setToolTip(str(v))
                self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        for c in (4, 5):
            self.table.setColumnWidth(c, min(self.table.columnWidth(c), 260))
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self.count.setText(f"{len(self.records)} registro(s)")

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.DisplayRole)) if item else None

    def delete_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            self.error("Selecione um registro.")
            return
        self.ctx.db.delete_operation(rid)
        self.ctx.notify_history()

    def clear(self) -> None:
        if confirm(self, "Limpar histórico",
                   "Todos os registros serão removidos permanentemente. Continuar?"):
            n = self.ctx.db.clear_history()
            self.ctx.notify_history()
            self.toast(f"{n} registro(s) removido(s).")

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar histórico (CSV)",
            str(self.ctx.output_dir() / f"historico_{date.today():%Y%m%d}.csv"), "CSV (*.csv)")
        if path:
            csv_report.export_history_csv(self.records, path)
            self.ctx.service.log_report(path, "Histórico (CSV)")
            self.ctx.notify_history()
            self.toast("Histórico exportado em CSV.")

    def export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar histórico (PDF)",
            str(self.ctx.output_dir() / f"historico_{date.today():%Y%m%d}.pdf"), "PDF (*.pdf)")
        if path:
            pdf_report.history_report_pdf(self.records, self.ctx.db.statistics(), path,
                                          "Filtro atual do histórico")
            self.ctx.service.log_report(path, "Histórico (PDF)")
            self.ctx.notify_history()
            self.toast("Relatório PDF gerado.")


class ReportsPage(Page):
    key = "reports"
    title = "Relatórios"
    subtitle = ("Gere relatórios técnicos em PDF e CSV por período. Relatórios de análise e "
                "comparação são gerados nas respectivas telas.")
    icon_name = "report"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        card = Card("Relatório de operações por período")
        row = QHBoxLayout()
        row.addWidget(label("De:"))
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        row.addWidget(self.date_from)
        row.addWidget(label("Até:"))
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        row.addWidget(self.date_to)
        self.all_period = QCheckBox("Todo o período")
        row.addWidget(self.all_period)
        row.addStretch()
        card.add(layout=row)
        row2 = QHBoxLayout()
        row2.addWidget(label("Tipo:"))
        self.op_filter = QComboBox()
        self.op_filter.addItem("Todas as operações", "")
        for k, v in OPERATION_LABELS.items():
            self.op_filter.addItem(v, k)
        row2.addWidget(self.op_filter)
        row2.addStretch()
        card.add(layout=row2)
        card.add(label("Destino", "SectionTitle"))
        self.dest = PathSelector("dir", placeholder="Pasta de destino",
                                 default_dir=ctx.output_dir)
        self.dest.set_path(str(ctx.output_dir()))
        card.add(self.dest)
        brow = QHBoxLayout()
        brow.addWidget(button("Gerar PDF", "pdf", obj="Primary", on_click=self.make_pdf))
        brow.addWidget(button("Gerar CSV", "csv", on_click=self.make_csv))
        brow.addWidget(button("Abrir pasta", "folder", on_click=self._open_dest))
        brow.addStretch()
        card.add(layout=brow)
        self.status = label("", "Hint", wrap=True)
        card.add(self.status)
        self.body.addWidget(card)
        note = Card("Privacidade dos relatórios")
        note.add(label("Os relatórios contêm apenas metadados técnicos: data, tipo de operação, "
                       "caminhos, tamanhos, parâmetros e hashes SHA-256. Senhas, chaves, "
                       "mensagens e nomes de arquivos ocultos jamais são incluídos.", wrap=True))
        self.body.addWidget(note)
        self.body.addStretch()

    def _period(self) -> tuple[str | None, str | None, str]:
        if self.all_period.isChecked():
            return None, None, "Todo o período"
        a = self.date_from.date().toString("yyyy-MM-dd")
        b = self.date_to.date().toString("yyyy-MM-dd")
        return a, b, (f"{self.date_from.date().toString('dd/MM/yyyy')} a "
                      f"{self.date_to.date().toString('dd/MM/yyyy')}")

    def _records(self):
        a, b, label_ = self._period()
        recs = self.ctx.db.list_operations(operation=self.op_filter.currentData() or None,
                                           date_from=a, date_to=b)
        return recs, label_

    def _dest_file(self, ext: str) -> Path | None:
        d = self.dest.path()
        if not d or not os.path.isdir(d):
            self.error("Selecione uma pasta de destino válida.")
            return None
        return Path(d) / f"MARX_SECRET_relatorio_{datetime.now():%Y%m%d_%H%M%S}.{ext}"

    @staticmethod
    def _stats(recs) -> dict:
        total = len(recs)
        ok = sum(1 for r in recs if r.status == "sucesso")
        by_op: dict[str, int] = {}
        hidden = 0
        for r in recs:
            if r.status == "sucesso":
                by_op[r.operation] = by_op.get(r.operation, 0) + 1
                if r.operation in ("ocultar_mensagem", "ocultar_arquivo"):
                    hidden += r.payload_size
        return {"total": total, "success": ok, "failure": total - ok,
                "success_rate": ok / total * 100 if total else 0.0, "by_operation": by_op,
                "hidden_bytes": hidden}

    def make_pdf(self) -> Path | None:
        out = self._dest_file("pdf")
        if not out:
            return None
        recs, period = self._records()
        try:
            pdf_report.history_report_pdf(recs, self._stats(recs), out, period)
        except OSError as exc:
            self.error(f"Não foi possível gerar o PDF: {exc}")
            return None
        self.ctx.service.log_report(str(out), "Relatório de operações (PDF)")
        self.ctx.notify_history()
        self.status.setText(f"PDF gerado: {out}")
        self.toast("Relatório PDF gerado.")
        return out

    def make_csv(self) -> Path | None:
        out = self._dest_file("csv")
        if not out:
            return None
        recs, _ = self._records()
        try:
            csv_report.export_history_csv(recs, out)
        except OSError as exc:
            self.error(f"Não foi possível gerar o CSV: {exc}")
            return None
        self.ctx.service.log_report(str(out), "Relatório de operações (CSV)")
        self.ctx.notify_history()
        self.status.setText(f"CSV gerado: {out}")
        self.toast("Relatório CSV gerado.")
        return out

    def _open_dest(self) -> None:
        if self.dest.path():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.dest.path()))


class FilesPage(Page):
    key = "files"
    title = "Gerenciamento de arquivos"
    subtitle = ("Navegue pelos arquivos de uma pasta, identifique imagens com conteúdo MARX "
                "SECRET, verifique hashes e exclua arquivos com segurança.")
    icon_name = "folder"

    COLS = ["Nome", "Tipo", "Tamanho", "Modificado", "MARX SECRET"]

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        top = Card()
        self.folder = PathSelector("dir", placeholder="Pasta", default_dir=ctx.output_dir)
        self.folder.set_path(str(ctx.output_dir()))
        self.folder.changed.connect(lambda _: self.refresh())
        top.add(self.folder)
        self.body.addWidget(top)
        card = Card()
        self.info = label("", "Hint")
        card.add(self.info)
        self.table = _table(self.COLS)
        self.table.setMinimumHeight(380)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda _: self.open_selected())
        card.add(self.table)
        brow = QHBoxLayout()
        brow.addWidget(button("Atualizar", "refresh", on_click=self.refresh))
        brow.addWidget(button("Abrir", "external", on_click=self.open_selected))
        brow.addWidget(button("Analisar", "analysis", on_click=self.analyze_selected))
        brow.addWidget(button("Copiar SHA-256", "hash", on_click=self.hash_selected))
        brow.addStretch()
        brow.addWidget(button("Exclusão segura", "trash", obj="Danger",
                              on_click=self.secure_delete_selected))
        card.add(layout=brow)
        card.add(label("A exclusão segura sobrescreve o arquivo antes de removê-lo. Em SSDs e "
                       "sistemas com cópias de sombra a eliminação física não pode ser garantida.",
                       "Hint", wrap=True))
        self.body.addWidget(card)
        self.body.addStretch()
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        d = self.folder.path()
        self.table.setSortingEnabled(False)
        if not d or not os.path.isdir(d):
            self.table.setRowCount(0)
            self.info.setText("Pasta inválida.")
            return
        entries = sorted((e for e in os.scandir(d) if e.is_file()), key=lambda e: e.name.lower())
        self.table.setRowCount(len(entries))
        marx = 0
        for i, e in enumerate(entries):
            st = e.stat()
            ext = Path(e.name).suffix.lower()
            flag = "—"
            if ext in imageio.SUPPORTED_OUTPUT_EXT and st.st_size < 60 * 1024 * 1024:
                try:
                    if stego.has_signature(imageio.load_image(e.path)):
                        flag = "Contém conteúdo"
                        marx += 1
                except MarxSecretError:
                    flag = "Imagem inválida"
            elif ext == ".mxs":
                flag = "Arquivo criptografado"
            vals = [e.name, ext.lstrip(".").upper() or "—", fmt_bytes(st.st_size),
                    datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"), flag]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, e.path)
                self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)
        self.info.setText(f"{len(entries)} arquivo(s) · {marx} imagem(ns) com conteúdo MARX SECRET")

    def selected_path(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def open_selected(self) -> None:
        p = self.selected_path()
        if p:
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def analyze_selected(self) -> None:
        p = self.selected_path()
        if not p:
            self.error("Selecione um arquivo.")
            return
        self.ctx.navigate.emit("analysis")
        self.ctx.request_analysis.emit(p)

    def hash_selected(self) -> None:
        p = self.selected_path()
        if not p:
            self.error("Selecione um arquivo.")
            return
        from PySide6.QtGui import QGuiApplication

        def done(h):
            QGuiApplication.clipboard().setText(h)
            self.toast(f"SHA-256 copiado: {h[:16]}…")

        run_task(lambda: crypto.sha256_file(p), done, self.error)

    def secure_delete_selected(self) -> None:
        p = self.selected_path()
        if not p:
            self.error("Selecione um arquivo.")
            return
        if self.ctx.setting("confirm_secure_delete") and not confirm(
            self, "Exclusão segura",
            f"O arquivo será sobrescrito e excluído permanentemente:\n{p}\n\nContinuar?"):
            return
        passes = int(self.ctx.setting("secure_delete_passes"))

        def done(_):
            self.ctx.notify_history()
            self.refresh()
            self.toast("Arquivo excluído com segurança.")

        def fail(msg):
            self.ctx.notify_history()
            self.error(msg)

        run_task(lambda: self.ctx.service.secure_delete(p, passes), done, fail)
