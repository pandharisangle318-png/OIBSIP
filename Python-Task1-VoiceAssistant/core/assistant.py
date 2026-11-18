"""Assistant: owns the services, serialises commands and announces replies."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable, Optional

from core.command_handler import CommandHandler, Reply
from core.config import Config
from core.nlp import KnowledgeBase
from core.text_to_speech import NullSpeaker
from features.custom_commands import CustomCommands
from features.email_service import EmailService
from features.online_lookup import OnlineLookup
from features.reminder_service import ReminderService, play_alert_sound
from features.search_service import SearchService
from features.weather_service import WeatherService

log = logging.getLogger(__name__)


class Assistant:
    """Qt-free controller used by both the GUI and the console mode."""

    def __init__(
        self,
        config: Optional[Config] = None,
        speaker=None,
        on_message: Optional[Callable[[str, str], None]] = None,
        handler: Optional[CommandHandler] = None,
        alert: Callable[[], None] = play_alert_sound,
    ) -> None:
        self.config = config or Config()
        self.speaker = speaker or NullSpeaker()
        self.on_message = on_message or (lambda role, text: None)
        self._alert = alert
        self._lock = threading.RLock()
        self.reminders = ReminderService(self._on_reminder, max_seconds=float(self.config.get("reminders.max_seconds", 86400)))
        self.handler = handler or self._build_handler()

    def _build_handler(self) -> CommandHandler:
        cfg = self.config
        kb = KnowledgeBase.from_file(cfg.data_dir / "knowledge_base.json")
        custom = CustomCommands.from_file(cfg.data_dir / "custom_commands.json")
        weather = WeatherService(cfg.weather_api_key, cfg.get("weather.units", "metric"), cfg.get("weather.timeout", 10))
        email = EmailService(cfg.email_address, cfg.email_app_password, cfg.get("email.smtp_host"),
                             cfg.get("email.smtp_port"), cfg.get("email.timeout"))
        online = OnlineLookup() if cfg.get("assistant.online_lookup", True) else None
        return CommandHandler(cfg, kb, custom, weather, email, SearchService(), self.reminders, online=online)

    @property
    def expects_reply(self) -> bool:
        return self.handler.expects_reply

    # --------------------------------------------------------------- messages
    def _emit(self, role: str, text: str) -> None:
        try:
            self.on_message(role, text)
        except Exception:
            log.exception("on_message callback failed")

    def announce(self, text: str, speak: bool = True) -> None:
        """Show (and optionally speak) an assistant message that is not a command reply."""
        self._emit("assistant", text)
        if speak:
            self.speaker.say(text)

    def process(self, text: str, source: str = "text") -> list:
        """Handle one user command. Blocking: call from a worker thread, never the GUI thread."""
        text = (text or "").strip()
        if not text:
            return []
        with self._lock:
            self._emit("user", text)
            try:
                replies = self.handler.handle(text)
            except Exception:
                log.exception("Command failed")
                replies = [Reply("Sorry, something went wrong while handling that command.")]
            for reply in replies:
                self._emit("assistant", reply.text)
                self.speaker.say(reply.speech or reply.text)
            return replies

    def _on_reminder(self, reminder) -> None:
        message = f"Reminder: {reminder.message}"
        self._emit("assistant", message)
        try:
            self._alert()
        except Exception:
            log.exception("Alert sound failed")
        self.speaker.say(f"Reminder. {reminder.message}")

    def shutdown(self) -> None:
        self.reminders.shutdown()
        self.speaker.shutdown()
