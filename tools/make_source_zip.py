"""Gera MARX_SECRET_Source.zip com o projeto completo (código, testes, docs, build).

Uso: python tools/make_source_zip.py [saida.zip]
Inclui apenas arquivos versionados no Git (ou, sem Git, a árvore filtrada).
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "build", "dist", "release", ".venv",
                "venv", ".venv-build", "dados", "saida"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
        files = [ROOT / f for f in out.stdout.decode("utf-8").split("\0") if f]
        if files:
            return [f for f in files if f.is_file()]
    except (OSError, subprocess.CalledProcessError):
        pass
    return [p for p in ROOT.rglob("*")
            if p.is_file() and not (set(p.relative_to(ROOT).parts) & EXCLUDE_DIRS)]


def main() -> Path:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "release" / "MARX_SECRET_Source.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in sorted(tracked_files()):
            zf.write(f, Path("MARX_SECRET_Source") / f.relative_to(ROOT))
    print(f"Código-fonte empacotado: {out}")
    return out


if __name__ == "__main__":
    main()
