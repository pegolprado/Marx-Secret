"""Dashboard profissional."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from ... import APP_NAME, APP_SLOGAN, __version__
from ...core import crypto, paths
from ..icons import logo_pixmap
from ..widgets import BarChart, Card, Page, StatCard, button, fmt_bytes, label

_WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class DashboardPage(Page):
    key = "dashboard"
    title = "Dashboard"
    subtitle = "Visão geral da sua atividade e do estado de segurança."
    icon_name = "dashboard"

    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(ctx, parent)
        # --- destaque
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(28, 24, 28, 24)
        hl.setSpacing(24)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(112))
        hl.addWidget(logo)
        txt = QVBoxLayout()
        txt.setSpacing(4)
        txt.addWidget(label(APP_NAME, "HeroTitle"))
        txt.addWidget(label(APP_SLOGAN, "HeroSlogan"))
        txt.addWidget(label("Esteganografia profissional com criptografia AES-256-GCM, "
                            "derivação de chaves Argon2id e verificação de integridade SHA-256. "
                            "Todo o processamento é local e offline.", "HeroText", wrap=True))
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for text, icon_name, key, primary in (
            ("Ocultar mensagem", "hide", "hide_message", True),
            ("Extrair mensagem", "reveal", "extract_message", False),
            ("Ocultar arquivo", "file_hide", "hide_file", False),
            ("Analisar imagem", "analysis", "analysis", False),
        ):
            b = button(text, icon_name, obj="Primary" if primary else None,
                       on_click=lambda _=False, k=key: ctx.navigate.emit(k))
            actions.addWidget(b)
        actions.addStretch()
        txt.addSpacing(8)
        txt.addLayout(actions)
        hl.addLayout(txt, 1)
        self.body.addWidget(hero)

        # --- indicadores
        stats = QGridLayout()
        stats.setSpacing(16)
        self.c_total = StatCard("Operações", "history")
        self.c_hidden = StatCard("Ocultações", "hide")
        self.c_extracted = StatCard("Extrações", "reveal")
        self.c_rate = StatCard("Taxa de sucesso", "check")
        for i, c in enumerate((self.c_total, self.c_hidden, self.c_extracted, self.c_rate)):
            stats.addWidget(c, 0, i)
        self.body.addLayout(stats)

        row = QHBoxLayout()
        row.setSpacing(16)
        chart_card = Card("Atividade nos últimos 7 dias")
        self.chart = BarChart()
        chart_card.add(self.chart)
        row.addWidget(chart_card, 3)
        sec = Card("Estado de segurança")
        self.sec_labels = label("", wrap=True)
        self.sec_labels.setTextFormat(Qt.TextFormat.RichText)
        sec.add(self.sec_labels)
        sec.layout_.addStretch()
        row.addWidget(sec, 2)
        self.body.addLayout(row)

        recent = Card("Operações recentes")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Data/Hora", "Operação", "Status", "Arquivo"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(240)
        recent.add(self.table)
        rrow = QHBoxLayout()
        rrow.addStretch()
        rrow.addWidget(button("Ver histórico completo", "history",
                              on_click=lambda: ctx.navigate.emit("history")))
        recent.add(layout=rrow)
        self.body.addWidget(recent)
        self.body.addStretch()
        ctx.history_changed.connect(self.refresh)
        ctx.settings_changed.connect(self.refresh)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        st = self.ctx.db.statistics()
        by = st["by_operation"]
        hidden = by.get("ocultar_mensagem", 0) + by.get("ocultar_arquivo", 0)
        extracted = by.get("extrair_mensagem", 0) + by.get("recuperar_arquivo", 0)
        self.c_total.set(str(st["total"]), f"{st['failure']} com falha")
        self.c_hidden.set(str(hidden), f"{fmt_bytes(st['hidden_bytes'])} ocultados")
        self.c_extracted.set(str(extracted), "mensagens e arquivos")
        self.c_rate.set(f"{st['success_rate']:.0f}%", "das operações")
        self.chart.set_data([(_WEEKDAYS[date.fromisoformat(d).weekday()], n)
                             for d, n in st["last7"]])
        profile = self.ctx.setting("kdf_profile")
        p = crypto.KDF_PROFILES.get(profile, crypto.KDF_PROFILES["padrao"])
        acc = self.ctx.palette.accent
        items = [
            "Processamento 100% local e offline",
            "Criptografia AES-256-GCM autenticada",
            f"Argon2id: {p.memory_kib // 1024} MiB, {p.time_cost} iterações, "
            f"{p.parallelism} thread(s)",
            "Integridade SHA-256 em toda recuperação",
            "Senha obrigatória" if self.ctx.setting("require_password")
            else "Senha opcional (recomenda-se exigir)",
            "Histórico sem senhas nem conteúdos secretos"
            if self.ctx.setting("history_enabled") else "Histórico desativado",
            f"Modo: {'portátil' if paths.is_portable() else 'instalado'} · v{__version__}",
        ]
        self.sec_labels.setText("<br>".join(
            f"<span style='color:{acc}'>●</span>&nbsp; {t}" for t in items))
        recs = self.ctx.db.list_operations(limit=8)
        self.table.setRowCount(len(recs))
        for i, r in enumerate(recs):
            vals = [r.timestamp.replace("T", " "), r.operation_label, r.status_label,
                    r.output_path or r.input_path]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 2:
                    it.setForeground(Qt.GlobalColor.red if r.status != "sucesso" else
                                     Qt.GlobalColor.darkGreen)
                self.table.setItem(i, j, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
