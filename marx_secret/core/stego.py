"""Esteganografia LSB (bits menos significativos) nos canais RGB.

Fluxo embutido na imagem::

    cabeçalho (17 bytes, sempre gravado a 1 bit/canal nos primeiros valores)
        magia (4) | layout (1) | tamanho do contêiner (4) | semente (8)
    corpo (contêiner MARX SECRET), gravado a partir do valor 136

O byte ``layout`` codifica os bits por canal (1–3) e se a distribuição é
**sequencial** ou **dispersa**. No modo disperso as posições são escolhidas
de forma pseudoaleatória a partir de SHA-256(senha + semente), espalhando a
alteração pela imagem inteira e dificultando ataques estatísticos.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .errors import (
    CapacityError,
    CorruptedDataError,
    InvalidInputError,
    NoHiddenDataError,
    PasswordRequiredError,
)

STREAM_MAGIC = b"MXS\xa7"
_HEADER = struct.Struct(">4sBI8s")
HEADER_LEN = _HEADER.size  # 17 bytes
HEADER_VALUES = HEADER_LEN * 8  # valores de canal usados pelo cabeçalho
LAYOUT_SCATTER = 0x80
MAX_BPC = 3


@dataclass(frozen=True)
class StegoLayout:
    bits_per_channel: int = 1
    scattered: bool = False

    def to_byte(self) -> int:
        return (self.bits_per_channel & 0x03) | (LAYOUT_SCATTER if self.scattered else 0)

    @classmethod
    def from_byte(cls, value: int) -> "StegoLayout":
        bpc = value & 0x03
        if bpc < 1 or bpc > MAX_BPC or (value & 0x7C):
            raise CorruptedDataError("Cabeçalho de esteganografia inválido.")
        return cls(bpc, bool(value & LAYOUT_SCATTER))


@dataclass(frozen=True)
class StegoHeader:
    layout: StegoLayout
    length: int
    seed: bytes


def _rgb_view(img: Image.Image) -> np.ndarray:
    if img.mode not in ("RGB", "RGBA"):
        raise InvalidInputError("A imagem deve estar em RGB ou RGBA.")
    arr = np.array(img, dtype=np.uint8)
    return arr


def _channel_values(arr: np.ndarray) -> np.ndarray:
    """Valores RGB achatados (cópia contígua), ignorando o canal alfa."""
    return np.ascontiguousarray(arr[..., :3]).reshape(-1)


def total_values(img: Image.Image) -> int:
    return img.width * img.height * 3


def capacity_bytes(img: Image.Image, bits_per_channel: int = 1) -> int:
    """Capacidade útil (bytes de contêiner) para a imagem e densidade informadas."""
    _check_bpc(bits_per_channel)
    usable = total_values(img) - HEADER_VALUES
    return max(0, usable * bits_per_channel // 8)


def capacity_for_size(width: int, height: int, bits_per_channel: int = 1) -> int:
    return max(0, (width * height * 3 - HEADER_VALUES) * bits_per_channel // 8)


def _check_bpc(bpc: int) -> None:
    if bpc not in (1, 2, 3):
        raise InvalidInputError("Bits por canal deve ser 1, 2 ou 3.")


def _positions(n_available: int, count: int, layout: StegoLayout, seed: bytes,
               password: str | None) -> np.ndarray:
    if not layout.scattered:
        return np.arange(HEADER_VALUES, HEADER_VALUES + count, dtype=np.int64)
    if not password:
        raise PasswordRequiredError(
            "A distribuição dispersa exige a senha para localizar os dados."
        )
    digest = hashlib.sha256(b"MARX-SECRET/scatter/v1" + seed + password.encode("utf-8")).digest()
    rng = np.random.Generator(np.random.PCG64(int.from_bytes(digest, "big")))
    chosen = rng.choice(n_available, size=count, replace=False, shuffle=True)
    return chosen.astype(np.int64) + HEADER_VALUES


def _bits_to_values(data: bytes, bpc: int) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    pad = (-len(bits)) % bpc
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    groups = bits.reshape(-1, bpc)
    weights = (1 << np.arange(bpc - 1, -1, -1)).astype(np.uint8)
    return (groups * weights).sum(axis=1).astype(np.uint8)


def _values_to_bytes(values: np.ndarray, bpc: int, n_bytes: int) -> bytes:
    shifts = np.arange(bpc - 1, -1, -1, dtype=np.uint8)
    bits = ((values[:, None] >> shifts) & 1).astype(np.uint8).reshape(-1)
    return np.packbits(bits[: n_bytes * 8]).tobytes()


def embed(img: Image.Image, container: bytes, bits_per_channel: int = 1,
          scattered: bool = False, password: str | None = None) -> Image.Image:
    """Oculta ``container`` na imagem e retorna uma nova imagem."""
    _check_bpc(bits_per_channel)
    if not container:
        raise InvalidInputError("Nada a ocultar.")
    if scattered and not password:
        raise InvalidInputError("A distribuição dispersa exige uma senha.")
    cap = capacity_bytes(img, bits_per_channel)
    if len(container) > cap:
        raise CapacityError(
            f"Conteúdo de {len(container):,} bytes excede a capacidade de {cap:,} bytes "
            f"desta imagem com {bits_per_channel} bit(s) por canal.".replace(",", ".")
        )
    arr = _rgb_view(img)
    flat = _channel_values(arr)
    layout = StegoLayout(bits_per_channel, scattered)
    seed = np.random.default_rng().bytes(8) if scattered else b"\x00" * 8
    header = _HEADER.pack(STREAM_MAGIC, layout.to_byte(), len(container), seed)

    # Cabeçalho: 1 bit por canal, sequencial
    hdr_vals = _bits_to_values(header, 1)
    flat[:HEADER_VALUES] = (flat[:HEADER_VALUES] & 0xFE) | hdr_vals

    body_vals = _bits_to_values(container, bits_per_channel)
    pos = _positions(len(flat) - HEADER_VALUES, len(body_vals), layout, seed, password)
    mask = np.uint8((0xFF << bits_per_channel) & 0xFF)
    flat[pos] = (flat[pos] & mask) | body_vals

    arr[..., :3] = flat.reshape(arr.shape[0], arr.shape[1], 3)
    out = Image.fromarray(arr)
    return out


def read_header(img: Image.Image) -> StegoHeader:
    """Lê o cabeçalho; levanta NoHiddenDataError se não houver assinatura."""
    if total_values(img) <= HEADER_VALUES:
        raise NoHiddenDataError()
    arr = _rgb_view(img)
    flat = _channel_values(arr)
    raw = _values_to_bytes(flat[:HEADER_VALUES] & 1, 1, HEADER_LEN)
    magic, layout_byte, length, seed = _HEADER.unpack(raw)
    if magic != STREAM_MAGIC:
        raise NoHiddenDataError()
    layout = StegoLayout.from_byte(layout_byte)
    if length == 0 or length > capacity_bytes(img, layout.bits_per_channel):
        raise CorruptedDataError("O tamanho declarado no cabeçalho é inválido.")
    return StegoHeader(layout, length, seed)


def has_signature(img: Image.Image) -> bool:
    try:
        read_header(img)
        return True
    except (NoHiddenDataError, CorruptedDataError):
        return False


def extract(img: Image.Image, password: str | None = None) -> tuple[bytes, StegoHeader]:
    """Recupera o contêiner oculto da imagem."""
    header = read_header(img)
    arr = _rgb_view(img)
    flat = _channel_values(arr)
    bpc = header.layout.bits_per_channel
    n_vals = -(-header.length * 8 // bpc)
    pos = _positions(len(flat) - HEADER_VALUES, n_vals, header.layout, header.seed, password)
    mask = np.uint8((1 << bpc) - 1)
    vals = flat[pos] & mask
    return _values_to_bytes(vals, bpc, header.length), header
