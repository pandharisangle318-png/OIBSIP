"""Business rules shared by the web app and the TCP server.

Keeping validation and message-sending here means a message behaves the same
no matter which client it came from.
"""

import re

from werkzeug.security import check_password_hash, generate_password_hash

from . import database as db
from .emoji import convert_shortcodes

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
ROOM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-]{1,28}[A-Za-z0-9]$")
MAX_MESSAGE_LEN = 1000
MIN_PASSWORD_LEN = 8


class ChatError(Exception):
    """A problem the user can fix (bad input, wrong password, ...)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ---- accounts --------------------------------------------------------------

def register_user(path, username, password):
    username = (username or "").strip()
    password = password or ""
    if not USERNAME_RE.match(username):
        raise ChatError("Username must be 3-20 characters: letters, numbers or underscore.")
    if len(password) < MIN_PASSWORD_LEN:
        raise ChatError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
    if len(password) > 128:
        raise ChatError("Password is too long (max 128 characters).")
    user_id = db.create_user(path, username, generate_password_hash(password))
    if user_id is None:
        raise ChatError("That username is already taken.", 409)
    return db.get_user(path, user_id)


# A throwaway hash so failed logins for unknown users take about as long as real ones.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def authenticate(path, username, password):
    user = db.get_user_by_name(path, (username or "").strip())
    if user is None:
        check_password_hash(_DUMMY_HASH, password or "")
        raise ChatError("Invalid username or password.", 401)
    if not check_password_hash(user["password_hash"], password or ""):
        raise ChatError("Invalid username or password.", 401)
    return user


# ---- rooms & messages ------------------------------------------------------

def make_room(path, name, description, user_id):
    name = " ".join((name or "").split())
    description = (description or "").strip()
    if not ROOM_RE.match(name):
        raise ChatError("Room name must be 3-30 characters (letters, numbers, spaces, - or _).")
    if len(description) > 120:
        raise ChatError("Description can be at most 120 characters.")
    room_id = db.create_room(path, name, description, user_id)
    if room_id is None:
        raise ChatError("A room with that name already exists.", 409)
    return db.get_room(path, room_id)


def clean_message(text):
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        raise ChatError("Message can't be empty.")
    if len(text) > MAX_MESSAGE_LEN:
        raise ChatError(f"Message is too long (max {MAX_MESSAGE_LEN} characters).")
    return convert_shortcodes(text)


def send_message(path, hub, room_id, user_id, text):
    """Validate, convert emoji, store in SQLite, then broadcast to everyone."""
    room = db.get_room(path, room_id)
    if room is None:
        raise ChatError("Room not found.", 404)
    body = clean_message(text)
    message = db.add_message(path, room_id, user_id, body)
    hub.publish_message(message)
    return message
