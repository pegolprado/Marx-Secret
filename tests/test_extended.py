"""Capacidade estendida (blocos PNG privados)."""

import os

import numpy as np
import pytest
from PIL import Image

from marx_secret.core import analysis, crypto, pngchunk
from marx_secret.core.errors import (
    AuthenticationError,
    CorruptedDataError,
    InvalidInputError,
    NoHiddenDataError,
)
from marx_secret.core.payload import PayloadKind
from marx_secret.services.operations import HideOptions

from .conftest import PASSWORD


def _opts(mode="auto", **kw):
    return HideOptions(password=PASSWORD, kdf_profile="rapido", mode=mode, **kw)


def test_auto_uses_lsb_when_it_fits(service, cover, tmp_path):
    res = service.hide_message(cover, str(tmp_path / "s.png"), "curta", _opts())
    assert res.mode == "lsb"
    assert not pngchunk.has_extended(tmp_path / "s.png")


def test_auto_switches_to_extended_for_large_file(service, cover, tmp_path):
    big = tmp_path / "video.bin"
    big.write_bytes(os.urandom(3 * 1024 * 1024))  # muito maior que a capacidade LSB (~7 KB)
    out = tmp_path / "s.png"
    res = service.hide_file(cover, str(out), str(big), _opts())
    assert res.mode == "estendido" and pngchunk.has_extended(out)
    # pixels idênticos aos da imagem original e PNG válido
    assert np.array_equal(np.asarray(Image.open(cover)), np.asarray(Image.open(out)))
    ext = service.extract(str(out), PASSWORD, PayloadKind.FILE)
    assert ext.mode == "estendido" and ext.payload.data == big.read_bytes()
    assert ext.payload.filename == "video.bin"
    assert big.read_bytes()[:4096] not in out.read_bytes()  # conteúdo criptografado


def test_multiple_chunks(service, cover, tmp_path, monkeypatch):
    monkeypatch.setattr(pngchunk, "CHUNK_DATA_MAX", 1000)
    big = tmp_path / "doc.bin"
    big.write_bytes(os.urandom(10_500))
    out = tmp_path / "s.png"
    service.hide_file(cover, str(out), str(big), _opts("estendido"))
    assert out.read_bytes().count(b"mxSc") == 11
    assert service.extract(str(out), PASSWORD).payload.data == big.read_bytes()


def test_forced_lsb_still_reports_capacity_error(service, cover, tmp_path):
    from marx_secret.core.errors import CapacityError

    big = tmp_path / "b.bin"
    big.write_bytes(os.urandom(100_000))
    with pytest.raises(CapacityError):
        service.hide_file(cover, str(tmp_path / "s.png"), str(big), _opts("lsb"))


def test_extended_requires_png(service, cover, tmp_path):
    with pytest.raises(InvalidInputError):
        service.hide_message(cover, str(tmp_path / "s.bmp"), "x", _opts("estendido"))


def test_extended_wrong_password(service, cover, tmp_path):
    out = str(tmp_path / "s.png")
    service.hide_message(cover, out, "segredo grande", _opts("estendido"))
    with pytest.raises(AuthenticationError):
        service.extract(out, "senha-errada-1234")


def test_extended_corruption_detected(service, cover, tmp_path):
    out = tmp_path / "s.png"
    service.hide_message(cover, str(out), "segredo" * 100, _opts("estendido"))
    raw = bytearray(out.read_bytes())
    i = raw.index(b"mxSc") + 40
    raw[i] ^= 0xFF
    out.write_bytes(bytes(raw))
    with pytest.raises(CorruptedDataError):
        service.extract(str(out), PASSWORD)


def test_reembed_replaces_old_chunks(cover, tmp_path):
    import shutil

    out = tmp_path / "s.png"
    shutil.copy(cover, out)
    pngchunk.embed(out, b"primeiro" * 10)
    pngchunk.embed(out, b"segundo")
    assert pngchunk.extract(out) == b"segundo"


def test_no_extended_data(cover):
    assert not pngchunk.has_extended(cover)
    with pytest.raises(NoHiddenDataError):
        pngchunk.extract(cover)


def test_analysis_detects_extended(service, cover, tmp_path):
    out = str(tmp_path / "s.png")
    service.hide_message(cover, out, "x" * 20000, _opts("estendido"))
    r = analysis.analyze_image(out)
    assert r.signature.detected and r.signature.mode == "estendido"
    assert r.signature.encrypted and r.suspicion_label == "Alto"
    assert crypto.sha256_file(out) == r.file_sha256
