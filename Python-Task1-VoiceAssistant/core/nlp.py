"""Lightweight, offline natural language understanding for VYOM.

Pipeline: normalise -> intent recognition -> topic extraction -> knowledge
base retrieval (exact phrase match first, then guarded fuzzy match).  Only the
Python standard library is used.
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CONTRACTIONS = {
    "what's": "what is", "whats": "what is", "who's": "who is", "how's": "how is",
    "where's": "where is", "that's": "that is", "it's": "it is", "i'm": "i am",
    "you're": "you are", "can't": "cannot", "don't": "do not", "doesn't": "does not",
    "won't": "will not", "let's": "let us", "i'd": "i would", "i'll": "i will",
    "wanna": "want to", "gonna": "going to",
}

STOP_WORDS = frozenset(
    """a an the of in on at to for by with from and or is are was were be been am do does did
    can could would should will shall may might please tell me my i you your we us it its this
    that these those what who whom whose which when where why how explain explanation explained
    describe description define definition meaning mean means give want like learn know about
    something anything simple simply easy easier words word terms term short brief briefly basic
    basics detail details understand understanding quick overview introduction intro some more
    any also just let hey vyom hello hi there so then ok okay thanks thank teach""".split()
)

QUESTION_WORDS = frozenset(
    """what who why how explain tell define describe meaning mean know learn about difference
    introduction overview give teach""".split()
)


def normalize(text: Optional[str]) -> str:
    """Lower-case, expand contractions, drop punctuation, collapse spaces."""
    t = (text or "").lower().replace("\u2019", "'").replace("`", "'")
    for short, full in CONTRACTIONS.items():
        t = re.sub(r"\b" + re.escape(short) + r"\b", full, t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    t = re.sub(r"\be mail\b", "email", t)
    return t


def content_tokens(norm: str) -> list:
    """Tokens left after stop-word removal (the 'topic' words)."""
    return [tok for tok in norm.split() if tok not in STOP_WORDS]


def is_question_like(norm: str) -> bool:
    return any(tok in QUESTION_WORDS for tok in norm.split())


# --------------------------------------------------------------------- intents
@dataclass
class Intent:
    name: str
    params: dict = field(default_factory=dict)


_NUM_STOP = {"the", "current", "today", "todays", "tell", "me", "give", "get", "show", "check",
             "what", "is", "how", "whats", "weather", "like", "now", "of", "in", "for", "at", "a"}


def extract_city(norm: str) -> str:
    """Pull a city name out of a weather request ('weather in pune')."""
    m = re.search(r"\b(?:in|at|for|of)\s+([a-z][a-z ]*?)(?:\s+(?:today|now|right now|please|tomorrow|currently))*$", norm)
    if m:
        city = m.group(1).strip()
        city = re.sub(r"^(the )", "", city)
        if city and city not in ("today", "now"):
            return city.title()
    before = norm.split("weather")[0].split() if "weather" in norm else []
    words = [w for w in before if w not in _NUM_STOP]
    return " ".join(words).title() if words else ""


def extract_search_query(text: str) -> Optional[str]:
    """Return the search query, '' if search was requested without a topic, None if not a search.

    Works on the original text (not the normalised one) so characters such as '+' in 'C++' survive.
    """
    m = re.match(r"^\s*(?:please\s+)?(?:search|google|look up|lookup)\b[\s,:]*(.*)$", text or "", re.I | re.S)
    if not m:
        return None
    rest = m.group(1).strip()
    rest = re.sub(r"^(?:on google|on the web|on the internet|on web|google)\b\s*", "", rest, flags=re.I)
    rest = re.sub(r"^(?:for|about|up|on)\b\s*", "", rest, flags=re.I)
    rest = re.sub(r"\s+(?:on google|on the web|on the internet|in google|on web)\s*[.?!]*$", "", rest, flags=re.I)
    rest = rest.strip(" .?!,")
    if normalize(rest) in ("", "google", "the web", "the internet", "for", "about"):
        return ""
    return rest


def detect_intent(text: str) -> Intent:
    """Rule-based intent recognition on normalised text."""
    n = normalize(text)
    if not n:
        return Intent("empty")

    if re.match(r"^(exit|quit|close)( the)?( assistant| vyom| app| application| program)?$", n):
        return Intent("exit")
    if re.match(r"^(stop|pause) listening( vyom)?$|^stop( vyom| assistant)?$|^(go to )?(standby|stand by|sleep)$|^(goodbye|good bye|bye|see you)( vyom)?$", n):
        return Intent("stop_listening", {"farewell": "bye" in n or "see you" in n})
    if re.match(r"^(thanks|thank you)( vyom| a lot| so much)?$", n):
        return Intent("thanks")
    gm = re.match(r"^good (morning|afternoon|evening|night)( vyom| there)?$", n)
    if gm:
        return Intent("greeting", {"period": gm.group(1)})
    if re.match(r"^(hello|hi|hey|hiya|namaste|hello there|hi there|hey there)( vyom| there| assistant)?$", n):
        return Intent("greeting", {})
    if re.search(r"\bhow are you\b|\bhow do you do\b|\bhow is it going\b", n):
        return Intent("how_are_you")
    if re.search(r"\bwho are you\b|\byour name\b|\bintroduce yourself\b", n):
        return Intent("identity")
    if re.match(r"^(help|help me)( vyom)?$", n) or re.search(
        r"\bwhat can you do\b|\bwhat do you do\b|\byour (features|abilities|capabilities)\b|\bhow can you help\b|\bhow do i use\b", n
    ):
        return Intent("help")

    if re.search(r"\b(cancel|delete|clear|remove|stop)\b.*\b(reminders?|timers?|alarms?)\b", n):
        return Intent("reminder_cancel")
    if re.search(r"\b(list|show|what are|any)\b.*\b(reminders?|timers?)\b|\bmy reminders\b", n):
        return Intent("reminder_list")
    if re.search(r"\bremind me\b|\bset (a |an )?(reminder|timer|alarm)\b|\b(reminder|timer|alarm) (for|after|in)\b", n):
        return Intent("reminder_set")

    if re.search(r"\b(send|compose|write|draft)\b.*\bemail\b|^email\b|\bsend (a |an )?mail\b", n):
        return Intent("email")

    if re.search(r"\bweather\b|\bforecast\b|\btemperature (in|of|at)\b", n):
        return Intent("weather", {"city": extract_city(n)})

    query = extract_search_query(text)
    if query is not None:
        return Intent("search", {"query": query})

    if re.search(r"\bjoke\b|\bsomething funny\b|\bmake me laugh\b|\bfunny\b", n):
        return Intent("joke")

    has_date = bool(re.search(r"\bdate\b", n))
    has_time = bool(re.search(r"\btime\b", n))
    if has_date and has_time:
        return Intent("datetime")
    if has_date:
        return Intent("date")
    if re.search(r"\bwhat day\b|\bwhich day\b|\bday of (the )?week\b|\bthe day (today|is it)\b|\bday (is it|today)\b", n):
        return Intent("day")
    if has_time:
        return Intent("time")

    return Intent("unknown")


# ------------------------------------------------------------- knowledge base
@dataclass
class TopicMatch:
    topic: dict
    alias: str
    confidence: float
    method: str  # "exact" or "fuzzy"


class KnowledgeBase:
    FUZZY_THRESHOLD = 0.85
    FUZZY_MIN_LENGTH = 5

    def __init__(self, topics: list) -> None:
        self.topics = []
        self._aliases = []  # (alias, regex, topic)
        for topic in topics:
            if not isinstance(topic, dict) or not topic.get("name") or not topic.get("answer"):
                continue
            self.topics.append(topic)
            names = {normalize(topic["name"])}
            names.update(normalize(a) for a in topic.get("aliases", []))
            for alias in sorted(a for a in names if a):
                self._aliases.append((alias, re.compile(r"\b" + re.escape(alias) + r"\b"), topic))

    @classmethod
    def from_file(cls, path: Path) -> "KnowledgeBase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data.get("topics", []))

    def find_topic(self, text: str) -> Optional[TopicMatch]:
        norm = normalize(text)
        if not norm:
            return None
        best = None
        for alias, regex, topic in self._aliases:
            m = regex.search(norm)
            if m:
                key = (len(alias), -m.start())
                if best is None or key > best[0]:
                    best = (key, alias, topic)
        if best:
            return TopicMatch(best[2], best[1], 1.0, "exact")

        tokens = content_tokens(norm)
        fuzzy = None
        for alias, _regex, topic in self._aliases:
            if len(alias) < self.FUZZY_MIN_LENGTH:
                continue
            size = len(alias.split())
            for i in range(len(tokens) - size + 1):
                gram = " ".join(tokens[i:i + size])
                if len(gram) < self.FUZZY_MIN_LENGTH:
                    continue
                ratio = difflib.SequenceMatcher(None, gram, alias).ratio()
                if ratio >= self.FUZZY_THRESHOLD and (fuzzy is None or ratio > fuzzy.confidence):
                    fuzzy = TopicMatch(topic, alias, ratio, "fuzzy")
        return fuzzy

    def answer(self, text: str) -> Optional[str]:
        match = self.find_topic(text)
        return match.topic["answer"] if match else None

    @staticmethod
    def topic_phrase(text: str) -> str:
        return " ".join(content_tokens(normalize(text)))
