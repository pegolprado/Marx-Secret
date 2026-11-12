"""Exclusão segura (melhor esforço) e gerenciamento de arquivos temporários.

Observação: em SSDs (wear leveling), sistemas com journaling, cópias de sombra
ou armazenamento em nuvem, a sobrescrita não garante a eliminação física de
todas as cópias. Por isso a exclusão é descrita como "quando tecnicamente
possível" na interface e no manual.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .errors import InvalidInputError


def secure_delete(path: str | os.PathLike, passes: int = 3) -> None:
    """Sobrescreve o arquivo com dados aleatórios e zeros e então o remove."""
    p = Path(path)
    if not p.exists():
        raise InvalidInputError("O arquivo não existe.")
    if not p.is_file() or p.is_symlink():
        raise InvalidInputError("Apenas arquivos regulares podem ser excluídos com segurança.")
    size = p.stat().st_size
    chunk = 1024 * 1024
    try:
        with open(p, "r+b", buffering=0) as fh:
            for i in range(max(1, passes)):
                fh.seek(0)
                remaining = size
                while remaining > 0:
                    n = min(chunk, remaining)
                    fh.write(os.urandom(n) if i < passes - 1 else b"\x00" * n)
                    remaining -= n
                fh.flush()
                os.fsync(fh.fileno())
        # renomeia para ocultar o nome original antes de remover
        anon = p.with_name("." + os.urandom(8).hex())
        os.replace(p, anon)
        anon.unlink()
    except PermissionError as exc:
        raise InvalidInputError("Sem permissão para excluir o arquivo.") from exc


def secure_delete_tree(path: str | os.PathLike) -> None:
    root = Path(path)
    if not root.exists():
        return
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            try:
                secure_delete(Path(dirpath) / name, passes=1)
            except (InvalidInputError, OSError):
                pass
    shutil.rmtree(root, ignore_errors=True)


@contextmanager
def secure_temp_dir(prefix: str = "marxsecret-"):
    """Diretório temporário privado, apagado com sobrescrita ao final."""
    d = tempfile.mkdtemp(prefix=prefix)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    try:
        yield Path(d)
    finally:
        secure_delete_tree(d)


def cleanup_stale_temp(prefix: str = "marxsecret-") -> int:
    """Remove temporários esquecidos por execuções interrompidas."""
    count = 0
    tmp = Path(tempfile.gettempdir())
    for item in tmp.glob(prefix + "*"):
        if item.is_dir():
            secure_delete_tree(item)
            count += 1
    return count
