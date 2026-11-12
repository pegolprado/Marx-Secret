from pathlib import Path

from marx_secret import APP_NAME, __version__
from marx_secret.app import main
from marx_secret.core import paths


def test_portable_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("MARX_SECRET_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "app_base_dir", lambda: tmp_path)
    assert not paths.is_portable()
    (tmp_path / paths.PORTABLE_FLAG).write_text("x")
    assert paths.is_portable()
    assert paths.data_dir() == tmp_path / "dados"
    assert paths.default_output_dir() == tmp_path / "saida"
    assert paths.database_path().parent == tmp_path / "dados"


def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("MARX_SECRET_DATA_DIR", str(tmp_path / "x"))
    assert paths.data_dir() == tmp_path / "x" and (tmp_path / "x").is_dir()


def test_resources_exist():
    for name in ("logo.svg", "check.svg", "marx_secret.ico", "logo_256.png", "banner.jpg"):
        assert (paths.resource_dir() / name).exists()


def test_cli_version_and_selftest(tmp_path):
    rep = tmp_path / "v.txt"
    assert main(["--version", "--report", str(rep)]) == 0
    assert rep.read_text(encoding="utf-8").strip() == f"{APP_NAME} {__version__}"
    rep2 = tmp_path / "s.txt"
    assert main(["--self-test", "--no-gui-test", "--report", str(rep2)]) == 0
    assert "APROVADO" in rep2.read_text(encoding="utf-8")


def test_no_legacy_names_in_project():
    root = Path(__file__).resolve().parents[1]
    legacy = ("STEGA" + " PRO", "STEGA" + "PRO", "Stega" + "Tool")
    for f in root.rglob("*"):
        if f.is_file() and f.suffix in {".py", ".md", ".txt", ".iss", ".spec", ".yml", ".toml",
                                         ".ps1", ".svg"} and ".git" not in f.parts:
            text = f.read_text(encoding="utf-8", errors="ignore").upper()
            for name in legacy:
                assert name.upper() not in text, f"{name} encontrado em {f}"
