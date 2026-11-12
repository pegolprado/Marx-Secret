"""Validação, leitura e gravação de imagens."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .errors import InvalidImageError, InvalidInputError

SUPPORTED_INPUT_EXT = {".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg", ".webp", ".gif"}
# A saída precisa ser sem perdas, senão os bits menos significativos são destruídos.
SUPPORTED_OUTPUT_EXT = {".png", ".bmp", ".tif", ".tiff"}
LOSSY_EXT = {".jpg", ".jpeg", ".webp", ".gif"}

MAX_IMAGE_FILE_BYTES = 300 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000  # 100 megapixels
MIN_IMAGE_PIXELS = 64

INPUT_FILTER = "Imagens (*.png *.bmp *.tif *.tiff *.jpg *.jpeg *.webp *.gif)"
OUTPUT_FILTER = "PNG (*.png);;BMP (*.bmp);;TIFF (*.tif *.tiff)"


@dataclass(frozen=True)
class ImageInfo:
    path: str
    format: str
    mode: str
    width: int
    height: int
    file_size: int

    @property
    def pixels(self) -> int:
        return self.width * self.height


def validate_image_path(path: str | os.PathLike) -> Path:
    if not path:
        raise InvalidInputError("Selecione uma imagem.")
    p = Path(path)
    if not p.is_file():
        raise InvalidImageError("A imagem não foi encontrada.")
    if p.suffix.lower() not in SUPPORTED_INPUT_EXT:
        raise InvalidImageError(
            f"Formato '{p.suffix or 'sem extensão'}' não suportado. "
            "Use PNG, BMP, TIFF, JPEG, WEBP ou GIF."
        )
    size = p.stat().st_size
    if size == 0:
        raise InvalidImageError("O arquivo de imagem está vazio.")
    if size > MAX_IMAGE_FILE_BYTES:
        raise InvalidImageError("O arquivo de imagem excede o limite de 300 MB.")
    return p


def validate_output_path(path: str | os.PathLike) -> Path:
    if not path:
        raise InvalidInputError("Informe o arquivo de saída.")
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED_OUTPUT_EXT:
        raise InvalidInputError(
            "A imagem de saída deve ser PNG, BMP ou TIFF (formatos sem perdas). "
            "Formatos com compressão com perdas (JPEG/WEBP) destroem o conteúdo oculto."
        )
    if not p.parent.exists():
        raise InvalidInputError("A pasta de destino não existe.")
    return p


def load_image(path: str | os.PathLike) -> Image.Image:
    """Carrega e valida a imagem, convertendo para RGB ou RGBA."""
    p = validate_image_path(path)
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(p) as probe:
            probe.verify()
        with Image.open(p) as img:
            img.load()
            if img.width * img.height > MAX_IMAGE_PIXELS:
                raise InvalidImageError("A imagem excede o limite de 100 megapixels.")
            if img.width * img.height < MIN_IMAGE_PIXELS:
                raise InvalidImageError("A imagem é pequena demais.")
            has_alpha = img.mode in ("RGBA", "LA", "PA") or (
                img.mode == "P" and "transparency" in img.info
            )
            converted = img.convert("RGBA" if has_alpha else "RGB")
            converted.info["source_format"] = img.format or p.suffix.lstrip(".").upper()
            return converted
    except InvalidImageError:
        raise
    except Image.DecompressionBombError as exc:
        raise InvalidImageError("A imagem excede o limite de tamanho seguro.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError("A imagem está corrompida ou não pôde ser lida.") from exc


def image_info(path: str | os.PathLike) -> ImageInfo:
    p = validate_image_path(path)
    try:
        with Image.open(p) as img:
            return ImageInfo(str(p), img.format or "?", img.mode, img.width, img.height,
                             p.stat().st_size)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError() from exc


def save_image(img: Image.Image, path: str | os.PathLike) -> Path:
    """Grava em formato sem perdas, sem metadados do original."""
    p = validate_output_path(path)
    ext = p.suffix.lower()
    tmp = p.with_name(p.name + ".tmp-marx")
    try:
        if ext == ".png":
            img.save(tmp, format="PNG", optimize=False, compress_level=6)
        elif ext == ".bmp":
            img.save(tmp, format="BMP")
        else:
            img.save(tmp, format="TIFF", compression="tiff_lzw")
        os.replace(tmp, p)
    except OSError as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise InvalidInputError(f"Não foi possível gravar a imagem: {exc.strerror or exc}") from exc
    return p


def is_lossy_input(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in LOSSY_EXT
