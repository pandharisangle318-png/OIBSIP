"""Google web search (opens the default browser)."""
from __future__ import annotations

import logging
import re
import urllib.parse
import webbrowser
from typing import Callable

log = logging.getLogger(__name__)
MAX_QUERY_LENGTH = 200


class SearchService:
    def __init__(self, opener: Callable[[str], bool] = webbrowser.open) -> None:
        self._open = opener

    @staticmethod
    def clean_query(query: str) -> str:
        query = re.sub(r"[\x00-\x1f\x7f]", " ", query or "")
        return " ".join(query.split())[:MAX_QUERY_LENGTH]

    @staticmethod
    def build_url(query: str) -> str:
        return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)

    def search(self, query: str) -> str:
        """Open a Google search and return a message for the user."""
        query = self.clean_query(query)
        if not query:
            return "What would you like me to search for?"
        try:
            opened = self._open(self.build_url(query))
        except Exception as exc:  # webbrowser can raise on odd systems
            log.warning("Browser open failed: %s", exc)
            opened = False
        if not opened:
            return "I could not open your web browser. Please check your default browser settings."
        return f"Searching Google for {query}."
