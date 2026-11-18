"""Main VYOM window (PySide6)."""
from __future__ import annotations

import logging
import math
import random
from datetime import datetime

from PySide6.QtCore import QThreadPool, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from core.assistant import Assistant
from core.config import Config
from core.listener import Listener
from core.text_to_speech import Speaker
from core.voice_session import VoiceSession
from gui import styles
from gui.workers import Bridge, CommandTask, VoiceWorker

log = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    """Animated mint-green voice visualisation that reacts to the assistant state."""

    BARS = 56

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self._state = "standby"
        self._phase = 0.0
        self._noise = [random.random() for _ in range(self.BARS)]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_state(self, state: str) -> None:
        self._state = state

    def _amplitude(self, i: int) -> float:
        wave = math.sin(self._phase + i * 0.35)
        if self._state == "listening":
            return 0.30 + 0.22 * abs(wave) + 0.18 * self._noise[i]
        if self._state == "speaking":
            return 0.35 + 0.45 * abs(math.sin(self._phase * 1.3 + i * 0.5)) * (0.6 + 0.4 * self._noise[i])
        if self._state == "processing":
            return 0.15 + 0.40 * max(0.0, math.sin(self._phase * 2 - i * 0.25))
        return 0.07 + 0.03 * wave

    def _tick(self) -> None:
        self._phase += 0.22
        if int(self._phase * 10) % 3 == 0:
            self._noise = [random.random() for _ in range(self.BARS)]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        gap = 4
        bar_w = max(3.0, (w - gap * (self.BARS + 1)) / self.BARS)
        top = QColor(styles.STATE_COLORS.get(self._state, styles.MINT))
        if self._state in ("listening", "standby"):
            top = QColor(styles.MINT)
        bottom = QColor(styles.PURPLE)
        for i in range(self.BARS):
            amp = max(0.04, min(1.0, self._amplitude(i)))
            bar_h = amp * (h - 10)
            x = gap + i * (bar_w + gap)
            y = (h - bar_h) / 2
            gradient = QLinearGradient(x, y, x, y + bar_h)
            gradient.setColorAt(0.0, top)
            gradient.setColorAt(1.0, bottom)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, bar_w / 2, bar_w / 2)
        painter.end()


