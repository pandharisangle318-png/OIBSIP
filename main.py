"""VYOM - Intelligent Personal Voice Assistant (entry point).

    python main.py          start the graphical assistant
    python main.py --cli    text-only console mode (no PySide6 / microphone needed)
"""
from __future__ import annotations

import sys

from core.config import Config
from core.logging_setup import setup_logging


def run_cli(config: Config) -> int:
    from core.assistant import Assistant

    def show(role: str, text: str) -> None:
        if role == "assistant":
            print(f"VYOM > {text}")

    assistant = Assistant(config, on_message=show)
    print("VYOM console mode. Type a command (or 'exit assistant' to quit).")
    try:
        while True:
            try:
                line = input("You  > ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            replies = assistant.process(line, source="text")
            if any(r.action == "exit" for r in replies):
                break
    finally:
        assistant.shutdown()
    return 0


def run_gui(config: Config) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run setup.bat (or: pip install -r requirements.txt).")
        print("You can still try the text-only mode: python main.py --cli")
        return 1
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("VYOM")
    window = MainWindow(config)
    window.show()
    return app.exec()


def main() -> int:
    config = Config()
    setup_logging(config.log_dir, config.secrets)
    if "--cli" in sys.argv[1:]:
        return run_cli(config)
    return run_gui(config)


if __name__ == "__main__":
    sys.exit(main())
