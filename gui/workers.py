"""Background workers so the GUI thread never blocks on microphone or network."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, QThread, Signal

from core.voice_session import VoiceSession

log = logging.getLogger(__name__)


class Bridge(QObject):
    """Thread-safe signal hub. Emitting from any thread is delivered on the GUI thread."""

    message = Signal(str, str)   # role ("user" | "assistant"), text
    state = Signal(str)          # standby | listening | processing | speaking | error
    action = Signal(str)         # "exit"
    command_done = Signal()


class VoiceWorker(QThread):
    """Runs one VoiceSession. Only one instance may exist at a time (enforced by the window)."""

    def __init__(self, session: VoiceSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session

    def request_stop(self) -> None:
        self.session.request_stop()

    def run(self) -> None:
        self.session.run()


class CommandTask(QRunnable):
    """Runs Assistant.process off the GUI thread (network calls, SMTP, web lookups)."""

    def __init__(self, assistant, text: str, bridge: Bridge) -> None:
        super().__init__()
        self.assistant = assistant
        self.text = text
        self.bridge = bridge

    def run(self) -> None:
        try:
            self.bridge.state.emit("processing")
            replies = self.assistant.process(self.text, source="text")
            if any(r.action == "exit" for r in replies):
                self.bridge.action.emit("exit")
        except Exception:
            log.exception("Command task failed")
        finally:
            self.bridge.command_done.emit()
