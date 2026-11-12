"""Configurable custom commands loaded from data/custom_commands.json.

Only two safe command types exist: ``reply`` (say a fixed answer) and
``open_url`` (open an http/https address in the browser).  Nothing from the
file or from speech is ever run as a program or shell command.
"""
from __future__ import annotations

import difflib
import json
import logging
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.nlp import normalize

log = logging.getLogger(__name__)
ALLOWED_TYPES = ("reply", "open_url")
FUZZY_THRESHOLD = 0.9


@dataclass
class CustomCommand:
    phrases: list
    type: str
    response: str
    url: str = ""


def is_safe_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and " " not in url


class CustomCommands:
    def __init__(self, commands: list, problems: Optional[list] = None, opener: Callable[[str], bool] = webbrowser.open) -> None:
        self.commands = commands
        self.problems = problems or []
        self._open = opener
        self._index = {}
        for cmd in commands:
            for phrase in cmd.phrases:
                self._index.setdefault(phrase, cmd)

    @classmethod
    def from_file(cls, path: Path, opener: Callable[[str], bool] = webbrowser.open) -> "CustomCommands":
        problems: list = []
        commands: list = []
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            entries = data.get("commands", [])
            if not isinstance(entries, list):
                raise ValueError('"commands" must be a list')
        except (OSError, ValueError) as exc:
            problems.append(f"custom_commands.json could not be loaded: {exc}")
            return cls([], problems, opener)
        for i, entry in enumerate(entries, 1):
            cmd = cls._validate(entry, i, problems)
            if cmd:
                commands.append(cmd)
        for problem in problems:
            log.warning(problem)
        return cls(commands, problems, opener)

    @staticmethod
    def _validate(entry, index: int, problems: list) -> Optional[CustomCommand]:
        if not isinstance(entry, dict):
            problems.append(f"Command #{index}: must be an object.")
            return None
        phrases = [normalize(p) for p in entry.get("phrases", []) if isinstance(p, str)]
        phrases = [p for p in phrases if p]
        ctype = entry.get("type")
        if not phrases:
            problems.append(f"Command #{index}: needs at least one phrase.")
            return None
        if ctype not in ALLOWED_TYPES:
            problems.append(f"Command #{index}: type must be one of {ALLOWED_TYPES}.")
            return None
        response = str(entry.get("response", "")).strip()
        url = str(entry.get("url", "")).strip()
        if ctype == "open_url" and not is_safe_url(url):
            problems.append(f"Command #{index}: url must be a valid http(s) address.")
            return None
        if ctype == "reply" and not response:
            problems.append(f"Command #{index}: a reply command needs a response.")
            return None
        return CustomCommand(phrases, ctype, response or "Opening that for you.", url)

    def match(self, text: str) -> Optional[CustomCommand]:
        norm = normalize(text)
        for prefix in ("please ", "vyom ", "can you ", "could you "):
            while norm.startswith(prefix):
                norm = norm[len(prefix):]
        if not norm:
            return None
        if norm in self._index:
            return self._index[norm]
        best, best_ratio = None, 0.0
        for phrase, cmd in self._index.items():
            ratio = difflib.SequenceMatcher(None, norm, phrase).ratio()
            if ratio > best_ratio:
                best, best_ratio = cmd, ratio
        return best if best_ratio >= FUZZY_THRESHOLD else None

    def run(self, cmd: CustomCommand) -> str:
        if cmd.type == "reply":
            return cmd.response
        try:
            opened = self._open(cmd.url)
        except Exception as exc:
            log.warning("Browser open failed: %s", exc)
            opened = False
        return cmd.response if opened else "I could not open your web browser. Please check your default browser settings."
