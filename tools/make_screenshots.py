"""Gera capturas de tela reais da interface (usadas no manual e no README).

Uso: python tools/make_screenshots.py [pasta_destino]   (padrão: docs/screenshots)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["MARX_SECRET_NO_DIALOGS"] = "1"
_tmp = Path(tempfile.mkdtemp(prefix="marx-shots-"))
os.environ["MARX_SECRET_DATA_DIR"] = str(_tmp / "dados")


def main() -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from marx_secret.core import paths
    from marx_secret.data.database import Database
    from marx_secret.selftest import _image
    from marx_secret.ui import worker
    from marx_secret.ui.context import AppContext
    from marx_secret.ui.main_window import MainWindow, apply_theme
    from marx_secret.ui.splash import splash_pixmap

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    db = Database(paths.database_path())
    db.set_setting("animations", False)
    db.set_setting("output_dir", str(_tmp))
    ctx = AppContext(db)

    def pump(ms: int = 300) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def shot(w, name: str) -> None:
        from marx_secret.ui.widgets import Toast

        pump(150)
        if Toast._current is not None:
            try:
                Toast._current.hide()
            except RuntimeError:
                pass
        w.grab().scaled(1280, 818).save(str(out / f"{name}.png"))

    cover = _image(_tmp / "paisagem.png", 900, 560)
    secret = _tmp / "contrato.pdf"
    secret.write_bytes(os.urandom(30000))
    for theme_name in ("escuro", "claro"):
        db.set_setting("theme", theme_name)
        apply_theme(app, ctx.palette)
        w = MainWindow(ctx)
        w.resize(1440, 920)
        w.show()
        suffix = "" if theme_name == "escuro" else "_claro"
        p = w.pages["hide_message"]
        w.go("hide_message")
        p.cover.set_path(cover)
        p.message.setPlainText("Reunião confirmada para sexta-feira às 18h. Código: ESMERALDA.")
        p.password.edit.setText("Esmeralda#2026!Forte")
        p.password.confirm.setText("Esmeralda#2026!Forte")
        p.output.set_path(str(_tmp / f"paisagem_marx{suffix}.png"))
        p._refresh()
        shot(w, "02_ocultar_mensagem" + suffix)
        if theme_name == "claro":
            w.go("dashboard")
            shot(w, "01_dashboard_claro")
            w.close()
            continue
        p.run()
        worker.wait_all()
        pump(400)
        stego = str(_tmp / "paisagem_marx.png")
        e = w.pages["extract_message"]
        w.go("extract_message")
        e.image.set_path(stego)
        e.password.edit.setText("Esmeralda#2026!Forte")
        e.run()
        worker.wait_all()
        pump(400)
        shot(w, "03_extrair_mensagem")
        hf = w.pages["hide_file"]
        w.go("hide_file")
        hf.cover.set_path(cover)
        hf.secret_file.set_path(str(secret))
        hf.password.edit.setText("Esmeralda#2026!Forte")
        hf.password.confirm.setText("Esmeralda#2026!Forte")
        hf.output.set_path(str(_tmp / "paisagem_arquivo.png"))
        hf.bpc.setCurrentIndex(1)
        shot(w, "04_ocultar_arquivo")
        hf.run()
        worker.wait_all()
        pump(400)
        r = w.pages["recover_file"]
        w.go("recover_file")
        r.image.set_path(str(_tmp / "paisagem_arquivo.png"))
        r.password.edit.setText("Esmeralda#2026!Forte")
        r.run()
        worker.wait_all()
        pump(400)
        shot(w, "05_recuperar_arquivo")
        w.go("crypto")
        w.pages["crypto"].tabs.setCurrentIndex(2)
        w.pages["crypto"].generate()
        shot(w, "06_criptografia")
        a = w.pages["analysis"]
        w.go("analysis")
        a.image.set_path(stego)
        a.run()
        worker.wait_all()
        pump(400)
        shot(w, "07_analise")
        ctx.request_compare.emit(cover, stego)
        worker.wait_all()
        pump(400)
        shot(w, "08_comparacao")
        for key, name in (("history", "09_historico"), ("reports", "10_relatorios"),
                          ("files", "11_arquivos"), ("settings", "12_configuracoes"),
                          ("about", "13_sobre"), ("dashboard", "01_dashboard")):
            w.go(key)
            if key == "files":
                w.pages["files"].folder.set_path(str(_tmp))
            shot(w, name)
        w.close()
    splash_pixmap().save(str(out / "00_abertura.png"))
    db.close()
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"Capturas salvas em {out}")


if __name__ == "__main__":
    main()
