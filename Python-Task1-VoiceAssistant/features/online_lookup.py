"""Optional online general-knowledge lookup (Wikipedia). Never required."""
from __future__ import annotations

import difflib
import logging
import re
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

log = logging.getLogger(__name__)
SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/title"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
HEADERS = {"User-Agent": "VYOM-VoiceAssistant/1.0 (internship project)"}


class LookupError_(Exception):
    """Raised when the online source cannot be used (network, timeout, bad reply)."""


class OnlineLookup:
    def __init__(self, timeout: float = 8, session=None) -> None:
        self.timeout = timeout
        self._session = session

    def lookup(self, query: str) -> Optional[str]:
        """Return a short summary, None if nothing relevant was found. Raises LookupError_ on failure."""
        query = " ".join((query or "").split())
        if not query:
            return None
        http = self._session or requests
        if http is None:
            raise LookupError_("requests not installed")
        try:
            found = http.get(SEARCH_URL, params={"q": query, "limit": 1}, headers=HEADERS, timeout=self.timeout)
            if found.status_code != 200:
                raise LookupError_(f"search status {found.status_code}")
            pages = found.json().get("pages") or []
            if not pages:
                return None
            title = str(pages[0].get("title", ""))
            if not self._relevant(query, title):
                return None
            summary = http.get(SUMMARY_URL + title.replace(" ", "_"), headers=HEADERS, timeout=self.timeout)
            if summary.status_code == 404:
                return None
            if summary.status_code != 200:
                raise LookupError_(f"summary status {summary.status_code}")
            extract = str(summary.json().get("extract") or "").strip()
        except LookupError_:
            raise
        except Exception as exc:  # timeouts, connection errors, bad JSON
            raise LookupError_(type(exc).__name__) from exc
        if not extract:
            return None
        sentences = re.split(r"(?<=[.!?])\s+", extract)
        return " ".join(sentences[:2])

    @staticmethod
    def _relevant(query: str, title: str) -> bool:
        q, t = query.lower(), title.lower()
        if not t:
            return False
        if q in t or t in q:
            return True
        return difflib.SequenceMatcher(None, q, t).ratio() >= 0.6
