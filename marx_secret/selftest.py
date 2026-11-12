"""Autodiagnóstico offline (``MARX_SECRET.exe --self-test``).

Valida, sem acesso à rede, todos os módulos essenciais no ambiente em que o
aplicativo foi instalado: criptografia, esteganografia, integridade, banco de
dados, análise, comparação, relatórios e interface gráfica.
"""

from __future__ import annotations

import os
import tempfile
import time
import traceback
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image


def _image(path: Path, w: int = 320, h: int = 240) -> str:
    rng = np.random.default_rng(42)
    yy, xx = np.mgrid[0:h, 0:w]
    base = (xx * 255 / w + yy * 90 / h) % 256
    arr = np.clip(np.stack([base, base[::-1], 255 - base], -1) + rng.normal(0, 10, (h, w, 3)),
                  0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path)
    return str(path)


def run_self_test(include_gui: bool = True) -> tuple[bool, list[str]]:
    from .core import analysis, compare, crypto
    from .core.errors import AuthenticationError
    from .core.payload import PayloadKind
    from .data.database import Database
    from .reports import csv_report, pdf_report
    from .services.operations import HideOptions, MarxSecretService

    lines: list[str] = []
    ok_all = True
    tmp = Path(tempfile.mkdtemp(prefix="marxsecret-selftest-"))
    db = Database(tmp / "selftest.db")
    svc = MarxSecretService(db)
    pwd = "Autoteste#MarxSecret2026"
    opts = HideOptions(password=pwd, kdf_profile="padrao", scattered=True)

    def check(name: str, fn: Callable[[], object]) -> None:
        nonlocal ok_all
        t0 = time.perf_counter()
        try:
            fn()
            lines.append(f"[OK]    {name} ({(time.perf_counter() - t0) * 1000:.0f} ms)")
        except Exception as exc:  # noqa: BLE001
            ok_all = False
            lines.append(f"[FALHA] {name}: {exc}")
            lines.append(traceback.format_exc())

    cover = _image(tmp / "capa.png")
    out = str(tmp / "saida.png")
    secret_file = tmp / "documento.bin"
    secret_file.write_bytes(os.urandom(4096))

    def t_crypto():
        key = crypto.derive_key(pwd, crypto.new_salt(), crypto.KDF_PROFILES["padrao"])
        n = crypto.new_nonce()
        assert crypto.aes_gcm_decrypt(key, n, crypto.aes_gcm_encrypt(key, n, b"x")) == b"x"

    def t_message():
        svc.hide_message(cover, out, "Mensagem de autoteste ✓", opts)
        assert svc.extract(out, pwd).payload.text == "Mensagem de autoteste ✓"

    def t_wrong_password():
        try:
            svc.extract(out, "senha-incorreta-123")
        except AuthenticationError:
            return
        raise AssertionError("senha incorreta não foi rejeitada")

    def t_file():
        out2 = str(tmp / "saida2.bmp")
        svc.hide_file(cover, out2, str(secret_file), opts)
        res = svc.extract(out2, pwd, PayloadKind.FILE)
        saved = svc.save_payload(res.payload, tmp)
        assert saved.read_bytes() == secret_file.read_bytes()

    def t_mxs():
        dst = str(tmp / "documento.bin.mxs")
        svc.encrypt_file(str(secret_file), dst, pwd, "rapido")
        rest = tmp / "restaurado"
        rest.mkdir()
        assert svc.decrypt_file(dst, str(rest), pwd).read_bytes() == secret_file.read_bytes()

    def t_analysis():
        r = analysis.analyze_image(out)
        assert r.signature.detected

    def t_compare():
        r = compare.compare_images(cover, out)
        assert r.psnr > 45

    def t_reports():
        recs = db.list_operations()
        pdf_report.history_report_pdf(recs, db.statistics(), tmp / "rel.pdf")
        csv_report.export_history_csv(recs, tmp / "rel.csv")
        assert (tmp / "rel.pdf").stat().st_size > 1000

    def t_history_privacy():
        raw = (tmp / "selftest.db").read_bytes()
        assert pwd.encode() not in raw and "autoteste ✓".encode() not in raw

    def t_gui():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from .ui.context import AppContext
        from .ui.main_window import MainWindow, apply_theme

        app = QApplication.instance() or QApplication([])
        ctx = AppContext(db)
        apply_theme(app, ctx.palette)
        win = MainWindow(ctx)
        for key in list(win.pages):
            win.go(key)
        win.close()

    check("Criptografia AES-256-GCM + Argon2id", t_crypto)
    check("Ocultação e extração de mensagem", t_message)
    check("Rejeição de senha incorreta", t_wrong_password)
    check("Ocultação e recuperação de arquivo", t_file)
    check("Criptografia de arquivos .mxs", t_mxs)
    check("Análise estatística", t_analysis)
    check("Comparação de imagens", t_compare)
    check("Relatórios PDF e CSV", t_reports)
    check("Privacidade do histórico", t_history_privacy)
    if include_gui:
        check("Interface gráfica", t_gui)
    db.close()
    from .core.secure_delete import secure_delete_tree

    secure_delete_tree(tmp)
    lines.insert(0, f"MARX SECRET – autodiagnóstico: {'APROVADO' if ok_all else 'REPROVADO'}")
    return ok_all, lines
