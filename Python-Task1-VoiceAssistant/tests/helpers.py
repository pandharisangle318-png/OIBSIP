"""Shared fakes for the VYOM test-suite (no network, no hardware)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.command_handler import CommandHandler  # noqa: E402
from core.config import Config  # noqa: E402
from core.nlp import KnowledgeBase  # noqa: E402
from features.custom_commands import CustomCommands  # noqa: E402
from features.email_service import EmailService  # noqa: E402
from features.joke_service import JokeService  # noqa: E402
from features.reminder_service import ReminderService  # noqa: E402
from features.search_service import SearchService  # noqa: E402
from features.weather_service import WeatherService  # noqa: E402

FIXED_NOW = datetime(2026, 11, 11, 15, 5, 0)  # a Wednesday


def make_kb() -> KnowledgeBase:
    return KnowledgeBase.from_file(ROOT / "data" / "knowledge_base.json")


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL. Records what would have been sent."""

    sent = []
    raise_on_login = None
    raise_on_connect = None

    def __init__(self, host, port, timeout=None, context=None):
        if FakeSMTP.raise_on_connect:
            raise FakeSMTP.raise_on_connect
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if FakeSMTP.raise_on_login:
            raise FakeSMTP.raise_on_login
        self.user = user

    def send_message(self, message):
        FakeSMTP.sent.append(message)

    @classmethod
    def reset(cls):
        cls.sent = []
        cls.raise_on_login = None
        cls.raise_on_connect = None


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("bad json")
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


class OpenerRecorder:
    def __init__(self, result=True):
        self.urls, self.result = [], result

    def __call__(self, url):
        self.urls.append(url)
        return self.result


class FakeOnline:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.queries = answer, error, []

    def lookup(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.answer


def make_handler(env=None, weather_session=None, online=None, opener=None, reminders_cb=None, custom_json=None):
    """Build a CommandHandler wired to fakes. Returns (handler, parts dict)."""
    env = env or {}
    config = Config(env=env, load_env_file=False)
    opener = opener or OpenerRecorder()
    FakeSMTP.reset()
    parts = {
        "config": config,
        "opener": opener,
        "fired": [],
    }
    custom = (CustomCommands.from_file(custom_json, opener=opener) if custom_json
              else CustomCommands.from_file(ROOT / "data" / "custom_commands.json", opener=opener))
    weather = WeatherService(config.weather_api_key, session=weather_session)
    email = EmailService(config.email_address, config.email_app_password, smtp_factory=FakeSMTP)
    reminders = ReminderService(reminders_cb or parts["fired"].append)
    parts.update(weather=weather, email=email, reminders=reminders, custom=custom)
    handler = CommandHandler(config, make_kb(), custom, weather, email, SearchService(opener=opener), reminders,
                             jokes=JokeService(), online=online, clock=lambda: FIXED_NOW)
    return handler, parts


EMAIL_ENV = {"EMAIL_ADDRESS": "sender@gmail.com", "EMAIL_APP_PASSWORD": "abcd efgh ijkl mnop"}
