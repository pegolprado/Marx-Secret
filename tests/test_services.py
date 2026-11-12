import os

import pytest

from marx_secret.core import crypto
from marx_secret.core.errors import (
    AuthenticationError,
    CapacityError,
    InvalidImageError,
    InvalidInputError,
    NoHiddenDataError,
    PasswordRequiredError,
)
from marx_secret.core.payload import PayloadKind
from marx_secret.services.operations import HideOptions

from .conftest import PASSWORD, make_image


def test_hide_and_extract_message(service, cover, tmp_path, opts):
    out = str(tmp_path / "saida.png")
    msg = "Encontro às 18h na praça. Código: ΩΣ-42 🔐"
    res = service.hide_message(cover, out, msg, opts)
    assert os.path.exists(out) and res.encrypted and res.scattered
    assert res.output_sha256 == crypto.sha256_file(out)
    ext = service.extract(out, PASSWORD)
    assert ext.payload.text == msg and ext.integrity_ok
    assert ext.payload.kind == PayloadKind.TEXT


def test_hide_and_recover_file(service, big_cover, tmp_path, opts):
    secret = tmp_path / "contrato.pdf"
    secret.write_bytes(os.urandom(20000))
    out = str(tmp_path / "saida.bmp")
    service.hide_file(big_cover, out, str(secret), opts)
    ext = service.extract(out, PASSWORD, expected=PayloadKind.FILE)
    dest_dir = tmp_path / "recuperados"
    dest_dir.mkdir()
    saved = service.save_payload(ext.payload, dest_dir)
    assert saved.name == "contrato.pdf"
    assert saved.read_bytes() == secret.read_bytes()
    saved2 = service.save_payload(ext.payload, dest_dir)  # não sobrescreve
    assert saved2.name == "contrato (1).pdf"


def test_wrong_password(service, cover, tmp_path):
    out = str(tmp_path / "s.png")
    o = HideOptions(password=PASSWORD, kdf_profile="rapido", scattered=False)
    service.hide_message(cover, out, "segredo", o)
    with pytest.raises(AuthenticationError):
        service.extract(out, "senha-errada-123")
    with pytest.raises(PasswordRequiredError):
        service.extract(out, None)


def test_wrong_password_scattered_mode(service, cover, tmp_path, opts):
    out = str(tmp_path / "s.png")
    service.hide_message(cover, out, "segredo", opts)
    with pytest.raises(AuthenticationError):
        service.extract(out, "senha-errada-123")


def test_unencrypted_mode_when_allowed(service, cover, tmp_path):
    out = str(tmp_path / "s.png")
    o = HideOptions(password=None, require_password=False, scattered=False)
    service.hide_message(cover, out, "aberto", o)
    assert service.extract(out).payload.text == "aberto"


def test_password_policy(service, cover, tmp_path):
    out = str(tmp_path / "s.png")
    with pytest.raises(InvalidInputError):
        service.hide_message(cover, out, "x", HideOptions(password=None))
    with pytest.raises(InvalidInputError):
        service.hide_message(cover, out, "x", HideOptions(password="curta", kdf_profile="rapido"))


def test_capacity_error_and_estimate(service, cover, tmp_path, opts):
    big = tmp_path / "grande.bin"
    big.write_bytes(os.urandom(50_000))
    with pytest.raises(CapacityError):
        service.hide_file(cover, str(tmp_path / "s.png"), str(big), opts)
    est = service.estimate(cover, 50_000, 1, True, "grande.bin")
    assert not est.fits and est.usage_pct > 100
    est = service.estimate(cover, 100, 3, True)
    assert est.fits


def test_same_input_output_rejected(service, cover, opts):
    with pytest.raises(InvalidInputError):
        service.hide_message(cover, cover, "x", opts)


def test_incompatible_and_corrupted_images(service, tmp_path, opts):
    bad = tmp_path / "ruim.png"
    bad.write_bytes(b"corrompido" * 50)
    with pytest.raises(InvalidImageError):
        service.hide_message(str(bad), str(tmp_path / "o.png"), "x", opts)
    with pytest.raises(InvalidImageError):
        service.extract(str(bad), PASSWORD)
    doc = tmp_path / "doc.docx"
    doc.write_bytes(b"PK")
    with pytest.raises(InvalidImageError):
        service.extract(str(doc), PASSWORD)


def test_extract_from_clean_image(service, cover):
    with pytest.raises(NoHiddenDataError):
        service.extract(cover, PASSWORD)


def test_jpeg_cover_produces_png(service, tmp_path, opts):
    jpg = make_image(tmp_path / "foto.jpg", size=(200, 150), fmt="JPEG")
    out = str(tmp_path / "foto_segura.png")
    service.hide_message(jpg, out, "de jpeg para png", opts)
    assert service.extract(out, PASSWORD).payload.text == "de jpeg para png"


def test_history_records_without_secrets(service, db, cover, tmp_path, opts):
    out = str(tmp_path / "s.png")
    secret = "CONTEUDO-ULTRA-SECRETO-XYZ"
    service.hide_message(cover, out, secret, opts)
    service.extract(out, PASSWORD)
    with pytest.raises(AuthenticationError):
        service.extract(out, "senha-errada-999")
    recs = db.list_operations()
    assert [r.operation for r in recs] == ["extrair_mensagem", "extrair_mensagem", "ocultar_mensagem"]
    assert recs[0].status == "falha" and recs[1].status == "sucesso"
    raw = open(db.path, "rb").read()
    for forbidden in (secret, PASSWORD, "senha-errada-999"):
        assert forbidden.encode() not in raw
        for r in recs:
            assert forbidden not in str(r.__dict__)


def test_history_can_be_disabled(service, db, cover, tmp_path, opts):
    db.set_setting("history_enabled", False)
    service.hide_message(cover, str(tmp_path / "s.png"), "x", opts)
    assert db.list_operations() == []


def test_encrypt_decrypt_file(service, tmp_path):
    src = tmp_path / "planilha.xlsx"
    src.write_bytes(os.urandom(4096))
    dst = str(tmp_path / "planilha.xlsx.mxs")
    service.encrypt_file(str(src), dst, PASSWORD, kdf_profile="rapido")
    assert src.read_bytes() not in open(dst, "rb").read()
    outdir = tmp_path / "out"
    outdir.mkdir()
    rec = service.decrypt_file(dst, str(outdir), PASSWORD)
    assert rec.read_bytes() == src.read_bytes() and rec.name == "planilha.xlsx"
    with pytest.raises(AuthenticationError):
        service.decrypt_file(dst, str(outdir), "senha-errada-1")


def test_verify_integrity_and_secure_delete(service, tmp_path):
    f = tmp_path / "temp.bin"
    f.write_bytes(b"dados temporarios" * 100)
    h = crypto.sha256_file(f)
    assert service.verify_integrity(str(f), h)
    assert not service.verify_integrity(str(f), "0" * 64)
    service.secure_delete(str(f), passes=2)
    assert not f.exists()
    assert not list(tmp_path.glob(".*"))


def test_corrupted_stego_image_detected(service, cover, tmp_path):
    import numpy as np
    from PIL import Image

    out = str(tmp_path / "s.png")
    o = HideOptions(password=PASSWORD, kdf_profile="rapido", scattered=False)
    service.hide_message(cover, out, "mensagem integra" * 20, o)
    arr = np.asarray(Image.open(out)).copy()
    flat = arr.reshape(-1)
    flat[400:700] ^= 1  # corrompe o corpo
    Image.fromarray(flat.reshape(arr.shape)).save(out)
    with pytest.raises(AuthenticationError):
        service.extract(out, PASSWORD)
