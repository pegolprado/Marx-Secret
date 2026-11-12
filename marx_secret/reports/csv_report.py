"""Exportação CSV (UTF-8 com BOM e separador ';' – compatível com Excel pt-BR)."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable

from ..core.analysis import AnalysisResult
from ..core.compare import ComparisonResult
from ..data.database import OperationRecord

HISTORY_HEADERS = [
    "ID", "Data/Hora", "Operação", "Status", "Imagem/Arquivo de entrada", "Saída",
    "Tipo de conteúdo", "Tamanho do conteúdo (bytes)", "Criptografado", "Comprimido",
    "Bits por canal", "Distribuição dispersa", "SHA-256 entrada", "SHA-256 saída",
    "Duração (ms)", "Observação",
]


def _yn(v: bool) -> str:
    return "Sim" if v else "Não"


def _formula_safe(value) -> str:
    """Evita injeção de fórmulas em planilhas (CSV injection)."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _writer(path: Path):
    fh = open(path, "w", newline="", encoding="utf-8-sig")
    return fh, csv.writer(fh, delimiter=";", quoting=csv.QUOTE_MINIMAL)


def export_history_csv(records: Iterable[OperationRecord], path: str | Path) -> Path:
    p = Path(path)
    fh, w = _writer(p)
    with fh:
        w.writerow(HISTORY_HEADERS)
        for r in records:
            w.writerow([_formula_safe(x) for x in [
                r.id, r.timestamp.replace("T", " "), r.operation_label, r.status_label,
                r.input_path, r.output_path, r.payload_kind, r.payload_size,
                _yn(r.encrypted), _yn(r.compressed), r.bits_per_channel or "",
                _yn(r.scattered), r.input_sha256, r.output_sha256, r.duration_ms, r.message,
            ]])
    return p


def export_analysis_csv(result: AnalysisResult, path: str | Path) -> Path:
    p = Path(path)
    fh, w = _writer(p)
    with fh:
        w.writerow(["Campo", "Valor"])
        for k, v in [
            ("Arquivo", result.file_name),
            ("SHA-256", result.file_sha256),
            ("Formato", result.source_format),
            ("Dimensões", f"{result.width}x{result.height}"),
            ("Tamanho (bytes)", result.file_size),
            ("Qui-quadrado global", f"{result.chi_square_overall:.6f}"),
            ("Assinatura MARX SECRET", _yn(result.signature.detected)),
            ("Nível de suspeita", f"{result.suspicion_label} ({result.suspicion_score}/100)"),
        ]:
            w.writerow([k, _formula_safe(v)])
        w.writerow([])
        w.writerow(["Canal", "Média", "Desvio padrão", "Mínimo", "Máximo", "Entropia",
                    "Proporção LSB=1", "Prob. qui-quadrado"])
        for c in result.channels:
            w.writerow([c.name, f"{c.mean:.4f}", f"{c.std:.4f}", c.minimum, c.maximum,
                        f"{c.entropy:.6f}", f"{c.lsb_ones_ratio:.6f}",
                        f"{c.chi_square_probability:.6f}"])
        w.writerow([])
        w.writerow(["Trecho analisado (%)", "Prob. qui-quadrado"])
        for pct, prob in result.chi_square_sequence:
            w.writerow([pct, f"{prob:.6f}"])
        w.writerow([])
        w.writerow(["Valor", "Histograma R", "Histograma G", "Histograma B"])
        for i in range(256):
            w.writerow([i, *[int(result.histograms[c][i]) for c in range(3)]])
    return p


def export_comparison_csv(result: ComparisonResult, path: str | Path) -> Path:
    p = Path(path)
    fh, w = _writer(p)
    with fh:
        w.writerow(["Métrica", "Valor"])
        psnr = "∞" if math.isinf(result.psnr) else f"{result.psnr:.4f}"
        for k, v in [
            ("Imagem original", result.original_path),
            ("Imagem processada", result.processed_path),
            ("Dimensões", f"{result.width}x{result.height}"),
            ("MSE", f"{result.mse:.6f}"),
            ("PSNR (dB)", psnr),
            ("SSIM", f"{result.ssim:.6f}"),
            ("Pixels alterados", result.changed_pixels),
            ("Pixels alterados (%)", f"{result.changed_pixels_pct:.4f}"),
            ("Valores de canal alterados", result.changed_values),
            ("Diferença máxima", result.max_abs_diff),
            ("Diferença média", f"{result.mean_abs_diff:.6f}"),
            ("Qualidade", result.quality_label),
        ]:
            w.writerow([k, _formula_safe(v)])
    return p
