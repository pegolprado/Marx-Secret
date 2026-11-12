"""Organiza a entrega final do MARX SECRET em quatro pastas nomeadas.

release/
  MARX_SECRET_Entrega/
    Marx Secret - Instalação tradicional no Windows/MARX_SECRET_Setup.exe
    Marx Secret - Executar sem instalação tradicional/MARX_SECRET_Portable.zip
    Marx Secret - Projeto completo e código-fonte/MARX_SECRET_Source.zip
    Marx Secret - Manual de instalação e utilização/Manual_MARX_SECRET.pdf
  SHA256SUMS.txt
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"

DELIVERY = {
    "Marx Secret - Instalação tradicional no Windows": "MARX_SECRET_Setup.exe",
    "Marx Secret - Executar sem instalação tradicional": "MARX_SECRET_Portable.zip",
    "Marx Secret - Projeto completo e código-fonte": "MARX_SECRET_Source.zip",
    "Marx Secret - Manual de instalação e utilização": "Manual_MARX_SECRET.pdf",
}

README = {
    "Marx Secret - Instalação tradicional no Windows":
        "Execute MARX_SECRET_Setup.exe e siga o assistente.\n"
        "Requisitos: Windows 10 (1809+) ou 11, 64 bits. Não é necessário instalar Python.\n"
        "Cria atalhos no Menu Iniciar e na Área de Trabalho e permite desinstalação completa.\n",
    "Marx Secret - Executar sem instalação tradicional":
        "Extraia MARX_SECRET_Portable.zip para qualquer pasta ou pendrive e execute\n"
        "MARX_SECRET.exe. Os dados ficam na subpasta 'dados' (nada é gravado no sistema).\n",
    "Marx Secret - Projeto completo e código-fonte":
        "Código-fonte completo, testes automatizados, scripts de build (PyInstaller e Inno\n"
        "Setup) e documentação técnica. Veja README.md dentro do arquivo.\n",
    "Marx Secret - Manual de instalação e utilização":
        "Manual completo de instalação e utilização em PDF.\n",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    target = RELEASE / "MARX_SECRET_Entrega"
    if target.exists():
        shutil.rmtree(target)
    missing = []
    sums = []
    for folder, filename in DELIVERY.items():
        src = RELEASE / filename
        if not src.exists():
            missing.append(filename)
            continue
        d = target / folder
        d.mkdir(parents=True)
        shutil.copy2(src, d / filename)
        (d / "LEIA-ME.txt").write_text(README[folder], encoding="utf-8")
        sums.append(f"{sha256(src)}  {filename}")
    (RELEASE / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    shutil.copy2(RELEASE / "SHA256SUMS.txt", target / "SHA256SUMS.txt")
    if missing:
        print("Arquivos ausentes: " + ", ".join(missing))
        return 1
    print(f"Entrega organizada em {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
