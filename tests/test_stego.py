import numpy as np
import pytest
from PIL import Image

from marx_secret.core import imageio, stego
from marx_secret.core.errors import (
    CapacityError,
    InvalidImageError,
    InvalidInputError,
    NoHiddenDataError,
    PasswordRequiredError,
)

from .conftest import make_image


@pytest.mark.parametrize("bpc", [1, 2, 3])
@pytest.mark.parametrize("scattered", [False, True])
def test_embed_extract_roundtrip(cover, bpc, scattered):
    img = imageio.load_image(cover)
    data = bytes(range(256)) * 10
    out = stego.embed(img, data, bpc, scattered, "senha-1234")
    got, header = stego.extract(out, "senha-1234")
    assert got == data
    assert header.layout.bits_per_channel == bpc and header.layout.scattered == scattered


def test_only_lsbs_change(cover):
    img = imageio.load_image(cover)
    out = stego.embed(img, b"abc" * 100, 2, False)
    diff = np.abs(np.asarray(img, dtype=int) - np.asarray(out, dtype=int))
    assert diff.max() <= 3


def test_alpha_channel_preserved(tmp_path):
    path = make_image(tmp_path / "alfa.png", mode="RGBA")
    img = imageio.load_image(path)
    assert img.mode == "RGBA"
    out = stego.embed(img, b"oi" * 50, 1, False)
    assert np.array_equal(np.asarray(img)[..., 3], np.asarray(out)[..., 3])
    assert stego.extract(out)[0] == b"oi" * 50


def test_capacity_exceeded(cover):
    img = imageio.load_image(cover)
    cap = stego.capacity_bytes(img, 1)
    with pytest.raises(CapacityError):
        stego.embed(img, b"x" * (cap + 1), 1)
    stego.embed(img, b"x" * cap, 1)  # exatamente a capacidade funciona


def test_capacity_formula(cover):
    img = imageio.load_image(cover)
    assert stego.capacity_bytes(img, 1) == (160 * 120 * 3 - stego.HEADER_VALUES) // 8
    assert stego.capacity_for_size(160, 120, 3) == stego.capacity_bytes(img, 3)


def test_no_hidden_data(cover):
    with pytest.raises(NoHiddenDataError):
        stego.extract(imageio.load_image(cover))
    assert not stego.has_signature(imageio.load_image(cover))


def test_scattered_requires_password(cover):
    img = imageio.load_image(cover)
    with pytest.raises(InvalidInputError):
        stego.embed(img, b"abc", 1, True, None)
    out = stego.embed(img, b"abc", 1, True, "senha-1234")
    with pytest.raises(PasswordRequiredError):
        stego.extract(out)


def test_scattered_wrong_password_returns_garbage(cover):
    img = imageio.load_image(cover)
    out = stego.embed(img, b"conteudo-real" * 10, 1, True, "senha-1234")
    got, _ = stego.extract(out, "outra-senha")
    assert got != b"conteudo-real" * 10


def test_survives_png_bmp_tiff_save(tmp_path, cover):
    img = imageio.load_image(cover)
    out = stego.embed(img, b"persistente" * 20, 1, False)
    for ext in (".png", ".bmp", ".tif"):
        path = tmp_path / f"saida{ext}"
        imageio.save_image(out, path)
        assert stego.extract(imageio.load_image(path))[0] == b"persistente" * 20


def test_lossy_output_rejected(tmp_path, cover):
    with pytest.raises(InvalidInputError):
        imageio.validate_output_path(tmp_path / "x.jpg")


def test_invalid_images(tmp_path):
    bad = tmp_path / "corrompida.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"lixo" * 100)
    with pytest.raises(InvalidImageError):
        imageio.load_image(bad)
    txt = tmp_path / "texto.txt"
    txt.write_text("não sou imagem")
    with pytest.raises(InvalidImageError):
        imageio.load_image(txt)
    empty = tmp_path / "vazia.png"
    empty.write_bytes(b"")
    with pytest.raises(InvalidImageError):
        imageio.load_image(empty)
    with pytest.raises(InvalidImageError):
        imageio.load_image(tmp_path / "nao_existe.png")
    tiny = tmp_path / "mini.png"
    Image.new("RGB", (4, 4)).save(tiny)
    with pytest.raises(InvalidImageError):
        imageio.load_image(tiny)


def test_grayscale_and_jpeg_inputs_are_converted(tmp_path):
    gray = make_image(tmp_path / "cinza.png", mode="L")
    assert imageio.load_image(gray).mode == "RGB"
    jpg = make_image(tmp_path / "foto.jpg", fmt="JPEG")
    assert imageio.load_image(jpg).mode == "RGB"
    assert imageio.is_lossy_input(jpg)


def test_corrupted_stego_header(cover):
    img = imageio.load_image(cover)
    out = stego.embed(img, b"abc" * 30, 1, False)
    arr = np.asarray(out).copy()
    flat = arr[..., :3].reshape(-1)
    flat[:32] ^= 1  # destrói a assinatura
    arr[..., :3] = flat.reshape(arr.shape[0], arr.shape[1], 3)
    with pytest.raises(NoHiddenDataError):
        stego.extract(Image.fromarray(arr))
