"""Runs network calls on Qt's thread pool so the GUI never freezes."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    """Owned by the main window so it always outlives queued signal delivery."""

    result = Signal(int, object)
    error = Signal(int, object)


class FetchTask(QRunnable):
    def __init__(self, token: int, signals: WorkerSignals, fn: Callable[[], object]):
        super().__init__()
        self._token, self._signals, self._fn = token, signals, fn

    def run(self) -> None:
        try:
            outcome = self._fn()
        except Exception as exc:  # noqa: BLE001 - every failure must reach the UI
            self._signals.error.emit(self._token, exc)
            return
        self._signals.result.emit(self._token, outcome)
