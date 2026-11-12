import os

import pytest

from marx_secret.core import crypto, payload
from marx_secret.core.errors import (
    AuthenticationError,
    CorruptedDataError,
    IntegrityError,
    InvalidInputError,
    PasswordRequiredError,
    PayloadTooLargeError,
)
from marx_secret.core.payload import Payload, PayloadKind

FAST = crypto.KDF_PROFILES["rapido"]


def test_text_roundtrip_plain_and_encrypted():
    p = Payload.from_text("Mensagem secreta – ação, coração ✓")
    plain = payload.build_container(p)
    out, info = payload.open_container(plain)
    assert out.text == p.text and not info.encrypted
    enc = payload.build_container(p, "senha-boa-1", kdf=FAST)
    out, info = payload.open_container(enc, "senha-boa-1")
    assert out.text == p.text and info.encrypted
    assert p.data not in enc  # conteúdo nunca aparece em claro


def test_wrong_password_and_missing_password():
    enc = payload.build_container(Payload.from_text("x" * 50), "correta-123", kdf=FAST)
    with pytest.raises(AuthenticationError):
        payload.open_container(enc, "errada-123")
    with pytest.raises(PasswordRequiredError):
        payload.open_container(enc, None)


def test_header_tampering_detected_by_aad():
    enc = bytearray(payload.build_container(Payload.from_text("abc"), "correta-123", kdf=FAST))
    enc[1] ^= payload.FLAG_COMPRESSED  # altera flag autenticada
    with pytest.raises(AuthenticationError):
        payload.open_container(bytes(enc), "correta-123")


def test_integrity_sha256_detects_corruption_on_plain_container():
    c = bytearray(payload.build_container(Payload.from_text("conteúdo íntegro" * 3), compress=False))
    c[-1] ^= 0xFF
    with pytest.raises(IntegrityError):
        payload.open_container(bytes(c))


def test_corrupted_container():
    with pytest.raises(CorruptedDataError):
        payload.open_container(b"\x09\x00abc")
    with pytest.raises(CorruptedDataError):
        payload.open_container(b"\x01")


def test_file_payload_and_sanitized_name(tmp_path):
    f = tmp_path / "relatório final.pdf"
    f.write_bytes(os.urandom(5000))
    p = Payload.from_file(str(f))
    assert p.kind == PayloadKind.FILE and p.filename == "relatório final.pdf"
    out, _ = payload.open_container(payload.build_container(p, "senha-123", kdf=FAST), "senha-123")
    assert out.data == f.read_bytes() and out.filename == p.filename


@pytest.mark.parametrize("raw,expected", [
    ("../../etc/passwd", "passwd"),
    ("C:\\Windows\\system32\\evil.exe", "evil.exe"),
    ("CON.txt", "_CON.txt"),
    ("..", "arquivo_recuperado.bin"),
    ("a<b>c?.txt", "a_b_c_.txt"),
])
def test_sanitize_filename(raw, expected):
    assert payload.sanitize_filename(raw) == expected


def test_size_limits(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"\0" * 2048)
    with pytest.raises(PayloadTooLargeError):
        Payload.from_file(str(f), max_size=1024)
    empty = tmp_path / "vazio.bin"
    empty.write_bytes(b"")
    with pytest.raises(InvalidInputError):
        Payload.from_file(str(empty))
    with pytest.raises(InvalidInputError):
        Payload.from_text("")


def test_compression_used_only_when_beneficial():
    compressible = payload.build_container(Payload.from_text("a" * 10000))
    assert payload.inspect_container(compressible).compressed
    random_data = Payload(PayloadKind.FILE, os.urandom(3000), "r.bin")
    assert not payload.inspect_container(payload.build_container(random_data)).compressed


def test_encrypted_file_format():
    blob = payload.encrypt_file_bytes(Payload.from_text("arquivo"), "senha-123", FAST)
    assert blob.startswith(payload.FILE_MAGIC)
    out, _ = payload.decrypt_file_bytes(blob, "senha-123")
    assert out.text == "arquivo"
    with pytest.raises(CorruptedDataError):
        payload.decrypt_file_bytes(b"XXXX" + blob[4:], "senha-123")
