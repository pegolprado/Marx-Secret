"""Análise estatística de imagens e detecção de esteganografia LSB.

Inclui histogramas, entropia, proporção de bits LSB, ataque qui-quadrado
(Westfeld & Pfitzmann) global e sequencial, extração do plano LSB e
detecção da assinatura MARX SECRET. Nunca descriptografa nem exibe conteúdo.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import crypto, imageio, payload, pngchunk, stego
from .errors import MarxSecretError

CHANNELS = ("Vermelho", "Verde", "Azul")


@dataclass
class ChannelStats:
    name: str
    mean: float
    std: float
    minimum: int
    maximum: int
    entropy: float
    lsb_ones_ratio: float
    chi_square_probability: float


@dataclass
class SignatureInfo:
    detected: bool
    bits_per_channel: int | None = None
    scattered: bool | None = None
    stored_bytes: int | None = None
    encrypted: bool | None = None
    compressed: bool | None = None
    kdf: str | None = None
    mode: str = "lsb"  # "lsb" | "estendido"


@dataclass
class AnalysisResult:
    path: str
    file_name: str
    file_size: int
    file_sha256: str
    source_format: str
    mode: str
    width: int
    height: int
    channels: list[ChannelStats]
    histograms: np.ndarray  # (3, 256)
    chi_square_overall: float
    chi_square_sequence: list[tuple[int, float]]
    capacity: dict[int, int]
    signature: SignatureInfo
    suspicion_score: int  # 0–100
    suspicion_label: str
    findings: list[str] = field(default_factory=list)

    @property
    def megapixels(self) -> float:
        return self.width * self.height / 1_000_000


# ---------------------------------------------------------------------------
# Funções estatísticas
# ---------------------------------------------------------------------------

def _gammaincc(a: float, x: float) -> float:
    """Função gama incompleta superior regularizada Q(a, x)."""
    if x <= 0:
        return 1.0
    if a <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1.0:  # série
        ap, total, delta = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-14:
                break
        return max(0.0, min(1.0, 1.0 - total * math.exp(-x + a * math.log(x) - gln)))
    # fração continuada (Lentz)
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - gln) * h))


def chi_square_probability(values: np.ndarray) -> float:
    """Probabilidade (0–1) de embutimento LSB pelo ataque qui-quadrado."""
    if values.size == 0:
        return 0.0
    hist = np.bincount(values.reshape(-1), minlength=256).astype(np.float64)
    even, odd = hist[0::2], hist[1::2]
    expected = (even + odd) / 2.0
    valid = expected > 4.0
    k = int(valid.sum())
    if k < 2:
        return 0.0
    chi = float((((even[valid] - expected[valid]) ** 2) / expected[valid]).sum())
    return _gammaincc((k - 1) / 2.0, chi / 2.0)


def shannon_entropy(values: np.ndarray) -> float:
    hist = np.bincount(values.reshape(-1), minlength=256).astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 0.0
    p = hist[hist > 0] / total
    return float(-(p * np.log2(p)).sum())


def lsb_plane(img: Image.Image, channel: int | None = None) -> Image.Image:
    """Imagem em tons de cinza do plano de bits menos significativos."""
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    if channel is None:
        bits = (arr & 1).sum(axis=2) * 85
    else:
        bits = (arr[..., channel] & 1) * 255
    return Image.fromarray(bits.astype(np.uint8))


def detect_extended(path: str) -> SignatureInfo | None:
    """Detecta conteúdo em capacidade estendida (blocos PNG ``mxSc``)."""
    if not pngchunk.has_extended(path):
        return None
    info = SignatureInfo(True, mode="estendido", scattered=False,
                         stored_bytes=pngchunk.stored_size(path))
    try:
        cinfo = payload.inspect_container(pngchunk.extract(path))
        info.encrypted = cinfo.encrypted
        info.compressed = cinfo.compressed
        if cinfo.kdf:
            k = cinfo.kdf
            info.kdf = f"Argon2id t={k.time_cost}, m={k.memory_kib // 1024} MiB, p={k.parallelism}"
    except MarxSecretError:
        pass
    return info


def detect_signature(img: Image.Image) -> SignatureInfo:
    try:
        header = stego.read_header(img)
    except MarxSecretError:
        return SignatureInfo(False)
    info = SignatureInfo(
        True,
        bits_per_channel=header.layout.bits_per_channel,
        scattered=header.layout.scattered,
        stored_bytes=header.length,
    )
    if not header.layout.scattered:
        try:
            container, _ = stego.extract(img)
            cinfo = payload.inspect_container(container)
            info.encrypted = cinfo.encrypted
            info.compressed = cinfo.compressed
            if cinfo.kdf:
                k = cinfo.kdf
                info.kdf = f"Argon2id t={k.time_cost}, m={k.memory_kib // 1024} MiB, p={k.parallelism}"
        except MarxSecretError:
            pass
    else:
        info.encrypted = True  # o modo disperso sempre exige senha
    return info


def analyze_image(path: str) -> AnalysisResult:
    img = imageio.load_image(path)
    arr = np.asarray(img, dtype=np.uint8)
    rgb = arr[..., :3]
    channels: list[ChannelStats] = []
    hists = np.zeros((3, 256), dtype=np.int64)
    for i, name in enumerate(CHANNELS):
        ch = rgb[..., i]
        hists[i] = np.bincount(ch.reshape(-1), minlength=256)
        channels.append(
            ChannelStats(
                name=name,
                mean=float(ch.mean()),
                std=float(ch.std()),
                minimum=int(ch.min()),
                maximum=int(ch.max()),
                entropy=shannon_entropy(ch),
                lsb_ones_ratio=float((ch & 1).mean()),
                chi_square_probability=chi_square_probability(ch),
            )
        )
    flat = np.ascontiguousarray(rgb).reshape(-1)
    overall = chi_square_probability(flat)
    sequence: list[tuple[int, float]] = []
    for pct in range(5, 101, 5):
        n = max(1, flat.size * pct // 100)
        sequence.append((pct, chi_square_probability(flat[:n])))

    signature = detect_extended(path) or detect_signature(img)
    score, label, findings = _score(channels, overall, sequence, signature, path)
    return AnalysisResult(
        path=str(path),
        file_name=os.path.basename(path),
        file_size=os.path.getsize(path),
        file_sha256=crypto.sha256_file(path),
        source_format=img.info.get("source_format", "?"),
        mode=img.mode,
        width=img.width,
        height=img.height,
        channels=channels,
        histograms=hists,
        chi_square_overall=overall,
        chi_square_sequence=sequence,
        capacity={b: stego.capacity_bytes(img, b) for b in (1, 2, 3)},
        signature=signature,
        suspicion_score=score,
        suspicion_label=label,
        findings=findings,
    )


def _score(channels, overall, sequence, signature, path) -> tuple[int, str, list[str]]:
    findings: list[str] = []
    score = 0.0
    if signature.detected:
        score = 100
        findings.append("Assinatura MARX SECRET detectada: a imagem contém conteúdo oculto.")
        if signature.mode == "estendido":
            findings.append("Conteúdo em capacidade estendida (blocos PNG privados); "
                            "os pixels não foram alterados.")
        if signature.encrypted:
            findings.append("O conteúdo está protegido por AES-256-GCM.")
    first = sequence[0][1] if sequence else 0.0
    if first > 0.95:
        score = max(score, 85)
        findings.append(
            "O início da imagem apresenta pares de valores equalizados (qui-quadrado "
            f"{first:.0%}), padrão típico de LSB sequencial."
        )
    elif overall > 0.5:
        score = max(score, 60)
        findings.append(f"Probabilidade qui-quadrado global elevada ({overall:.0%}).")
    lsb_dev = max(abs(c.lsb_ones_ratio - 0.5) for c in channels)
    if lsb_dev < 0.002 and not signature.detected:
        score = max(score, 40)
        findings.append("Distribuição de bits LSB extremamente uniforme (possível dado aleatório).")
    if imageio.is_lossy_input(path):
        findings.append(
            "Imagem com compressão com perdas: inadequada como portadora LSB "
            "(o conteúdo oculto não sobrevive à recompressão)."
        )
    if not findings:
        findings.append("Nenhum indício estatístico relevante de esteganografia LSB.")
    score = int(round(score))
    if score >= 80:
        label = "Alto"
    elif score >= 40:
        label = "Moderado"
    else:
        label = "Baixo"
    return score, label, findings
