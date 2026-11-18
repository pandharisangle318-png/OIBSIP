"""Configuration loading (.env via python-dotenv, with safe defaults)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
API_BASE_URL = "https://api.openweathermap.org/data/2.5"

PLACEHOLDER_KEYS = frozenset(
    {"", "your_api_key_here", "your_openweathermap_api_key", "your-api-key", "changeme", "xxxxxxxx"}
)


def _to_float(value: Optional[str], default: float, lo: float, hi: float) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return min(max(number, lo), hi)


def _to_int(value: Optional[str], default: int, lo: int, hi: int) -> int:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    return min(max(number, lo), hi)


def _to_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Config:
    api_key: str = ""
    default_city: str = "Mumbai"
    default_units: str = "C"            # "C" or "F"
    timeout: float = 10.0               # seconds per HTTP request
    auto_refresh_minutes: int = 10      # 0 disables auto refresh
    effects_enabled: bool = True
    base_url: str = API_BASE_URL

    @property
    def has_api_key(self) -> bool:
        key = self.api_key.strip()
        return key.lower() not in PLACEHOLDER_KEYS and " " not in key and len(key) >= 16

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        units = str(env.get("WEATHERDESK_UNITS", "C")).strip().upper()
        city = str(env.get("WEATHERDESK_DEFAULT_CITY", "")).strip() or cls.default_city
        return cls(
            api_key=str(env.get("OPENWEATHER_API_KEY", "")).strip().strip("\"'"),
            default_city=city,
            default_units=units if units in {"C", "F"} else "C",
            timeout=_to_float(env.get("WEATHERDESK_TIMEOUT"), 10.0, 3.0, 60.0),
            auto_refresh_minutes=_to_int(env.get("WEATHERDESK_AUTO_REFRESH_MIN"), 10, 0, 120),
            effects_enabled=_to_bool(env.get("WEATHERDESK_EFFECTS"), True),
        )


def load_config(env_path: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None) -> Config:
    """Read the .env file (if present) and merge it with real environment variables.

    Real environment variables take priority over the file. Nothing is written
    back to ``os.environ``, so repeated calls always see fresh file contents.
    """
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    values: dict[str, str] = {}
    if path.is_file():
        values.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    values.update(os.environ if environ is None else environ)
    return Config.from_env(values)
