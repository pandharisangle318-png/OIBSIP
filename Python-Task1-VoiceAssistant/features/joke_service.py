"""Offline joke collection."""
from __future__ import annotations

import random
from typing import Optional

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why did the Python programmer wear glasses? Because he could not C.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are only 10 kinds of people in the world: those who understand binary and those who do not.",
    "Why was the computer cold? It left its Windows open.",
    "How many programmers does it take to change a light bulb? None, that is a hardware problem.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
    "Why did the developer go broke? Because he used up all his cache.",
    "What is a computer's favourite snack? Microchips.",
    "Why do Java developers wear glasses? Because they do not C sharp.",
    "My code never has bugs. It just develops random features.",
    "Why did the smartphone need glasses? It lost all its contacts.",
]


class JokeService:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng or random.Random()
        self._last: Optional[str] = None

    def tell(self) -> str:
        choices = [j for j in JOKES if j != self._last] or JOKES
        joke = self._rng.choice(choices)
        self._last = joke
        return joke
