"""Capacidade estendida: contêiner criptografado em blocos privados do PNG.

O formato PNG permite blocos (*chunks*) auxiliares privados, que os
visualizadores ignoram. O MARX SECRET grava o contêiner (já criptografado com
AES-256-GCM) em blocos ``mxSc`` antes do bloco final ``IEND``. Os pixels
permanecem idênticos aos da imagem original e o arquivo continua sendo um PNG
válido. A capacidade deixa de depender da resolução da imagem; o custo é que o
tamanho do arquivo cresce na mesma proporção do conteúdo.

Estrutura dos dados de cada bloco ``mxSc``::

    assinatura "MXSE" (4) | índice (4) | total de blocos (4) | dados
"""

from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path

from .errors import CorruptedDataError, InvalidInputError, NoHiddenDataError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHUNK_TYPE = b"mxSc"  # auxiliar, privado, seguro para cópia
CHUNK_MAGIC = b"MXSE"
CHUNK_DATA_MAX = 16 * 1024 * 1024  # 16 MiB por bloco
_PART = struct.Struct(">4sII")
MAX_FILE_BYTES = 1024 * 1024 * 1024  # leitura de no máximo 1 GiB


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def _iter_chunks(raw: bytes):
    if not raw.startswith(PNG_SIGNATURE):
        raise InvalidInputError("O arquivo não é um PNG válido.")
    pos = len(PNG_SIGNATURE)
    n = len(raw)
    while pos + 12 <= n:
        (length,) = struct.unpack_from(">I", raw, pos)
        ctype = raw[pos + 4 : pos + 8]
        start = pos + 8
        end = start + length
        if end + 4 > n:
            raise CorruptedDataError("Estrutura PNG truncada.")
        yield pos, ctype, start, end
        pos = end + 4
        if ctype == b"IEND":
            return
    raise CorruptedDataError("Bloco IEND não encontrado no PNG.")


def embed(png_path: str | os.PathLike, container: bytes) -> Path:
    """Insere o contêiner em blocos ``mxSc`` antes do IEND (gravação atômica)."""
    p = Path(png_path)
    if p.suffix.lower() != ".png":
        raise InvalidInputError("A capacidade estendida exige saída em PNG.")
    raw = p.read_bytes()
    iend_pos = None
    cleaned = bytearray(raw[: len(PNG_SIGNATURE)])
    for pos, ctype, _start, end in _iter_chunks(raw):
        if ctype == CHUNK_TYPE:
            continue  # remove blocos antigos
        if ctype == b"IEND":
            iend_pos = pos
            break
        cleaned += raw[pos : end + 4]
    if iend_pos is None:
        raise CorruptedDataError("Bloco IEND não encontrado no PNG.")
    parts = [container[i : i + CHUNK_DATA_MAX]
             for i in range(0, len(container), CHUNK_DATA_MAX)] or [b""]
    for idx, part in enumerate(parts):
        cleaned += _chunk(CHUNK_TYPE, _PART.pack(CHUNK_MAGIC, idx, len(parts)) + part)
    cleaned += raw[iend_pos:]
    tmp = p.with_name(p.name + ".tmp-marx")
    with open(tmp, "wb") as fh:
        fh.write(cleaned)
    os.replace(tmp, p)
    return p


def extract(path: str | os.PathLike) -> bytes:
    """Lê e valida (CRC, ordem, completude) os blocos ``mxSc`` do PNG."""
    p = Path(path)
    if p.stat().st_size > MAX_FILE_BYTES:
        raise InvalidInputError("O arquivo excede o limite de leitura de 1 GB.")
    with open(p, "rb") as fh:
        head = fh.read(len(PNG_SIGNATURE))
        if head != PNG_SIGNATURE:
            raise NoHiddenDataError()
        raw = head + fh.read()
    parts: dict[int, bytes] = {}
    total = None
    for _pos, ctype, start, end in _iter_chunks(raw):
        if ctype != CHUNK_TYPE:
            continue
        data = raw[start:end]
        (crc,) = struct.unpack_from(">I", raw, end)
        if zlib.crc32(ctype + data) & 0xFFFFFFFF != crc:
            raise CorruptedDataError("Bloco de capacidade estendida corrompido (CRC).")
        if len(data) < _PART.size:
            raise CorruptedDataError("Bloco de capacidade estendida inválido.")
        magic, idx, count = _PART.unpack_from(data, 0)
        if magic != CHUNK_MAGIC or count == 0 or idx >= count or idx in parts:
            raise CorruptedDataError("Bloco de capacidade estendida inválido.")
        if total is not None and total != count:
            raise CorruptedDataError("Blocos de capacidade estendida inconsistentes.")
        total = count
        parts[idx] = data[_PART.size :]
    if total is None:
        raise NoHiddenDataError()
    if len(parts) != total:
        raise CorruptedDataError("Blocos de capacidade estendida ausentes.")
    return b"".join(parts[i] for i in range(total))


def has_extended(path: str | os.PathLike) -> bool:
    """Verificação rápida (sem carregar os dados) da presença de blocos ``mxSc``."""
    try:
        with open(path, "rb") as fh:
            if fh.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                return False
            while True:
                hdr = fh.read(8)
                if len(hdr) < 8:
                    return False
                length, ctype = struct.unpack(">I", hdr[:4])[0], hdr[4:]
                if ctype == CHUNK_TYPE:
                    return True
                if ctype == b"IEND":
                    return False
                fh.seek(length + 4, os.SEEK_CUR)
    except OSError:
        return False


def stored_size(path: str | os.PathLike) -> int:
    """Soma do tamanho dos dados ``mxSc`` (sem validar) – usado na análise."""
    total = 0
    with open(path, "rb") as fh:
        if fh.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            return 0
        while True:
            hdr = fh.read(8)
            if len(hdr) < 8:
                return total
            length, ctype = struct.unpack(">I", hdr[:4])[0], hdr[4:]
            if ctype == CHUNK_TYPE:
                total += max(0, length - _PART.size)
            if ctype == b"IEND":
                return total
            fh.seek(length + 4, os.SEEK_CUR)
