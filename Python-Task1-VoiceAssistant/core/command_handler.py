"""Routes recognised text to features and runs multi-step dialogues (e.g. email)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from core import messages
from core.nlp import KnowledgeBase, content_tokens, detect_intent, is_question_like, normalize
from features.custom_commands import CustomCommands
from features.email_service import EmailError, parse_spoken_address, speakable_address
from features.joke_service import JokeService
from features.online_lookup import LookupError_
from features.reminder_service import format_duration, parse_reminder_request
from features.weather_service import WeatherError

log = logging.getLogger(__name__)

YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "send", "go ahead", "do it", "correct", "affirmative"}
NO_WORDS = {"no", "nope", "nah", "cancel", "stop", "abort", "negative", "never mind", "nevermind"}
CANCEL_PHRASES = {"cancel", "stop", "never mind", "nevermind", "abort", "forget it"}


@dataclass
class Reply:
    text: str
    speech: Optional[str] = None  # alternative text for the voice (e.g. spelled-out email address)
    action: Optional[str] = None  # None | "exit" | "stop_listening"


def is_yes(norm: str) -> bool:
    words = norm.split()
    if not words or is_no(norm):
        return False
    return norm in YES_WORDS or words[0] in {"yes", "yeah", "yep", "yup", "sure", "confirm", "ok", "okay"} or norm.startswith("send")


def is_no(norm: str) -> bool:
    words = norm.split()
    if not words:
        return False
    return (norm in NO_WORDS or words[0] in {"no", "nope", "nah", "cancel", "abort", "never"}
            or "do not" in norm or "dont" in words or "not" in words)


class CommandHandler:
    MAX_DIALOGUE_RETRIES = 3

    def __init__(self, config, kb: KnowledgeBase, custom: CustomCommands, weather, email, search, reminders,
                 jokes: Optional[JokeService] = None, online=None, clock: Callable[[], datetime] = datetime.now) -> None:
        self.config = config
        self.kb = kb
        self.custom = custom
        self.weather = weather
        self.email = email
        self.search = search
        self.reminders = reminders
        self.jokes = jokes or JokeService()
        self.online = online
        self.clock = clock
        self.state: Optional[str] = None
        self.draft: dict = {}
        self._retries = 0

    @property
    def expects_reply(self) -> bool:
        return self.state is not None

    def _reset(self) -> None:
        self.state = None
        self.draft = {}
        self._retries = 0

    # ------------------------------------------------------------------ entry
    def handle(self, text: str) -> list:
        text = (text or "").strip()
        if not text:
            return []
        norm = normalize(text)
        intent = detect_intent(text)

        if self.state:
            if intent.name in ("exit", "stop_listening"):
                self._reset()
            else:
                return self._continue_dialogue(text, norm)

        custom = self.custom.match(text)
        if custom:
            return [Reply(self.custom.run(custom))]

        method = getattr(self, "_intent_" + intent.name, None)
        if method:
            return method(intent, text)
        return self._knowledge_or_unknown(text, norm)

    # ---------------------------------------------------------------- intents
    def _intent_empty(self, intent, text):
        return []

    def _intent_greeting(self, intent, text):
        name = self.config.get("assistant.user_name") or ""
        period = intent.params.get("period")
        opener = f"Good {period}" if period else "Hello"
        if name:
            opener += f", {name}"
        return [Reply(f"{opener}! I am VYOM, your personal voice assistant. How can I help you?")]

    def _intent_how_are_you(self, intent, text):
        return [Reply("I am doing great, thank you for asking! How can I help you?")]

    def _intent_identity(self, intent, text):
        return [Reply("I am VYOM, an intelligent personal voice assistant written in Python. I can tell the time, search the web, check the weather, send emails, set reminders and answer questions.")]

    def _intent_help(self, intent, text):
        return [Reply(messages.HELP)]

    def _intent_thanks(self, intent, text):
        return [Reply("You're welcome!")]

    def _intent_stop_listening(self, intent, text):
        word = "Goodbye! " if intent.params.get("farewell") else ""
        return [Reply(word + "I have stopped listening. Press Start Assistant when you need me.", action="stop_listening")]

    def _intent_exit(self, intent, text):
        return [Reply("Goodbye! Closing VYOM.", action="exit")]

    def _intent_time(self, intent, text):
        now = self.clock()
        return [Reply(f"The time is {now.strftime('%I:%M %p').lstrip('0')}.")]

    def _intent_date(self, intent, text):
        now = self.clock()
        return [Reply(f"Today's date is {now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}.")]

    def _intent_day(self, intent, text):
        return [Reply(f"Today is {self.clock().strftime('%A')}.")]

    def _intent_datetime(self, intent, text):
        now = self.clock()
        return [Reply(f"It is {now.strftime('%I:%M %p').lstrip('0')} on {now.strftime('%A')}, {now.day} {now.strftime('%B %Y')}.")]

    def _intent_joke(self, intent, text):
        return [Reply(self.jokes.tell())]

    def _intent_search(self, intent, text):
        query = intent.params.get("query", "")
        if not query:
            self.state, self._retries = "search_query", 0
            return [Reply("What would you like me to search for?")]
        return [Reply(self.search.search(query))]

    def _intent_weather(self, intent, text):
        city = intent.params.get("city") or self.config.get("assistant.default_city") or ""
        if not self.weather.configured:
            return [Reply(self._weather_error_text("no_key"))]
        if not city:
            self.state, self._retries = "weather_city", 0
            return [Reply("Which city would you like the weather for?")]
        return [Reply(self._weather_text(city))]

    def _weather_error_text(self, kind):
        try:
            self.weather.get_weather("x")
        except WeatherError as exc:
            return exc.user_message
        return "Weather is not available right now."

    def _weather_text(self, city: str) -> str:
        try:
            return self.weather.get_weather(city).to_text()
        except WeatherError as exc:
            return exc.user_message

    def _intent_email(self, intent, text):
        problem = self.email.credential_problem()
        if problem:
            return [Reply(problem)]
        self.state, self.draft, self._retries = "email_to", {}, 0
        return [Reply("Who should I send the email to? You can say or type the address, for example name at gmail dot com.")]

    def _intent_reminder_set(self, intent, text):
        seconds, message = parse_reminder_request(text)
        if seconds is None:
            return [Reply("I could not understand when to remind you. Try: remind me in 5 minutes to drink water.")]
        try:
            reminder = self.reminders.add(seconds, message)
        except ValueError as exc:
            return [Reply(str(exc))]
        what = f" to {message}" if message else ""
        return [Reply(f"Okay, I will remind you{what} in {format_duration(seconds)}.")]

    def _intent_reminder_cancel(self, intent, text):
        count = self.reminders.cancel_all()
        return [Reply(f"Cancelled {count} reminder{'s' if count != 1 else ''}." if count else "You have no active reminders.")]

    def _intent_reminder_list(self, intent, text):
        active = self.reminders.active()
        if not active:
            return [Reply("You have no active reminders.")]
        import time as _time

        lines = [f"{r.message} in {format_duration(max(1, r.due - _time.time()))}" for r in active]
        return [Reply("You have " + str(len(active)) + " active reminder" + ("s" if len(active) != 1 else "") + ": " + "; ".join(lines) + ".")]

    # -------------------------------------------------------------- knowledge
    def _knowledge_or_unknown(self, text: str, norm: str) -> list:
        tokens = content_tokens(norm)
        match = self.kb.find_topic(text)
        if match and (is_question_like(norm) or len(tokens) <= 3):
            return [Reply(match.topic["answer"])]
        if is_question_like(norm) and tokens:
            online_text = self._try_online(self.kb.topic_phrase(text))
            if online_text:
                return [Reply("From Wikipedia, online: " + online_text)]
            if self.online is None or not self.config.get("assistant.online_lookup", True):
                return [Reply("I do not have that in my offline knowledge base. You can say search for, followed by your topic, to look it up on Google.")]
            return [Reply("I could not find an answer to that in my knowledge base or online. You can say search for, followed by your topic, to look it up on Google.")]
        return [Reply(messages.UNKNOWN_COMMAND)]

    def _try_online(self, topic: str) -> Optional[str]:
        if self.online is None or not self.config.get("assistant.online_lookup", True) or not topic:
            return None
        try:
            return self.online.lookup(topic)
        except LookupError_ as exc:
            log.info("Online lookup unavailable: %s", exc)
            return None

    # ---------------------------------------------------------------- dialogue
    def _retry(self, message: str) -> list:
        self._retries += 1
        if self._retries >= self.MAX_DIALOGUE_RETRIES:
            self._reset()
            return [Reply("I could not understand that, so I have cancelled this request.")]
        return [Reply(message)]

    def _continue_dialogue(self, text: str, norm: str) -> list:
        if norm in CANCEL_PHRASES or (norm.startswith("cancel") and len(norm.split()) <= 3):
            self._reset()
            return [Reply("Okay, cancelled.")]
        state = self.state
        if state == "search_query":
            self._reset()
            return [Reply(self.search.search(text))]
        if state == "weather_city":
            self._reset()
            return [Reply(self._weather_text(re.sub(r"^(?:in|at|for)\s+", "", text.strip(), flags=re.I)))]
        if state == "email_to":
            address = parse_spoken_address(text, self.config.get("email.contacts", {}))
            if not address:
                return self._retry("That does not look like a valid email address. Please say it again, for example name at gmail dot com, or say cancel.")
            self.draft["to"] = address
            self.state, self._retries = "email_subject", 0
            return [Reply("What is the subject?")]
        if state == "email_subject":
            self.draft["subject"] = text.strip()
            self.state = "email_body"
            return [Reply("What should the message say?")]
        if state == "email_body":
            self.draft["body"] = text.strip()
            self.state, self._retries = "email_confirm", 0
            to, subject, body = self.draft["to"], self.draft["subject"], self.draft["body"]
            shown = f"Here is your email.\nTo: {to}\nSubject: {subject}\nMessage: {body}\nWould you like me to send this email?"
            spoken = (f"Here is your email. To: {speakable_address(to)}. Subject: {subject}. "
                      f"Message: {body}. Would you like me to send this email?")
            return [Reply(shown, speech=spoken)]
        if state == "email_confirm":
            if is_no(norm):
                self._reset()
                return [Reply("Okay, I have cancelled the email. Nothing was sent.")]
            if is_yes(norm):
                draft = dict(self.draft)
                self._reset()
                try:
                    self.email.send(draft["to"], draft["subject"], draft["body"])
                except EmailError as exc:
                    return [Reply(exc.user_message)]
                return [Reply(f"Your email to {draft['to']} has been sent.", speech=f"Your email to {speakable_address(draft['to'])} has been sent.")]
            return self._retry("Please say yes to send the email, or no to cancel.")
        self._reset()
        return [Reply(messages.UNKNOWN_COMMAND)]
