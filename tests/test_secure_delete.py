import os

import pytest

from marx_secret.core import secure_delete as sd
from marx_secret.core.errors import InvalidInputError


def test_secure_delete_file(tmp_path):
    f = tmp_path / "segredo.txt"
    f.write_bytes(b"A" * 5000)
    sd.secure_delete(f)
    assert not f.exists()
    assert os.listdir(tmp_path) == []


def test_secure_delete_errors(tmp_path):
    with pytest.raises(InvalidInputError):
        sd.secure_delete(tmp_path / "nao_existe")
    with pytest.raises(InvalidInputError):
        sd.secure_delete(tmp_path)


def test_secure_temp_dir():
    with sd.secure_temp_dir() as d:
        (d / "a.bin").write_bytes(b"x" * 100)
        (d / "sub").mkdir()
        (d / "sub" / "b.bin").write_bytes(b"y")
        path = d
    assert not path.exists()


def test_cleanup_stale_temp(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    (tmp_path / "marxsecret-velho").mkdir()
    (tmp_path / "marxsecret-velho" / "x").write_bytes(b"1")
    assert sd.cleanup_stale_temp() == 1
    assert not (tmp_path / "marxsecret-velho").exists()
