"""Run blocking work (probe, privilege escalation) off the UI thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_LIVE_TASKS: set[Task] = set()


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class Task(QRunnable):
    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self.setAutoDelete(False)
        self._fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(str(exc))
        else:
            self.signals.done.emit(result)


def run_in_background(
    fn: Callable[[], object],
    on_done: Callable[[object], None],
    on_error: Callable[[str], None],
) -> None:
    task = Task(fn)
    _LIVE_TASKS.add(task)
    task.signals.done.connect(lambda result: (_LIVE_TASKS.discard(task), on_done(result)))
    task.signals.error.connect(lambda msg: (_LIVE_TASKS.discard(task), on_error(msg)))
    QThreadPool.globalInstance().start(task)
