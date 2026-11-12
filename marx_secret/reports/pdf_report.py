"""Relatórios técnicos em PDF com a identidade visual MARX SECRET."""

from __future__ import annotations

import io
import math
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .. import APP_COMMERCIAL_NAME, APP_NAME, APP_SLOGAN, __version__
from ..core.analysis import AnalysisResult
from ..core.compare import ComparisonResult
from ..data.database import OPERATION_LABELS, OperationRecord

EMERALD = colors.HexColor("#10B981")
EMERALD_DARK = colors.HexColor("#047857")
GRAPHITE = colors.HexColor("#1F2328")
BLACK = colors.HexColor("#030409")
LIGHT_ROW = colors.HexColor("#F1F5F3")
MUTED = colors.HexColor("#5B6470")
GOLD = colors.HexColor("#D4AF37")

PRIVACY_NOTE = (
    "Documento gerado localmente e offline. Por política de segurança, este relatório "
    "não contém senhas, chaves nem conteúdos secretos."
)


def banner_path() -> str | None:
    from ..core.paths import resource_dir

    p = resource_dir() / "banner.jpg"
    return str(p) if p.exists() else None


BANNER_RATIO = 2410 / 432


def draw_banner(c, x: float, y: float, height: float) -> bool:
    """Desenha o banner oficial MARX SECRET (canto inferior esquerdo em x, y)."""
    path = banner_path()
    if not path:
        return False
    c.drawImage(path, x, y, width=height * BANNER_RATIO, height=height)
    return True


def draw_logo(c, x: float, y: float, size: float) -> None:
    """Desenha o escudo MARX SECRET (vetorial) com origem no canto inferior esquerdo."""
    s = size / 256.0

    def P(px, py):
        return x + px * s, y + (256 - py) * s

    c.saveState()
    p = c.beginPath()
    p.moveTo(*P(128, 14))
    p.lineTo(*P(222, 48))
    p.lineTo(*P(222, 120))
    p.curveTo(*P(222, 180), *P(182, 222), *P(128, 242))
    p.curveTo(*P(74, 222), *P(34, 180), *P(34, 120))
    p.lineTo(*P(34, 48))
    p.close()
    c.setFillColor(GRAPHITE)
    c.setStrokeColor(EMERALD)
    c.setLineWidth(10 * s)
    c.setLineJoin(1)
    c.drawPath(p, fill=1, stroke=1)
    m = c.beginPath()
    m.moveTo(*P(76, 170))
    m.lineTo(*P(76, 86))
    m.lineTo(*P(128, 138))
    m.lineTo(*P(180, 86))
    m.lineTo(*P(180, 170))
    c.setLineWidth(17 * s)
    c.setLineCap(1)
    c.drawPath(m, fill=0, stroke=1)
    c.setFillColor(EMERALD)
    cx, cy = P(128, 178)
    c.circle(cx, cy, 12 * s, fill=1, stroke=0)
    k = c.beginPath()
    k.moveTo(*P(121, 184))
    k.lineTo(*P(135, 184))
    k.lineTo(*P(139, 210))
    k.lineTo(*P(117, 210))
    k.close()
    c.drawPath(k, fill=1, stroke=0)
    c.restoreState()


class _Decorator:
    def __init__(self, title: str):
        self.title = title
        self.generated = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def __call__(self, c, doc):
        w, h = doc.pagesize
        c.saveState()
        c.setFillColor(BLACK)
        c.rect(0, h - 26 * mm, w, 26 * mm, fill=1, stroke=0)
        c.setFillColor(EMERALD)
        c.rect(0, h - 27 * mm, w, 1 * mm, fill=1, stroke=0)
        if not draw_banner(c, 6 * mm, h - 25 * mm, 22 * mm):
            draw_logo(c, 12 * mm, h - 23.5 * mm, 20 * mm)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 17)
            c.drawString(36 * mm, h - 13 * mm, APP_NAME)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(w - 12 * mm, h - 13 * mm, self.title)
        c.setFont("Helvetica", 8)
        c.drawRightString(w - 12 * mm, h - 18.5 * mm, f"Gerado em {self.generated}")
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawRightString(w - 12 * mm, h - 23 * mm, APP_SLOGAN)
        c.setStrokeColor(colors.HexColor("#D0D5D2"))
        c.line(12 * mm, 14 * mm, w - 12 * mm, 14 * mm)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(12 * mm, 9 * mm, f"{APP_COMMERCIAL_NAME} v{__version__} — {PRIVACY_NOTE}")
        c.drawRightString(w - 12 * mm, 9 * mm, f"Página {doc.page}")
        c.restoreState()


