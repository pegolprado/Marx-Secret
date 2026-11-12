"""Formato do contêiner MARX SECRET (independente do meio de transporte).

Estrutura do contêiner::

    versão (1) | flags (1) | [kdf (6) | salt (16) | nonce (12)] | corpo

Se a flag ENCRYPTED estiver ativa, o corpo é ``AES-256-GCM(interno)`` e o
cabeçalho completo (versão, flags, kdf, salt, nonce) é usado como dado
autenticado adicional (AAD). Caso contrário, o corpo é o próprio interno.

Estrutura do bloco interno::

    tipo (1) | tamanho_nome (2) | nome (UTF-8) | tamanho_original (8) |
    sha256_original (32) | dados (opcionalmente comprimidos com zlib)

O SHA-256 dos dados originais é sempre verificado após a recuperação,
garantindo a integridade mesmo para conteúdos não criptografados.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import PurePath

from . import crypto
from .errors import (
    CorruptedDataError,
    IntegrityError,
    InvalidInputError,
    PasswordRequiredError,
    PayloadTooLargeError,
)

CONTAINER_VERSION = 1
FLAG_ENCRYPTED = 0x01
FLAG_COMPRESSED = 0x02

HARD_MAX_PAYLOAD = 256 * 1024 * 1024  # limite absoluto (256 MiB)
DEFAULT_MAX_PAYLOAD = 64 * 1024 * 1024  # limite padrão configurável (64 MiB)
MAX_NAME_LEN = 255

_INNER_FIXED = struct.Struct(">BH")
_INNER_SIZE = struct.Struct(">Q")
_KDF_SIZE = crypto.KdfParams.STRUCT.size
_ENC_HEADER_LEN = _KDF_SIZE + crypto.SALT_LEN + crypto.NONCE_LEN


class PayloadKind(IntEnum):
    TEXT = 1
    FILE = 2

    @property
    def label(self) -> str:
        return {PayloadKind.TEXT: "Mensagem", PayloadKind.FILE: "Arquivo"}[self]


@dataclass
class Payload:
    """Conteúdo a ser ocultado ou recuperado."""

    kind: PayloadKind
    data: bytes
    filename: str = ""

    @classmethod
    def from_text(cls, text: str) -> "Payload":
        if not isinstance(text, str) or text == "":
            raise InvalidInputError("A mensagem não pode ser vazia.")
        return cls(PayloadKind.TEXT, text.encode("utf-8"))

    @classmethod
    def from_file(cls, path: str, max_size: int = DEFAULT_MAX_PAYLOAD) -> "Payload":
        import os

        if not os.path.isfile(path):
            raise InvalidInputError("O arquivo a ocultar não foi encontrado.")
        size = os.path.getsize(path)
        if size == 0:
            raise InvalidInputError("O arquivo a ocultar está vazio.")
        if size > min(max_size, HARD_MAX_PAYLOAD):
            raise PayloadTooLargeError(
                f"O arquivo possui {size:,} bytes e excede o limite de "
                f"{min(max_size, HARD_MAX_PAYLOAD):,} bytes.".replace(",", ".")
            )
        with open(path, "rb") as fh:
            data = fh.read()
        return cls(PayloadKind.FILE, data, sanitize_filename(PurePath(path).name))

    @property
    def text(self) -> str:
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CorruptedDataError("A mensagem recuperada não é texto UTF-8 válido.") from exc

    @property
    def sha256(self) -> str:
        return crypto.sha256_hex(self.data)


@dataclass
class ContainerInfo:
    """Metadados (não secretos) de um contêiner decodificado."""

    version: int
    encrypted: bool
    compressed: bool
    kdf: crypto.KdfParams | None = None
    stored_size: int = 0
    extra: dict = field(default_factory=dict)


def sanitize_filename(name: str) -> str:
    """Remove componentes de caminho e caracteres perigosos de um nome de arquivo."""
    name = name.replace("\\", "/").split("/")[-1]
    forbidden = '<>:"|?*\x00'
    cleaned = "".join("_" if (c in forbidden or ord(c) < 32) else c for c in name).strip(" .")
    if cleaned in {"", ".", ".."}:
        cleaned = "arquivo_recuperado.bin"
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
        f"LPT{i}" for i in range(1, 10)
    }
    if cleaned.split(".")[0].upper() in reserved:
        cleaned = "_" + cleaned
    encoded = cleaned.encode("utf-8")[:MAX_NAME_LEN]
    return encoded.decode("utf-8", errors="ignore") or "arquivo_recuperado.bin"


def _build_inner(payload: Payload, compress: bool) -> tuple[bytes, bool]:
    name = sanitize_filename(payload.filename).encode("utf-8") if payload.filename else b""
    data = payload.data
    used_compression = False
    if compress:
        compressed = zlib.compress(data, 9)
        if len(compressed) < len(data):
            data = compressed
            used_compression = True
    inner = (
        _INNER_FIXED.pack(int(payload.kind), len(name))
        + name
        + _INNER_SIZE.pack(len(payload.data))
        + crypto.sha256_bytes(payload.data)
        + data
    )
    return inner, used_compression


def _parse_inner(inner: bytes, compressed: bool, max_size: int) -> Payload:
    try:
        kind_raw, name_len = _INNER_FIXED.unpack_from(inner, 0)
        pos = _INNER_FIXED.size
        name = inner[pos : pos + name_len].decode("utf-8")
        pos += name_len
        (orig_size,) = _INNER_SIZE.unpack_from(inner, pos)
        pos += _INNER_SIZE.size
        digest = inner[pos : pos + 32]
        pos += 32
        if len(digest) != 32:
            raise ValueError("digest truncado")
        kind = PayloadKind(kind_raw)
    except (struct.error, ValueError, UnicodeDecodeError) as exc:
        raise CorruptedDataError() from exc
    if orig_size > min(max_size, HARD_MAX_PAYLOAD):
        raise PayloadTooLargeError("O conteúdo oculto excede o limite de tamanho permitido.")
    data = inner[pos:]
    if compressed:
        try:
            dobj = zlib.decompressobj()
            data = dobj.decompress(data, orig_size + 1)
            if len(data) > orig_size or dobj.unconsumed_tail:
                raise CorruptedDataError("Tamanho descomprimido inconsistente.")
        except zlib.error as exc:
            raise CorruptedDataError() from exc
    if len(data) != orig_size:
        raise IntegrityError("O tamanho do conteúdo recuperado não confere.")
    if not crypto.constant_time_equals(crypto.sha256_bytes(data), digest):
        raise IntegrityError()
    return Payload(kind, data, sanitize_filename(name) if name else "")


def build_container(
    payload: Payload,
    password: str | None = None,
    compress: bool = True,
    kdf: crypto.KdfParams | None = None,
    max_size: int = DEFAULT_MAX_PAYLOAD,
) -> bytes:
    """Serializa (e opcionalmente criptografa) um conteúdo."""
    if len(payload.data) == 0:
        raise InvalidInputError("O conteúdo não pode ser vazio.")
    if len(payload.data) > min(max_size, HARD_MAX_PAYLOAD):
        raise PayloadTooLargeError()
    inner, used_compression = _build_inner(payload, compress)
    flags = FLAG_COMPRESSED if used_compression else 0
    if password:
        flags |= FLAG_ENCRYPTED
        params = kdf or crypto.KDF_PROFILES["padrao"]
        salt = crypto.new_salt()
        nonce = crypto.new_nonce()
        header = bytes([CONTAINER_VERSION, flags]) + params.pack() + salt + nonce
        key = bytearray(crypto.derive_key(password, salt, params))
        try:
            body = crypto.aes_gcm_encrypt(bytes(key), nonce, inner, aad=header)
        finally:
            _wipe(key)
        return header + body
    return bytes([CONTAINER_VERSION, flags]) + inner


def inspect_container(container: bytes) -> ContainerInfo:
    """Lê apenas o cabeçalho, sem descriptografar."""
    if len(container) < 2:
        raise CorruptedDataError()
    version, flags = container[0], container[1]
    if version != CONTAINER_VERSION:
        raise CorruptedDataError(f"Versão de contêiner não suportada ({version}).")
    encrypted = bool(flags & FLAG_ENCRYPTED)
    kdf = None
    if encrypted:
        if len(container) < 2 + _ENC_HEADER_LEN + crypto.TAG_LEN:
            raise CorruptedDataError()
        try:
            kdf = crypto.KdfParams.unpack(container[2 : 2 + _KDF_SIZE])
        except Exception as exc:  # parâmetros forjados/corrompidos
            raise CorruptedDataError() from exc
    return ContainerInfo(
        version=version,
        encrypted=encrypted,
        compressed=bool(flags & FLAG_COMPRESSED),
        kdf=kdf,
        stored_size=len(container),
    )


def open_container(
    container: bytes, password: str | None = None, max_size: int = DEFAULT_MAX_PAYLOAD
) -> tuple[Payload, ContainerInfo]:
    """Desserializa (e descriptografa) um contêiner, verificando a integridade."""
    info = inspect_container(container)
    if info.encrypted:
        if not password:
            raise PasswordRequiredError()
        header_len = 2 + _ENC_HEADER_LEN
        header = container[:header_len]
        salt = container[2 + _KDF_SIZE : 2 + _KDF_SIZE + crypto.SALT_LEN]
        nonce = container[2 + _KDF_SIZE + crypto.SALT_LEN : header_len]
        key = bytearray(crypto.derive_key(password, salt, info.kdf))
        try:
            inner = crypto.aes_gcm_decrypt(bytes(key), nonce, container[header_len:], aad=header)
        finally:
            _wipe(key)
    else:
        inner = container[2:]
    return _parse_inner(inner, info.compressed, max_size), info


def _wipe(buf: bytearray) -> None:
    """Sobrescreve um buffer mutável com zeros (melhor esforço em Python)."""
    for i in range(len(buf)):
        buf[i] = 0


# ---------------------------------------------------------------------------
# Arquivos criptografados independentes (.mxs) – módulo de Criptografia
# ---------------------------------------------------------------------------

FILE_MAGIC = b"MXSF"
ENCRYPTED_FILE_EXT = ".mxs"


def encrypt_file_bytes(
    payload: Payload, password: str, kdf: crypto.KdfParams | None = None,
    compress: bool = True, max_size: int = DEFAULT_MAX_PAYLOAD,
) -> bytes:
    if not password:
        raise InvalidInputError("Informe uma senha para criptografar.")
    return FILE_MAGIC + build_container(payload, password, compress, kdf, max_size)


def decrypt_file_bytes(
    data: bytes, password: str, max_size: int = DEFAULT_MAX_PAYLOAD
) -> tuple[Payload, ContainerInfo]:
    if not data.startswith(FILE_MAGIC):
        raise CorruptedDataError("O arquivo não é um arquivo criptografado MARX SECRET (.mxs).")
    return open_container(data[len(FILE_MAGIC):], password, max_size)
