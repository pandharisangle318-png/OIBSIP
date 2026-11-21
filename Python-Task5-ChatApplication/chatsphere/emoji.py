"""Emoji shortcode conversion, e.g. ':smile:' -> a smiling face."""

import re

SHORTCODES = {
    "smile": "\U0001F60A", "grin": "\U0001F601", "laughing": "\U0001F606",
    "joy": "\U0001F602", "rofl": "\U0001F923", "wink": "\U0001F609",
    "blush": "\U0001F60A", "heart_eyes": "\U0001F60D", "kissing_heart": "\U0001F618",
    "sunglasses": "\U0001F60E", "thinking": "\U0001F914", "neutral": "\U0001F610",
    "unamused": "\U0001F612", "sweat_smile": "\U0001F605", "cry": "\U0001F622",
    "sob": "\U0001F62D", "angry": "\U0001F620", "rage": "\U0001F621",
    "scream": "\U0001F631", "sleepy": "\U0001F62A", "yum": "\U0001F60B",
    "relieved": "\U0001F60C", "pensive": "\U0001F614", "confused": "\U0001F615",
    "open_mouth": "\U0001F62E", "hushed": "\U0001F62F", "zany": "\U0001F92A",
    "nerd": "\U0001F913", "partying": "\U0001F973", "star_struck": "\U0001F929",
    "heart": "❤️", "broken_heart": "\U0001F494", "blue_heart": "\U0001F499",
    "green_heart": "\U0001F49A", "purple_heart": "\U0001F49C", "sparkling_heart": "\U0001F496",
    "thumbsup": "\U0001F44D", "+1": "\U0001F44D", "thumbsdown": "\U0001F44E", "-1": "\U0001F44E",
    "clap": "\U0001F44F", "wave": "\U0001F44B", "pray": "\U0001F64F", "ok_hand": "\U0001F44C",
    "muscle": "\U0001F4AA", "raised_hands": "\U0001F64C", "handshake": "\U0001F91D",
    "victory": "✌️", "fist": "✊", "point_right": "\U0001F449",
    "fire": "\U0001F525", "star": "⭐", "sparkles": "✨", "boom": "\U0001F4A5",
    "100": "\U0001F4AF", "tada": "\U0001F389", "party": "\U0001F389", "balloon": "\U0001F388",
    "gift": "\U0001F381", "trophy": "\U0001F3C6", "medal": "\U0001F3C5", "crown": "\U0001F451",
    "rocket": "\U0001F680", "bulb": "\U0001F4A1", "zap": "⚡", "bell": "\U0001F514",
    "check": "✅", "x": "❌", "warning": "⚠️", "question": "❓",
    "eyes": "\U0001F440", "brain": "\U0001F9E0", "skull": "\U0001F480", "ghost": "\U0001F47B",
    "robot": "\U0001F916", "poop": "\U0001F4A9", "alien": "\U0001F47D",
    "coffee": "☕", "tea": "\U0001F375", "pizza": "\U0001F355", "burger": "\U0001F354",
    "cake": "\U0001F370", "beer": "\U0001F37A", "apple": "\U0001F34E", "mango": "\U0001F96D",
    "sun": "☀️", "moon": "\U0001F319", "cloud": "☁️", "rain": "\U0001F327️",
    "rainbow": "\U0001F308", "snowflake": "❄️", "earth": "\U0001F30D",
    "dog": "\U0001F436", "cat": "\U0001F431", "panda": "\U0001F43C", "tiger": "\U0001F42F",
    "computer": "\U0001F4BB", "phone": "\U0001F4F1", "book": "\U0001F4D6", "pencil": "✏️",
    "memo": "\U0001F4DD", "lock": "\U0001F512", "key": "\U0001F511", "mail": "\U0001F4E7",
    "snake": "\U0001F40D", "bug": "\U0001F41B", "music": "\U0001F3B5", "game": "\U0001F3AE",
    "cricket": "\U0001F3CF", "soccer": "⚽", "india": "\U0001F1EE\U0001F1F3",
}

_PATTERN = re.compile(r":([a-z0-9_+\-]+):", re.IGNORECASE)


def convert_shortcodes(text):
    """Replace known :shortcodes: with emoji. Unknown codes are left untouched."""

    def swap(match):
        return SHORTCODES.get(match.group(1).lower(), match.group(0))

    return _PATTERN.sub(swap, text)


def picker_list():
    """A short curated list (shortcode, emoji) for the web emoji picker."""
    names = [
        "smile", "grin", "joy", "wink", "heart_eyes", "sunglasses", "thinking",
        "sweat_smile", "cry", "angry", "scream", "partying", "thumbsup", "clap",
        "wave", "pray", "muscle", "fire", "sparkles", "tada", "rocket", "bulb",
        "check", "eyes", "heart", "coffee", "pizza", "100",
    ]
    return [(n, SHORTCODES[n]) for n in names]
