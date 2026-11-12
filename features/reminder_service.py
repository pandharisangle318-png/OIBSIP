"""Background timed reminders (threading.Timer based, never blocks the GUI)."""
from __future__ import annotations

import itertools
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from core.nlp import normalize

log = logging.getLogger(__name__)

_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60}
_UNITS = {"second": 1, "seconds": 1, "sec": 1, "secs": 1, "minute": 60, "minutes": 60, "min": 60, "mins": 60,
          "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600}

_NUM = (r"\d+(?:\.\d+)?|(?:twenty|thirty|forty|fifty|sixty)(?:\s+(?:one|two|three|four|five|six|seven|eight|nine))?|"
        + "|".join(sorted(_ONES, key=len, reverse=True)) + r"|an|a|half")
_DURATION_RE = re.compile(
    r"(?:\b(?:after|in|for|within)\s+)?\b(?P<num>" + _NUM + r")\s*(?P<unit>seconds?|secs?|minutes?|mins?|hours?|hrs?)\b"
)
_HALF_HOUR_RE = re.compile(r"(?:\b(?:after|in|for|within)\s+)?\bhalf (?:an )?hour\b")


def _word_to_number(word: str) -> float:
    word = word.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", word):
        return float(word)
    if word in ("a", "an"):
        return 1.0
    if word == "half":
        return 0.5
    parts = word.split()
    total = 0
    for part in parts:
        total += _TENS.get(part, _ONES.get(part, 0))
    return float(total)


def parse_duration(text: str) -> Tuple[Optional[float], str]:
    """Return (seconds or None, text with the duration phrase removed). ``text`` should be normalised."""
    total = 0.0
    found = False
    remainder = text

    def half_hour(_m):
        nonlocal total, found
        total += 1800
        found = True
        return " "

    remainder = _HALF_HOUR_RE.sub(half_hour, remainder)

    def replace(match):
        nonlocal total, found
        total += _word_to_number(match.group("num")) * _UNITS[match.group("unit")]
        found = True
        return " "

    remainder = _DURATION_RE.sub(replace, remainder)
    return (total if found else None), " ".join(remainder.split())


def parse_reminder_request(text: str) -> Tuple[Optional[float], str]:
    """'remind me after 5 minutes to drink water' -> (300.0, 'drink water')."""
    norm = normalize(text)
    seconds, rest = parse_duration(norm)
    rest = re.sub(r"^(?:please\s+)?(?:remind me|set (?:a |an )?(?:reminder|timer|alarm)|reminder|timer|alarm)\b", "", rest).strip()
    rest = re.sub(r"^(?:to|that|about|for|of)\s+", "", rest).strip()
    rest = re.sub(r"\s+(?:please)$", "", rest).strip()
    return seconds, rest


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    parts = []
    for name, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        value, seconds = divmod(seconds, size)
        if value:
            parts.append(f"{value} {name}{'s' if value != 1 else ''}")
    return " and ".join(parts) if parts else "0 seconds"


def play_alert_sound() -> None:
    """Audible alert. Uses winsound on Windows, the terminal bell elsewhere."""
    try:
        import winsound

        for freq in (880, 1175, 880, 1175):
            winsound.Beep(freq, 220)
    except Exception:
        print("\a", end="", flush=True)


@dataclass
class Reminder:
    id: int
    message: str
    seconds: float
    due: float
    timer: Optional[threading.Timer] = field(default=None, repr=False)


class ReminderService:
    def __init__(self, on_trigger: Callable[[Reminder], None], max_seconds: float = 86400) -> None:
        self._on_trigger = on_trigger
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._items: dict = {}
        self._ids = itertools.count(1)
        self._closed = False

    def add(self, seconds: float, message: str) -> Reminder:
        if seconds is None or seconds <= 0:
            raise ValueError("The reminder time must be greater than zero.")
        if seconds > self.max_seconds:
            raise ValueError(f"I can only set reminders up to {format_duration(self.max_seconds)} ahead.")
        message = (message or "").strip() or "your reminder"
        with self._lock:
            if self._closed:
                raise RuntimeError("Reminder service is shut down.")
            reminder = Reminder(next(self._ids), message, seconds, time.time() + seconds)
            timer = threading.Timer(seconds, self._fire, args=(reminder.id,))
            timer.daemon = True
            reminder.timer = timer
            self._items[reminder.id] = reminder
            timer.start()
        return reminder

    def _fire(self, reminder_id: int) -> None:
        with self._lock:
            reminder = self._items.pop(reminder_id, None)
        if reminder is None:
            return
        try:
            self._on_trigger(reminder)
        except Exception:
            log.exception("Reminder callback failed")

    def cancel(self, reminder_id: int) -> bool:
        with self._lock:
            reminder = self._items.pop(reminder_id, None)
        if reminder and reminder.timer:
            reminder.timer.cancel()
        return reminder is not None

    def cancel_all(self) -> int:
        with self._lock:
            items = list(self._items.values())
            self._items.clear()
        for reminder in items:
            if reminder.timer:
                reminder.timer.cancel()
        return len(items)

    def active(self) -> list:
        with self._lock:
            return sorted(self._items.values(), key=lambda r: r.due)

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        self.cancel_all()
