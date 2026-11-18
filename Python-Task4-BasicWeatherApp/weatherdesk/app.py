"""Application bootstrap."""
from __future__ import annotations

import sys

from . import APP_NAME


def run() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run:  pip install -r requirements.txt", file=sys.stderr)
        return 1

    from .config import load_config
    from .ui.main_window import MainWindow
    from .ui.theme import make_font

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(make_font(13))
    window = MainWindow(load_config())
    window.show()
    window.search_edit.setFocus()
    return app.exec()
