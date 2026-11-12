"""Execução de tarefas pesadas fora da thread da interface."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..core.errors import MarxSecretError


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except MarxSecretError as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - salvaguarda
            traceback.print_exc()
            self.signals.failed.emit(f"Erro inesperado: {exc}")
        else:
            self.signals.finished.emit(result)


_active: set[Task] = set()


def run_task(fn: Callable[[], Any], on_done: Callable[[Any], None],
             on_error: Callable[[str], None]) -> Task:
    """Executa ``fn`` em segundo plano e chama os callbacks na thread da interface."""
    task = Task(fn)
    _active.add(task)

    def done(result):
        _active.discard(task)
        on_done(result)

    def fail(msg):
        _active.discard(task)
        on_error(msg)

    task.signals.finished.connect(done)
    task.signals.failed.connect(fail)
    QThreadPool.globalInstance().start(task)
    return task


def wait_all(timeout_ms: int = 30000) -> bool:
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
