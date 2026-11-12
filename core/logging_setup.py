"""Logging with automatic secret redaction."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Iterable


class RedactingFilter(logging.Filter):
    """Replaces any known secret value found in a log record with ***."""

    def __init__(self, secrets_provider: Callable[[], Iterable[str]]) -> None:
        super().__init__()
        self._provider = secrets_provider

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            for secret in self._provider():
                if secret and secret in message:
                    message = message.replace(secret, "***")
            record.msg = message
            record.args = None
        except Exception:  # never let logging break the app
            pass
        return True


def setup_logging(log_dir: Path, secrets_provider: Callable[[], Iterable[str]]) -> None:
    log_dir = Path(log_dir)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        if getattr(handler, "_vyom", False):
            root.removeHandler(handler)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    redactor = RedactingFilter(secrets_provider)
    handlers = []
    try:
        handlers.append(RotatingFileHandler(log_dir / "vyom.log", maxBytes=500_000, backupCount=2, encoding="utf-8"))
    except OSError:
        pass
    handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(fmt)
        handler.addFilter(redactor)
        handler._vyom = True  # type: ignore[attr-defined]
        root.addHandler(handler)
