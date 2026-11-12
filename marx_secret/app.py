"""Ponto de entrada do MARX SECRET."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import APP_COMMERCIAL_NAME, APP_NAME, APP_ORGANIZATION, __version__


def _setup_logging() -> None:
    from .core import paths

    handler = RotatingFileHandler(paths.log_path(), maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("marx_secret")
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="MARX_SECRET", description=APP_COMMERCIAL_NAME)
    ap.add_argument("--version", action="store_true", help="mostra a versão e sai")
    ap.add_argument("--self-test", action="store_true", help="executa o autodiagnóstico offline")
    ap.add_argument("--report", help="arquivo onde gravar o resultado do autodiagnóstico")
    ap.add_argument("--no-gui-test", action="store_true",
                    help="no autodiagnóstico, não testa a interface gráfica")
    ap.add_argument("--no-splash", action="store_true", help="inicia sem tela de abertura")
    ap.add_argument("image", nargs="?", help="imagem para abrir na análise")
    args, _unknown = ap.parse_known_args(argv)
    return args


def _write_output(text: str, report: str | None) -> None:
    if report:
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    try:
        if sys.stdout:
            print(text)
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    args = _parse(sys.argv[1:] if argv is None else argv)
    if args.version:
        _write_output(f"{APP_NAME} {__version__}", args.report)
        return 0
    if args.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from .selftest import run_self_test

        ok, lines = run_self_test(include_gui=not args.no_gui_test)
        _write_output("\n".join(lines), args.report)
        return 0 if ok else 1

    _setup_logging()
    from PySide6.QtCore import QCoreApplication, Qt, QTimer
    from PySide6.QtWidgets import QApplication

    QCoreApplication.setOrganizationName(APP_ORGANIZATION)
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "MarxSecret.Professional.1")
            # Mutex usado pelo instalador para detectar o aplicativo em execução
            _mutex = ctypes.windll.kernel32.CreateMutexW(None, False,  # noqa: F841
                                                         "MarxSecretProfessionalMutex")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationDisplayName(APP_NAME)

    from .core import paths
    from .core.secure_delete import cleanup_stale_temp
    from .data.database import Database
    from .ui import icons
    from .ui.context import AppContext
    from .ui.main_window import MainWindow, apply_theme
    from .ui.splash import SplashScreen

    app.setWindowIcon(icons.app_icon())
    db = Database(paths.database_path())
    ctx = AppContext(db)
    apply_theme(app, ctx.palette)
    splash = None
    if not args.no_splash:
        splash = SplashScreen()
        splash.show()
        app.processEvents()
    cleanup_stale_temp()
    window = MainWindow(ctx)

    def show():
        if splash:
            splash.finish(window)
        window.show()
        if args.image and os.path.isfile(args.image):
            window.go("analysis")
            ctx.request_analysis.emit(args.image)

    QTimer.singleShot(1200 if splash else 0, show)
    code = app.exec()
    from .ui.worker import wait_all

    wait_all(10000)
    db.close()
    logging.getLogger("marx_secret").info("Encerrado")
    _ = Qt  # mantém import para empacotamento
    return code


if __name__ == "__main__":
    sys.exit(main())
