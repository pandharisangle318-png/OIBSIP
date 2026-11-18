"""Configuration loading for VYOM.

Secrets (email app password, weather API key) come from the environment / a
local ``.env`` file.  Non-secret preferences come from ``config.json``.
Nothing here is required just to launch the application: every missing value
falls back to a safe default.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping, Optional

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    "assistant": {
        "name": "VYOM",
        "user_name": "",
        "default_city": "",
        "online_lookup": True,
    },
    "speech": {
        "language": "en-IN",
        "listen_timeout": 6,
        "phrase_time_limit": 10,
        "calibration_seconds": 0.6,
        "max_consecutive_failures": 3,
    },
    "voice": {"rate": 175, "volume": 1.0, "voice_index": 0, "muted": False},
    "email": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "timeout": 20,
        "contacts": {},
    },
    "weather": {"units": "metric", "timeout": 10},
    "reminders": {"max_seconds": 86400},
}

_PLACEHOLDER_MARKERS = ("your_", "your-", "placeholder", "changeme", "xxxx")


def _clean_secret(value: Optional[str], strip_spaces: bool = False) -> Optional[str]:
    """Return a usable secret or None when empty / still a placeholder."""
    if value is None:
        return None
    text = str(value).strip().strip('"').strip("'").strip()
    if strip_spaces:
        text = "".join(text.split())
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return None
    return text


def _deep_merge(base: dict, override: Mapping) -> dict:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class Config:
    """Merged view of defaults + config.json + environment secrets."""

    def __init__(
        self,
        root: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        load_env_file: bool = True,
    ) -> None:
        self.root = Path(root) if root else PROJECT_ROOT
        self.env_file = self.root / ".env"
        self.config_file = self.root / "config.json"
        self.problems: list = []

        if load_env_file and env is None:
            try:
                from dotenv import load_dotenv

                load_dotenv(self.env_file, override=False)
            except ImportError:
                self.problems.append("python-dotenv is not installed; .env was not loaded.")
        self._env: Mapping[str, str] = env if env is not None else os.environ

        self.data: dict = copy.deepcopy(DEFAULTS)
        self._load_json()

    def _load_json(self) -> None:
        if not self.config_file.exists():
            self.problems.append("config.json not found; using defaults.")
            return
        try:
            loaded = json.loads(self.config_file.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("top level must be an object")
            _deep_merge(self.data, loaded)
        except (OSError, ValueError) as exc:
            self.problems.append(f"config.json could not be read ({exc}); using defaults.")
            log.warning("config.json invalid: %s", exc)

    # ---------------------------------------------------------------- access
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def email_address(self) -> Optional[str]:
        return _clean_secret(self._env.get("EMAIL_ADDRESS"))

    @property
    def email_app_password(self) -> Optional[str]:
        return _clean_secret(self._env.get("EMAIL_APP_PASSWORD"), strip_spaces=True)

    @property
    def weather_api_key(self) -> Optional[str]:
        return _clean_secret(self._env.get("OPENWEATHER_API_KEY"))

    @property
    def email_configured(self) -> bool:
        return bool(self.email_address and self.email_app_password)

    @property
    def weather_configured(self) -> bool:
        return bool(self.weather_api_key)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def log_dir(self) -> Path:
        return self.root / "logs"

    def secrets(self) -> list:
        """Secret values that must never appear in logs."""
        return [s for s in (self.email_app_password, self.weather_api_key) if s]

    def summary(self) -> dict:
        """Human-readable status. Never contains secret values."""
        return {
            "email_configured": self.email_configured,
            "weather_configured": self.weather_configured,
            "env_file_found": self.env_file.exists(),
            "config_file_found": self.config_file.exists(),
            "online_lookup": bool(self.get("assistant.online_lookup", True)),
            "language": self.get("speech.language"),
            "listen_timeout": self.get("speech.listen_timeout"),
            "phrase_time_limit": self.get("speech.phrase_time_limit"),
            "voice_rate": self.get("voice.rate"),
            "voice_volume": self.get("voice.volume"),
            "default_city": self.get("assistant.default_city") or "(not set)",
            "project_folder": str(self.root),
        }