def _styles():
    ss = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, textColor=GRAPHITE,
                             spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=EMERALD_DARK,
                             spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12,
                               alignment=TA_LEFT),
        "small": ParagraphStyle("small", parent=ss["BodyText"], fontSize=7, leading=9),
        "cell": ParagraphStyle("cell", parent=ss["BodyText"], fontSize=7, leading=8.5),
    }


def _table(data, col_widths=None, header=True, zebra=True) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D1CD")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_ROW))
    t.setStyle(TableStyle(style))
    return t


def _kv_table(rows, width) -> Table:
    t = _table([[k, v] for k, v in rows], [width * 0.32, width * 0.68], header=False)
    t.setStyle(TableStyle([("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8),
                           ("TEXTCOLOR", (0, 0), (0, -1), GRAPHITE)]))
    return t


def _pil_flowable(img: Image.Image, max_w: float, max_h: float) -> RLImage:
    img = img.copy()
    img.thumbnail((1200, 1200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    ratio = min(max_w / img.width, max_h / img.height)
    return RLImage(buf, width=img.width * ratio, height=img.height * ratio)


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.0f} {u}" if u == "B" else f"{v:.2f} {u}".replace(".", ",")
        v /= 1024
    return str(n)


def _short(path: str, n: int = 48) -> str:
    return path if len(path) <= n else "…" + path[-(n - 1):]


# ---------------------------------------------------------------------------
# Relatório de histórico
# ---------------------------------------------------------------------------

def history_report_pdf(records: Iterable[OperationRecord], stats: dict, path: str | Path,
                       period: str = "Todo o período") -> Path:
    records = list(records)
    p = Path(path)
    doc = SimpleDocTemplate(str(p), pagesize=landscape(A4), topMargin=32 * mm,
                            bottomMargin=20 * mm, leftMargin=12 * mm, rightMargin=12 * mm,
                            title=f"{APP_NAME} – Relatório de Operações", author=APP_NAME,
                            creator=APP_COMMERCIAL_NAME, subject="Relatório técnico")
    st = _styles()
    width = doc.width
    story = [Paragraph("Relatório de Operações", st["h1"]),
             Paragraph(f"Período: {period}", st["body"]), Spacer(0, 4)]
    summary = [
        ["Operações", "Sucesso", "Falhas", "Taxa de sucesso", "Dados ocultados"],
        [str(stats.get("total", 0)), str(stats.get("success", 0)), str(stats.get("failure", 0)),
         f"{stats.get('success_rate', 0):.1f}%".replace(".", ","),
         _fmt_bytes(int(stats.get("hidden_bytes", 0)))],
    ]
    story.append(_table(summary, [width / 5] * 5, zebra=False))
    by_op = stats.get("by_operation", {})
    if by_op:
        story.append(Paragraph("Operações bem-sucedidas por tipo", st["h2"]))
        rows = [["Tipo de operação", "Quantidade"]] + [
            [OPERATION_LABELS.get(k, k), str(v)] for k, v in sorted(by_op.items(),
                                                                     key=lambda kv: -kv[1])
        ]
        story.append(_table(rows, [width * 0.5, width * 0.2]))
    story.append(Paragraph(f"Registros ({len(records)})", st["h2"]))
    if not records:
        story.append(Paragraph("Nenhuma operação registrada no período.", st["body"]))
    else:
        header = ["#", "Data/Hora", "Operação", "Status", "Entrada", "Saída", "Tam.", "Cripto",
                  "BPC", "SHA-256 saída", "Observação"]
        rows = [header]
        for r in records:
            rows.append([
                str(r.id), r.timestamp.replace("T", " "), r.operation_label, r.status_label,
                Paragraph(_short(r.input_path, 60), st["cell"]),
                Paragraph(_short(r.output_path, 60), st["cell"]),
                _fmt_bytes(r.payload_size) if r.payload_size else "–",
                "Sim" if r.encrypted else "Não",
                str(r.bits_per_channel or "–"),
                Paragraph((r.output_sha256[:16] + "…") if r.output_sha256 else "–", st["cell"]),
                Paragraph(r.message[:120], st["cell"]),
            ])
        fr = [0.035, 0.1, 0.1, 0.055, 0.15, 0.15, 0.06, 0.045, 0.035, 0.1, 0.17]
        t = _table(rows, [width * f for f in fr])
        for i, r in enumerate(records, start=1):
            if r.status != "sucesso":
                t.setStyle(TableStyle([("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#B91C1C"))]))
        story.append(t)
    doc.build(story, onFirstPage=_Decorator("Relatório de Operações"),
              onLaterPages=_Decorator("Relatório de Operações"))
    return p


# ---------------------------------------------------------------------------
# Relatório de análise
# ---------------------------------------------------------------------------

def _histogram_drawing(result: AnalysisResult, width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y = 30, 20
    lp.width, lp.height = width - 45, height - 35
    peak = max(1, int(result.histograms.max()))
    lp.data = [[(i, int(result.histograms[c][i])) for i in range(256)] for c in range(3)]
    for i, col in enumerate(("#DC2626", "#10B981", "#2563EB")):
        lp.lines[i].strokeColor = colors.HexColor(col)
        lp.lines[i].strokeWidth = 0.8
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, 255
    lp.xValueAxis.valueSteps = [0, 64, 128, 192, 255]
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, peak
    lp.xValueAxis.labels.fontSize = lp.yValueAxis.labels.fontSize = 6
    lp.yValueAxis.labelTextFormat = lambda v: f"{int(v):,}".replace(",", ".")
    d.add(lp)
    d.add(String(30, height - 10, "Histograma RGB", fontSize=8, fillColor=GRAPHITE))
    return d


def _chi_drawing(result: AnalysisResult, width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y = 30, 20
    lp.width, lp.height = width - 45, height - 35
    lp.data = [[(pct, prob * 100) for pct, prob in result.chi_square_sequence]]
    lp.lines[0].strokeColor = EMERALD
    lp.lines[0].strokeWidth = 1.4
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, 100
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, 100
    lp.xValueAxis.labels.fontSize = lp.yValueAxis.labels.fontSize = 6
    d.add(lp)
    d.add(String(30, height - 10, "Ataque qui-quadrado sequencial (% da imagem × probabilidade %)",
                 fontSize=8, fillColor=GRAPHITE))
    return d


def analysis_report_pdf(result: AnalysisResult, path: str | Path,
                        lsb_image: Image.Image | None = None) -> Path:
    p = Path(path)
    doc = SimpleDocTemplate(str(p), pagesize=A4, topMargin=32 * mm, bottomMargin=20 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f"{APP_NAME} – Relatório de Análise", author=APP_NAME,
                            creator=APP_COMMERCIAL_NAME)
    st = _styles()
    w = doc.width
    sig = result.signature
    story = [
        Paragraph("Relatório de Análise Estatística", st["h1"]),
        _kv_table([
            ("Arquivo", Paragraph(result.file_name, st["cell"])),
            ("SHA-256", Paragraph(result.file_sha256, st["cell"])),
            ("Formato / modo", f"{result.source_format} / {result.mode}"),
            ("Dimensões", f"{result.width} × {result.height} px "
                          f"({result.megapixels:.2f} MP)".replace(".", ",")),
            ("Tamanho do arquivo", _fmt_bytes(result.file_size)),
            ("Capacidade LSB (1/2/3 bits)", " / ".join(_fmt_bytes(result.capacity[b])
                                                       for b in (1, 2, 3))),
        ], w),
        Paragraph("Diagnóstico", st["h2"]),
        _kv_table([
            ("Nível de suspeita", f"{result.suspicion_label} ({result.suspicion_score}/100)"),
            ("Qui-quadrado global", f"{result.chi_square_overall * 100:.2f}%".replace(".", ",")),
            ("Assinatura MARX SECRET", "Detectada" if sig.detected else "Não detectada"),
        ] + ([
            ("Bits por canal", str(sig.bits_per_channel)),
            ("Distribuição", "Dispersa (pseudoaleatória)" if sig.scattered else "Sequencial"),
            ("Bytes armazenados", _fmt_bytes(sig.stored_bytes or 0)),
            ("Criptografia", "AES-256-GCM" if sig.encrypted else "Não"
             if sig.encrypted is not None else "Indeterminado"),
            ("Derivação de chave", sig.kdf or "–"),
        ] if sig.detected else []), w),
    ]
    for f in result.findings:
        story.append(Paragraph("• " + f, st["body"]))
    story.append(Paragraph("Estatísticas por canal", st["h2"]))
    rows = [["Canal", "Média", "Desvio", "Mín", "Máx", "Entropia", "LSB = 1", "Qui-quadrado"]]
    for c in result.channels:
        rows.append([c.name, f"{c.mean:.2f}", f"{c.std:.2f}", str(c.minimum), str(c.maximum),
                     f"{c.entropy:.4f}", f"{c.lsb_ones_ratio * 100:.2f}%",
                     f"{c.chi_square_probability * 100:.2f}%"])
    story.append(_table(rows, [w / 8] * 8))
    story.append(Spacer(0, 6))
    story.append(KeepTogether([_histogram_drawing(result, w, 150)]))
    story.append(KeepTogether([_chi_drawing(result, w, 150)]))
    if lsb_image is not None:
        story.append(Paragraph("Plano de bits menos significativos (LSB)", st["h2"]))
        story.append(_pil_flowable(lsb_image, w, 90 * mm))
    doc.build(story, onFirstPage=_Decorator("Relatório de Análise"),
              onLaterPages=_Decorator("Relatório de Análise"))
    return p


# ---------------------------------------------------------------------------
# Relatório de comparação
# ---------------------------------------------------------------------------

def comparison_report_pdf(result: ComparisonResult, path: str | Path,
                          original: Image.Image | None = None,
                          processed: Image.Image | None = None,
                          diff: Image.Image | None = None) -> Path:
    p = Path(path)
    doc = SimpleDocTemplate(str(p), pagesize=A4, topMargin=32 * mm, bottomMargin=20 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f"{APP_NAME} – Relatório de Comparação", author=APP_NAME,
                            creator=APP_COMMERCIAL_NAME)
    st = _styles()
    w = doc.width
    psnr = "Infinito (idênticas)" if math.isinf(result.psnr) else f"{result.psnr:.2f} dB"
    story = [
        Paragraph("Relatório de Comparação de Imagens", st["h1"]),
        _kv_table([
            ("Imagem original", Paragraph(result.original_path, st["cell"])),
            ("Imagem processada", Paragraph(result.processed_path, st["cell"])),
            ("Dimensões", f"{result.width} × {result.height} px"),
            ("Avaliação", result.quality_label),
            ("PSNR", psnr.replace(".", ",")),
            ("SSIM", f"{result.ssim:.6f}".replace(".", ",")),
            ("MSE", f"{result.mse:.6f}".replace(".", ",")),
            ("MSE por canal (R/G/B)", " / ".join(f"{v:.5f}" for v in result.per_channel_mse)),
            ("Pixels alterados", f"{result.changed_pixels:,} "
                                 f"({result.changed_pixels_pct:.3f}%)".replace(",", ".")),
            ("Valores de canal alterados", f"{result.changed_values:,}".replace(",", ".")),
            ("Diferença máxima / média", f"{result.max_abs_diff} / {result.mean_abs_diff:.5f}"),
        ], w),
    ]
    images = [(t, im) for t, im in (("Original", original), ("Processada", processed),
                                    ("Diferenças (amplificadas)", diff)) if im is not None]
    if images:
        story.append(Paragraph("Visualização", st["h2"]))
        cell_w = w / len(images) - 4
        story.append(Table([[t for t, _ in images],
                            [_pil_flowable(im, cell_w, 70 * mm) for _, im in images]],
                           colWidths=[w / len(images)] * len(images),
                           style=TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                                             ("ALIGN", (0, 0), (-1, -1), "CENTER")])))
    doc.build(story, onFirstPage=_Decorator("Relatório de Comparação"),
              onLaterPages=_Decorator("Relatório de Comparação"))
    return p