class ChatView(QScrollArea):
    """Conversation panel with separate user and assistant bubbles."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._content = QWidget()
        self._content.setObjectName("chatContent")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)

    def add_message(self, role: str, text: str) -> None:
        user = role == "user"
        bubble = QFrame()
        bubble.setObjectName("userBubble" if user else "assistantBubble")
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 8, 14, 10)
        inner.setSpacing(2)
        who = QLabel("You" if user else "VYOM")
        who.setObjectName("bubbleRole")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMaximumWidth(560)
        inner.addWidget(who)
        inner.addWidget(body)
        row = QHBoxLayout()
        if user:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        self._layout.insertWidget(self._layout.count() - 1, holder)
        QTimer.singleShot(30, self._scroll_to_end)

    def _scroll_to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def clear_messages(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VYOM Settings and Configuration")
        self.resize(560, 460)
        layout = QVBoxLayout(self)
        info = QTextEdit()
        info.setReadOnly(True)
        s = config.summary()
        yes_no = lambda ok: "configured" if ok else "NOT configured"  # noqa: E731
        info.setPlainText(
            "Secrets are read from the .env file (never shown here).\n\n"
            f"Email (Gmail App Password): {yes_no(s['email_configured'])}\n"
            f"Weather (OpenWeatherMap key): {yes_no(s['weather_configured'])}\n"
            f".env file present: {s['env_file_found']}\n"
            f"config.json present: {s['config_file_found']}\n\n"
            f"Recognition language: {s['language']}\n"
            f"Listen timeout: {s['listen_timeout']} s, phrase limit: {s['phrase_time_limit']} s\n"
            f"Voice rate: {s['voice_rate']}, volume: {s['voice_volume']}\n"
            f"Default weather city: {s['default_city']}\n"
            f"Online knowledge lookup: {'on' if s['online_lookup'] else 'off'}\n\n"
            "To change anything, edit these files in the project folder and restart VYOM:\n"
            "  .env                      secrets (copy from .env.example)\n"
            "  config.json               voice, speech and preference settings\n"
            "  data/custom_commands.json your own commands\n"
            "  data/knowledge_base.json  offline knowledge base\n\n"
            f"Project folder: {s['project_folder']}"
        )
        layout.addWidget(info)
        row = QHBoxLayout()
        open_btn = QPushButton("Open Project Folder")
        close_btn = QPushButton("Close")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(s["project_folder"])))
        close_btn.clicked.connect(self.accept)
        row.addWidget(open_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        layout.addLayout(row)


class MainWindow(QWidget):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("VYOM - Intelligent Voice Assistant")
        self.resize(980, 780)
        self.setStyleSheet(styles.STYLESHEET)

        self.bridge = Bridge()
        self.bridge.message.connect(self.on_message)
        self.bridge.state.connect(self.set_state)
        self.bridge.action.connect(self.on_action)
        self.bridge.command_done.connect(self._command_done)

        self.speaker = Speaker(config.get("voice", {}), on_state=self._speaker_state)
        self.assistant = Assistant(config, speaker=self.speaker, on_message=self.bridge.message.emit)
        self.listener = Listener(config.get("speech", {}))
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)  # commands run one at a time, in order
        self.voice_worker = None
        self._pending_commands = 0
        self._closing = False

        self._build_ui()
        self._start_clock()
        self.set_state("standby")
        self.chat.add_message("assistant", "Hello! I am VYOM. Press Start Assistant to talk, or type a command below.")
        self._warn_about_configuration()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        brand = QLabel("VYOM")
        brand.setObjectName("brand")
        tagline = QLabel("Intelligent Personal Voice Assistant")
        tagline.setObjectName("tagline")
        titles.addWidget(brand)
        titles.addWidget(tagline)
        header.addLayout(titles)
        header.addStretch(1)
        clock_box = QVBoxLayout()
        self.clock_label = QLabel()
        self.clock_label.setObjectName("clock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label = QLabel()
        self.date_label.setObjectName("date")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.date_label)
        header.addLayout(clock_box)
        root.addLayout(header)

        self.wave = WaveformWidget()
        root.addWidget(self.wave)

        status_row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.mic_label = QLabel()
        self.mic_label.setObjectName("tagline")
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.mic_label)
        status_row.addStretch(1)
        root.addLayout(status_row)

        self.chat = ChatView()
        root.addWidget(self.chat, 1)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("Start Assistant")
        self.start_btn.setObjectName("start")
        self.stop_btn = QPushButton("Stop Assistant")
        self.stop_btn.setObjectName("stop")
        self.mute_btn = QPushButton("Mute Voice")
        self.clear_btn = QPushButton("Clear")
        self.settings_btn = QPushButton("Settings")
        for btn in (self.start_btn, self.stop_btn, self.mute_btn, self.clear_btn, self.settings_btn):
            controls.addWidget(btn)
        root.addLayout(controls)

        quick = QHBoxLayout()
        self.quick_buttons = {}
        for label, handler in (
            ("Time", self.quick_time), ("Date", self.quick_date), ("Help", self.quick_help),
            ("Weather", self.quick_weather), ("Search", self.quick_search), ("Email", self.quick_email),
        ):
            btn = QPushButton(label)
            btn.setObjectName("quick")
            btn.clicked.connect(handler)
            quick.addWidget(btn)
            self.quick_buttons[label] = btn
        root.addLayout(quick)

        entry = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command, for example: what is the time")
        self.send_btn = QPushButton("Send")
        entry.addWidget(self.input, 1)
        entry.addWidget(self.send_btn)
        root.addLayout(entry)

        self.start_btn.clicked.connect(self.start_assistant)
        self.stop_btn.clicked.connect(self.stop_assistant)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.clear_btn.clicked.connect(self.clear_conversation)
        self.settings_btn.clicked.connect(self.show_settings)
        self.send_btn.clicked.connect(self.send_typed_command)
        self.input.returnPressed.connect(self.send_typed_command)

    def _start_clock(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self) -> None:
        now = datetime.now()
        self.clock_label.setText(now.strftime("%I:%M:%S %p").lstrip("0"))
        self.date_label.setText(f"{now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}")

    def _warn_about_configuration(self) -> None:
        notes = []
        if not self.config.weather_configured:
            notes.append("Weather needs OPENWEATHER_API_KEY in .env.")
        if not self.config.email_configured:
            notes.append("Email needs EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env.")
        if notes:
            self.chat.add_message("assistant", "Setup note: " + " ".join(notes) + " Everything else works now. See Settings for details.")

    # ----------------------------------------------------------------- state
    def _speaker_state(self, state: str) -> None:
        """Called from the speech thread."""
        if self._closing:
            return
        if state == "speaking":
            self.bridge.state.emit("speaking")
        elif self.voice_worker is None or not self.voice_worker.isRunning():
            self.bridge.state.emit("standby")

    def set_state(self, state: str) -> None:
        names = {"standby": "Standby", "listening": "Listening", "processing": "Processing",
                 "speaking": "Speaking", "error": "Error"}
        color = styles.STATE_COLORS.get(state, styles.MUTED)
        self.status_label.setText(f"\u25cf {names.get(state, state)}")
        self.status_label.setStyleSheet(f"color: {color};")
        self.wave.set_state(state)
        self.mic_label.setText("Microphone active" if state == "listening" else "Microphone idle")

    def _command_done(self) -> None:
        """A typed command finished: go back to standby unless voice or speech is still active."""
        if not self.voice_running() and self.speaker.wait_idle(timeout=0):
            self.set_state("standby")

    def on_message(self, role: str, text: str) -> None:
        self.chat.add_message(role, text)

    def on_action(self, action: str) -> None:
        if action == "exit":
            self.close()

    # -------------------------------------------------------------- controls
    def voice_running(self) -> bool:
        return self.voice_worker is not None and self.voice_worker.isRunning()

    def start_assistant(self) -> None:
        if self.voice_running():  # never create a second listening thread
            return
        session = VoiceSession(
            self.assistant, self.listener,
            max_failures=int(self.config.get("speech.max_consecutive_failures", 3)),
            on_state=self.bridge.state.emit, on_action=self.bridge.action.emit,
        )
        self.voice_worker = VoiceWorker(session)
        self.voice_worker.finished.connect(self._voice_finished)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.voice_worker.start()

    def stop_assistant(self) -> None:
        if self.voice_running():
            self.voice_worker.request_stop()
            self.speaker.clear()
            self.stop_btn.setEnabled(False)
            self.status_label.setText("\u25cf Stopping...")

    def _voice_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_state("standby")

    def toggle_mute(self) -> None:
        self.speaker.set_muted(not self.speaker.muted)
        self.mute_btn.setText("Unmute Voice" if self.speaker.muted else "Mute Voice")

    def clear_conversation(self) -> None:
        self.chat.clear_messages()

    def show_settings(self) -> None:
        SettingsDialog(self.config, self).exec()

    # --------------------------------------------------------------- commands
    def run_command(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.pool.start(CommandTask(self.assistant, text, self.bridge))

    def send_typed_command(self) -> None:
        text = self.input.text().strip()
        self.input.clear()
        self.run_command(text)

    def quick_time(self) -> None:
        self.run_command("what is the time")

    def quick_date(self) -> None:
        self.run_command("what is today's date")

    def quick_help(self) -> None:
        self.run_command("help")

    def quick_weather(self) -> None:
        default = str(self.config.get("assistant.default_city") or "")
        city, ok = QInputDialog.getText(self, "Weather", "Which city?", text=default)
        if ok and city.strip():
            self.run_command(f"what is the weather in {city.strip()}")

    def quick_search(self) -> None:
        query, ok = QInputDialog.getText(self, "Search", "What should I search for on Google?")
        if ok and query.strip():
            self.run_command(f"search for {query.strip()}")

    def quick_email(self) -> None:
        self.run_command("send an email")
        self.input.setFocus()

    # ---------------------------------------------------------------- closing
    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        if self.voice_running():
            self.voice_worker.request_stop()
            self.voice_worker.wait(5000)
        self.pool.waitForDone(3000)
        self.assistant.shutdown()
        event.accept()
