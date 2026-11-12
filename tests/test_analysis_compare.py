import math

import pytest

from marx_secret.core import analysis, compare
from marx_secret.core.errors import InvalidInputError
from marx_secret.services.operations import HideOptions

from .conftest import PASSWORD, make_image


def test_clean_image_analysis(big_cover):
    r = analysis.analyze_image(big_cover)
    assert r.width == 640 and r.height == 480
    assert not r.signature.detected
    assert r.histograms.shape == (3, 256)
    assert r.histograms[0].sum() == 640 * 480
    assert len(r.chi_square_sequence) == 20
    assert all(0 <= c.entropy <= 8 for c in r.channels)
    assert r.capacity[2] > r.capacity[1]


def test_signature_detected_and_metadata(service, big_cover, tmp_path):
    out = str(tmp_path / "s.png")
    service.hide_message(big_cover, out, "x" * 3000,
                         HideOptions(password=PASSWORD, kdf_profile="rapido", scattered=False))
    r = analysis.analyze_image(out)
    assert r.signature.detected and r.signature.encrypted
    assert r.signature.bits_per_channel == 1 and r.signature.scattered is False
    assert "Argon2id" in r.signature.kdf
    assert r.suspicion_label == "Alto"


def test_chi_square_detects_full_lsb_embedding(big_cover):
    import numpy as np
    from PIL import Image

    img = np.asarray(Image.open(big_cover)).copy()
    rng = np.random.default_rng(3)
    img = (img & 0xFE) | rng.integers(0, 2, img.shape, dtype=np.uint8)
    p_stego = analysis.chi_square_probability(img)
    p_clean = analysis.chi_square_probability(np.asarray(Image.open(big_cover)))
    assert p_stego > 0.9
    assert p_clean < p_stego


def test_gammaincc_reference_values():
    assert analysis._gammaincc(1.0, 1.0) == pytest.approx(math.exp(-1), rel=1e-9)
    assert analysis._gammaincc(2.5, 3.0) == pytest.approx(0.30621892, rel=1e-6)
    assert analysis._gammaincc(10.0, 2.0) == pytest.approx(0.99995350, rel=1e-6)


def test_lsb_plane(big_cover):
    from marx_secret.core import imageio

    img = imageio.load_image(big_cover)
    assert analysis.lsb_plane(img).size == img.size
    assert analysis.lsb_plane(img, 0).mode == "L"


def test_compare_identical_and_processed(service, big_cover, tmp_path):
    r = compare.compare_images(big_cover, big_cover)
    assert r.identical and math.isinf(r.psnr) and r.ssim == pytest.approx(1.0)
    out = str(tmp_path / "s.png")
    service.hide_message(big_cover, out, "y" * 500,
                         HideOptions(password=PASSWORD, kdf_profile="rapido"))
    r = compare.compare_images(big_cover, out)
    assert not r.identical and r.max_abs_diff == 1
    assert r.psnr > 50 and r.ssim > 0.99
    assert r.quality_label == "Imperceptível"
    assert compare.difference_image(big_cover, out).size == (640, 480)


def test_compare_size_mismatch(tmp_path, big_cover):
    other = make_image(tmp_path / "outra.png", size=(100, 100))
    with pytest.raises(InvalidInputError):
        compare.compare_images(big_cover, other)
