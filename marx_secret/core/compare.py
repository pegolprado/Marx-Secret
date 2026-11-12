"""Comparação entre imagem original e imagem processada."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import imageio
from .errors import InvalidInputError

_SSIM_MAX_SIDE = 2048


@dataclass
class ComparisonResult:
    original_path: str
    processed_path: str
    width: int
    height: int
    mse: float
    psnr: float  # math.inf quando idênticas
    ssim: float
    changed_values: int
    changed_pixels: int
    changed_pixels_pct: float
    max_abs_diff: int
    mean_abs_diff: float
    per_channel_mse: tuple[float, float, float]
    identical: bool

    @property
    def quality_label(self) -> str:
        if self.identical:
            return "Idênticas"
        if self.psnr >= 50:
            return "Imperceptível"
        if self.psnr >= 40:
            return "Excelente"
        if self.psnr >= 30:
            return "Boa"
        return "Alteração visível"


def _ssim(a: np.ndarray, b: np.ndarray, win: int = 8) -> float:
    """SSIM médio (janela uniforme) sobre a luminância."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

    def box(x: np.ndarray) -> np.ndarray:
        s = np.cumsum(np.cumsum(np.pad(x, ((1, 0), (1, 0))), axis=0), axis=1)
        return (s[win:, win:] - s[:-win, win:] - s[win:, :-win] + s[:-win, :-win]) / (win * win)

    if a.shape[0] < win or a.shape[1] < win:
        return 1.0 if np.array_equal(a, b) else 0.0
    mu_a, mu_b = box(a), box(b)
    va = box(a * a) - mu_a**2
    vb = box(b * b) - mu_b**2
    cov = box(a * b) - mu_a * mu_b
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (va + vb + c2)
    return float(np.clip((num / den).mean(), -1.0, 1.0))


def _luma(img: Image.Image) -> np.ndarray:
    g = img.convert("L")
    if max(g.size) > _SSIM_MAX_SIDE:
        scale = _SSIM_MAX_SIDE / max(g.size)
        g = g.resize((max(1, int(g.width * scale)), max(1, int(g.height * scale))),
                     Image.Resampling.BILINEAR)
    return np.asarray(g, dtype=np.float64)


def compare_images(original_path: str, processed_path: str) -> ComparisonResult:
    a_img = imageio.load_image(original_path)
    b_img = imageio.load_image(processed_path)
    if a_img.size != b_img.size:
        raise InvalidInputError(
            f"As imagens possuem dimensões diferentes ({a_img.width}×{a_img.height} e "
            f"{b_img.width}×{b_img.height})."
        )
    a = np.asarray(a_img.convert("RGB"), dtype=np.int16)
    b = np.asarray(b_img.convert("RGB"), dtype=np.int16)
    diff = np.abs(a - b)
    sq = diff.astype(np.float64) ** 2
    mse = float(sq.mean())
    psnr = math.inf if mse == 0 else 10 * math.log10(255**2 / mse)
    changed_mask = diff.any(axis=2)
    changed_pixels = int(changed_mask.sum())
    return ComparisonResult(
        original_path=os.path.abspath(original_path),
        processed_path=os.path.abspath(processed_path),
        width=a_img.width,
        height=a_img.height,
        mse=mse,
        psnr=psnr,
        ssim=_ssim(_luma(a_img), _luma(b_img)),
        changed_values=int((diff > 0).sum()),
        changed_pixels=changed_pixels,
        changed_pixels_pct=100.0 * changed_pixels / (a_img.width * a_img.height),
        max_abs_diff=int(diff.max()),
        mean_abs_diff=float(diff.mean()),
        per_channel_mse=tuple(float(sq[..., i].mean()) for i in range(3)),  # type: ignore[arg-type]
        identical=changed_pixels == 0,
    )


def difference_image(original_path: str, processed_path: str) -> Image.Image:
    """Mapa de calor das diferenças (amplificadas) entre as imagens."""
    a = np.asarray(imageio.load_image(original_path).convert("RGB"), dtype=np.int16)
    b = np.asarray(imageio.load_image(processed_path).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        raise InvalidInputError("As imagens possuem dimensões diferentes.")
    d = np.abs(a - b).max(axis=2).astype(np.float64)
    peak = d.max()
    norm = d / peak if peak > 0 else d
    out = np.zeros(a.shape, dtype=np.uint8)
    out[..., 0] = (norm * 40).astype(np.uint8)  # fundo grafite → verde esmeralda
    out[..., 1] = np.where(d > 0, 120 + norm * 135, 18).astype(np.uint8)
    out[..., 2] = np.where(d > 0, 80 + norm * 60, 20).astype(np.uint8)
    out[d == 0] = (18, 20, 22)
    return Image.fromarray(out)
