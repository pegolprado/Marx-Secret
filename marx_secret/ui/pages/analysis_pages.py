"""Análise estatística e comparação de imagens."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ...core import analysis, compare, imageio
from ...core.errors import MarxSecretError
from ...reports import csv_report, pdf_report
from ..widgets import (
    Card,
    ImageDropZone,
    LineChart,
    Page,
    button,
    fmt_bytes,
    label,
    pil_to_pixmap,
)
from ..worker import run_task
from .stego_pages import busy_bar


def _kv_table(rows: int) -> QTableWidget:
    t = QTableWidget(rows, 2)
    t.horizontalHeader().setVisible(False)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    return t


def _fill_kv(t: QTableWidget, rows: list[tuple[str, str]]) -> None:
    t.setRowCount(len(rows))
    for i, (k, v) in enumerate(rows):
        a = QTableWidgetItem(k)
        f = a.font()
        f.setBold(True)
        a.setFont(f)
        t.setItem(i, 0, a)
        t.setItem(i, 1, QTableWidgetItem(v))
    t.resizeColumnToContents(0)
    t.setFixedHeight(min(40 + 30 * len(rows), 460))


class AnalysisPage(Page):
    key = "analysis"
    title = "Análise estatística"
    subtitle = ("Histogramas, entropia, ataque qui-quadrado, plano LSB e detecção de assinatura "
                "MARX SECRET. Nenhum conteúdo é descriptografado.")
    icon_name = "analysis"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        top = QGridLayout()
        top.setHorizontalSpacing(18)
        top.setColumnStretch(0, 4)
        top.setColumnStretch(1, 6)
        left = Card()
        self.image = ImageDropZone("Imagem a analisar")
        left.add(self.image)
        row = QHBoxLayout()
        self.run_btn = button("Analisar", "analysis", obj="Primary", on_click=self.run)
        row.addStretch()
        row.addWidget(self.run_btn)
        left.add(layout=row)
        self.busy = busy_bar()
        left.add(self.busy)
        top.addWidget(left, 0, 0)

        diag = Card("Diagnóstico")
        self.verdict = label("Selecione uma imagem e clique em Analisar.", "Muted", wrap=True)
        self.verdict.setTextFormat(Qt.TextFormat.RichText)
        diag.add(self.verdict)
        self.summary = _kv_table(0)
        diag.add(self.summary)
        top.addWidget(diag, 0, 1)
        self.body.addLayout(top)

        self.details = QWidget()
        dl = QGridLayout(self.details)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(18)
        ch_card = Card("Estatísticas por canal")
        self.channels = QTableWidget(0, 8)
        self.channels.setHorizontalHeaderLabels(["Canal", "Média", "Desvio", "Mín", "Máx",
                                                 "Entropia", "LSB = 1", "Qui-quadrado"])
        self.channels.verticalHeader().setVisible(False)
        self.channels.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.channels.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.channels.setFixedHeight(130)
        ch_card.add(self.channels)
        dl.addWidget(ch_card, 0, 0, 1, 2)
        self.hist = LineChart("Histograma RGB")
        hcard = Card()
        hcard.add(self.hist)
        dl.addWidget(hcard, 1, 0)
        self.chi = LineChart("Qui-quadrado sequencial (% da imagem × probabilidade)", y_max=100)
        ccard = Card()
        ccard.add(self.chi)
        dl.addWidget(ccard, 1, 1)
        lsb_card = Card("Plano de bits menos significativos (LSB)",
                        "Regiões com aparência de ruído uniforme podem indicar dados ocultos.")
        prow = QHBoxLayout()
        prow.addWidget(label("Canal:"))
        self.lsb_channel = QComboBox()
        self.lsb_channel.addItems(["Combinado", "Vermelho", "Verde", "Azul"])
        self.lsb_channel.currentIndexChanged.connect(self._update_lsb)
        prow.addWidget(self.lsb_channel)
        prow.addStretch()
        lsb_card.add(layout=prow)
        self.lsb_view = QLabel()
        self.lsb_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lsb_view.setMinimumHeight(240)
        lsb_card.add(self.lsb_view)
        dl.addWidget(lsb_card, 2, 0, 1, 2)
        exp = Card("Exportar")
        erow = QHBoxLayout()
        erow.addWidget(button("Relatório PDF", "pdf", obj="Primary", on_click=self.export_pdf))
        erow.addWidget(button("Dados CSV", "csv", on_click=self.export_csv))
        erow.addStretch()
        exp.add(layout=erow)
        dl.addWidget(exp, 3, 0, 1, 2)
        self.details.hide()
        self.body.addWidget(self.details)
        self.body.addStretch()
        self.result: analysis.AnalysisResult | None = None
        self._img = None
        ctx.request_analysis.connect(self.load)

    def load(self, path: str) -> None:
        if self.image.set_path(path):
            self.run()

    def run(self) -> None:
        path = self.image.path()
        if not path:
            self.error("Selecione uma imagem.")
            return
        svc = self.ctx.service
        self.run_btn.setEnabled(False)
        self.busy.show()

        def work():
            r = svc.analyze(path)
            return r, imageio.load_image(path)

        run_task(work, self._done, self._failed)

    def _failed(self, msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.ctx.notify_history()
        self.error(msg)

    def _done(self, res) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.ctx.notify_history()
        r, img = res
        self.result, self._img = r, img
        p = self.ctx.palette
        color = {"Alto": p.danger, "Moderado": p.warning}.get(r.suspicion_label, p.accent)
        self.verdict.setText(
            f"<span style='font-size:15pt; font-weight:800; color:{color}'>Suspeita "
            f"{r.suspicion_label} · {r.suspicion_score}/100</span><br>"
            + "<br>".join(f"• {f}" for f in r.findings))
        sig = r.signature
        rows = [
            ("Arquivo", r.file_name),
            ("Dimensões", f"{r.width} × {r.height} px ({r.megapixels:.2f} MP)"),
            ("Formato / modo", f"{r.source_format} / {r.mode}"),
            ("Tamanho", fmt_bytes(r.file_size)),
            ("SHA-256", r.file_sha256),
            ("Capacidade (1/2/3 bits)", " / ".join(fmt_bytes(r.capacity[b]) for b in (1, 2, 3))),
            ("Qui-quadrado global", f"{r.chi_square_overall * 100:.2f}%"),
            ("Assinatura MARX SECRET", "Detectada" if sig.detected else "Não detectada"),
        ]
        if sig.detected:
            rows += [
                ("Dados armazenados", fmt_bytes(sig.stored_bytes or 0)),
                ("Layout", f"{sig.bits_per_channel} bit(s)/canal · "
                           f"{'dispersa' if sig.scattered else 'sequencial'}"),
                ("Criptografia", "AES-256-GCM" if sig.encrypted else
                 ("Não" if sig.encrypted is not None else "—")),
            ]
            if sig.kdf:
                rows.append(("Derivação de chave", sig.kdf))
        _fill_kv(self.summary, rows)
        self.channels.setRowCount(3)
        for i, c in enumerate(r.channels):
            vals = [c.name, f"{c.mean:.2f}", f"{c.std:.2f}", str(c.minimum), str(c.maximum),
                    f"{c.entropy:.4f}", f"{c.lsb_ones_ratio * 100:.2f}%",
                    f"{c.chi_square_probability * 100:.2f}%"]
            for j, v in enumerate(vals):
                self.channels.setItem(i, j, QTableWidgetItem(v))
        xs = np.arange(256)
        self.hist.set_series([(np.column_stack([xs, r.histograms[i]]), col)
                              for i, col in enumerate(("#EF4444", "#10B981", "#3B82F6"))],
                             (0, 255))
        seq = np.array([(pct, prob * 100) for pct, prob in r.chi_square_sequence], dtype=float)
        self.chi.set_series([(seq, p.accent)], (5, 100))
        self._update_lsb()
        self.details.show()
        self.toast("Análise concluída.")

    def _lsb_image(self):
        if self._img is None:
            return None
        idx = self.lsb_channel.currentIndex()
        return analysis.lsb_plane(self._img, None if idx == 0 else idx - 1)

    def _update_lsb(self) -> None:
        img = self._lsb_image()
        if img is None:
            return
        preview = img.copy()
        preview.thumbnail((900, 360))
        self.lsb_view.setPixmap(pil_to_pixmap(preview))

    def export_pdf(self) -> None:
        if not self.result:
            return
        default = str(self.ctx.output_dir() / f"analise_{Path(self.result.file_name).stem}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Salvar relatório PDF", default, "PDF (*.pdf)")
        if path:
            self.save_pdf(path)

    def save_pdf(self, path: str) -> None:
        try:
            pdf_report.analysis_report_pdf(self.result, path, self._lsb_image())
            self.ctx.service.log_report(path, "Relatório de análise (PDF)")
            self.ctx.notify_history()
            self.toast("Relatório PDF gerado.")
        except (OSError, MarxSecretError) as exc:
            self.error(f"Não foi possível gerar o relatório: {exc}")

    def export_csv(self) -> None:
        if not self.result:
            return
        default = str(self.ctx.output_dir() / f"analise_{Path(self.result.file_name).stem}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", default, "CSV (*.csv)")
        if path:
            try:
                csv_report.export_analysis_csv(self.result, path)
                self.ctx.service.log_report(path, "Dados de análise (CSV)")
                self.ctx.notify_history()
                self.toast("CSV exportado.")
            except OSError as exc:
                self.error(f"Não foi possível exportar: {exc}")


class ComparePage(Page):
    key = "compare"
    title = "Comparação de imagens"
    subtitle = ("Compare a imagem original com a processada: PSNR, SSIM, MSE, pixels alterados "
                "e mapa de diferenças.")
    icon_name = "compare"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        self.original = ImageDropZone("Imagem original")
        self.processed = ImageDropZone("Imagem processada")
        c1, c2 = Card(), Card()
        c1.add(self.original)
        c2.add(self.processed)
        grid.addWidget(c1, 0, 0)
        grid.addWidget(c2, 0, 1)
        self.body.addLayout(grid)
        row = QHBoxLayout()
        row.addStretch()
        self.run_btn = button("Comparar", "compare", obj="Primary", on_click=self.run)
        row.addWidget(self.run_btn)
        self.body.addLayout(row)
        self.busy = busy_bar()
        self.body.addWidget(self.busy)

        self.results = QWidget()
        rl = QGridLayout(self.results)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(18)
        metrics = Card("Métricas")
        self.verdict = label("", wrap=True)
        self.verdict.setTextFormat(Qt.TextFormat.RichText)
        metrics.add(self.verdict)
        self.metrics = _kv_table(0)
        metrics.add(self.metrics)
        rl.addWidget(metrics, 0, 0)
        diff_card = Card("Mapa de diferenças (amplificado)",
                         "Pixels alterados aparecem em verde; quanto mais claro, maior a alteração.")
        self.diff_view = QLabel()
        self.diff_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diff_view.setMinimumHeight(260)
        diff_card.add(self.diff_view)
        rl.addWidget(diff_card, 0, 1)
        exp = Card("Exportar")
        erow = QHBoxLayout()
        erow.addWidget(button("Relatório PDF", "pdf", obj="Primary", on_click=self.export_pdf))
        erow.addWidget(button("Dados CSV", "csv", on_click=self.export_csv))
        erow.addStretch()
        exp.add(layout=erow)
        rl.addWidget(exp, 1, 0, 1, 2)
        self.results.hide()
        self.body.addWidget(self.results)
        self.body.addStretch()
        self.result: compare.ComparisonResult | None = None
        self._diff = None
        ctx.request_compare.connect(self.load)

    def load(self, original: str, processed: str) -> None:
        self.original.set_path(original)
        self.processed.set_path(processed)
        self.ctx.navigate.emit(self.key)
        self.run()

    def run(self) -> None:
        a, b = self.original.path(), self.processed.path()
        if not a or not b:
            self.error("Selecione as duas imagens.")
            return
        svc = self.ctx.service
        self.run_btn.setEnabled(False)
        self.busy.show()
        run_task(lambda: (svc.compare(a, b), compare.difference_image(a, b)), self._done,
                 self._failed)

    def _failed(self, msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.ctx.notify_history()
        self.error(msg)

    def _done(self, res) -> None:
        self.run_btn.setEnabled(True)
        self.busy.hide()
        self.ctx.notify_history()
        r, diff = res
        self.result, self._diff = r, diff
        p = self.ctx.palette
        psnr = "∞ (idênticas)" if math.isinf(r.psnr) else f"{r.psnr:.2f} dB"
        self.verdict.setText(f"<span style='font-size:15pt; font-weight:800; color:{p.accent}'>"
                             f"{r.quality_label}</span>")
        _fill_kv(self.metrics, [
            ("PSNR", psnr),
            ("SSIM", f"{r.ssim:.6f}"),
            ("MSE", f"{r.mse:.6f}"),
            ("MSE por canal (R/G/B)", " / ".join(f"{v:.5f}" for v in r.per_channel_mse)),
            ("Pixels alterados", f"{r.changed_pixels:,} ({r.changed_pixels_pct:.3f}%)"
             .replace(",", ".")),
            ("Valores de canal alterados", f"{r.changed_values:,}".replace(",", ".")),
            ("Diferença máxima", str(r.max_abs_diff)),
            ("Diferença média", f"{r.mean_abs_diff:.5f}"),
            ("Dimensões", f"{r.width} × {r.height} px"),
        ])
        preview = diff.copy()
        preview.thumbnail((640, 360))
        self.diff_view.setPixmap(pil_to_pixmap(preview))
        self.results.show()
        self.toast("Comparação concluída.")

    def export_pdf(self) -> None:
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar relatório PDF",
                                              str(self.ctx.output_dir() / "comparacao.pdf"),
                                              "PDF (*.pdf)")
        if path:
            self.save_pdf(path)

    def save_pdf(self, path: str) -> None:
        try:
            pdf_report.comparison_report_pdf(
                self.result, path, imageio.load_image(self.original.path()),
                imageio.load_image(self.processed.path()), self._diff)
            self.ctx.service.log_report(path, "Relatório de comparação (PDF)")
            self.ctx.notify_history()
            self.toast("Relatório PDF gerado.")
        except (OSError, MarxSecretError) as exc:
            self.error(f"Não foi possível gerar o relatório: {exc}")

    def export_csv(self) -> None:
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV",
                                              str(self.ctx.output_dir() / "comparacao.csv"),
                                              "CSV (*.csv)")
        if path:
            try:
                csv_report.export_comparison_csv(self.result, path)
                self.ctx.service.log_report(path, "Dados de comparação (CSV)")
                self.ctx.notify_history()
                self.toast("CSV exportado.")
            except OSError as exc:
                self.error(f"Não foi possível exportar: {exc}")
