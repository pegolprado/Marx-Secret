import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image

from marx_secret.core import crypto
from marx_secret.data.database import Database
from marx_secret.services.operations import HideOptions, MarxSecretService

FAST_KDF = "rapido"
PASSWORD = "Senha-Forte#2026"


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MARX_SECRET_DATA_DIR", str(tmp_path / "appdata"))


def make_image(path, size=(160, 120), mode="RGB", seed=1, fmt=None):
    rng = np.random.default_rng(seed)
    channels = {"RGB": 3, "RGBA": 4, "L": 1}[mode]
    yy, xx = np.mgrid[0 : size[1], 0 : size[0]]
    base = ((xx * 255 / max(1, size[0] - 1) + yy * 128 / max(1, size[1] - 1)) % 256)
    arr = np.stack([base] * channels, axis=-1) + rng.normal(0, 12, (size[1], size[0], channels))
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    if mode == "L":
        arr = arr[..., 0]
    if mode == "RGBA":
        arr[..., 3] = 255
    Image.fromarray(arr).save(path, format=fmt)
    return str(path)


@pytest.fixture
def cover(tmp_path):
    return make_image(tmp_path / "capa.png")


@pytest.fixture
def big_cover(tmp_path):
    return make_image(tmp_path / "capa_grande.png", size=(640, 480), seed=7)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "teste.db")
    yield d
    d.close()


@pytest.fixture
def service(db):
    return MarxSecretService(db)


@pytest.fixture
def opts():
    return HideOptions(password=PASSWORD, kdf_profile=FAST_KDF, bits_per_channel=1,
                       scattered=True, compress=True)
