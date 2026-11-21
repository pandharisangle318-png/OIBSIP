"""SQLite helpers: schema, connections, and small query functions."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    created_by  INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
"""

DEFAULT_ROOMS = [
    ("Lobby", "Say hello - everyone starts here."),
    ("Study Hall", "Quiet corner for exam prep and doubts."),
    ("Tech Talk", "Code, tools, projects and bugs."),
    ("Random", "Anything that doesn't fit elsewhere."),
]


def utc_now():
    """Current time as an ISO-8601 UTC string (what we store and send)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(path):
    """Open a connection, commit on success, always close."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path):
    """Create tables and seed the default rooms (safe to call repeatedly)."""
    with session(path) as db:
        db.executescript(SCHEMA)
        for name, desc in DEFAULT_ROOMS:
            db.execute(
                "INSERT OR IGNORE INTO rooms (name, description, created_at) VALUES (?, ?, ?)",
                (name, desc, utc_now()),
            )


# ---- users -----------------------------------------------------------------

def create_user(path, username, password_hash):
    """Insert a user. Returns the new id, or None if the name is taken."""
    try:
        with session(path) as db:
            cur = db.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, utc_now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_name(path, username):
    with session(path) as db:
        return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(path, user_id):
    with session(path) as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---- rooms -----------------------------------------------------------------

def list_rooms(path):
    with session(path) as db:
        rows = db.execute(
            """SELECT r.id, r.name, r.description,
                      (SELECT COUNT(*) FROM messages m WHERE m.room_id = r.id) AS message_count
               FROM rooms r ORDER BY r.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_room(path, room_id):
    with session(path) as db:
        row = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return dict(row) if row else None


def get_room_by_name(path, name):
    with session(path) as db:
        row = db.execute("SELECT * FROM rooms WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def create_room(path, name, description, user_id):
    """Insert a room. Returns the new id, or None if the name is taken."""
    try:
        with session(path) as db:
            cur = db.execute(
                "INSERT INTO rooms (name, description, created_by, created_at) VALUES (?, ?, ?, ?)",
                (name, description, user_id, utc_now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


# ---- messages --------------------------------------------------------------

_MSG_SELECT = """SELECT m.id, m.room_id, u.username, m.body, m.created_at
                 FROM messages m JOIN users u ON u.id = m.user_id"""


def add_message(path, room_id, user_id, body):
    with session(path) as db:
        cur = db.execute(
            "INSERT INTO messages (room_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (room_id, user_id, body, utc_now()),
        )
        row = db.execute(_MSG_SELECT + " WHERE m.id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_history(path, room_id, limit=50, before_id=None):
    """Newest `limit` messages (oldest first). `before_id` pages further back."""
    sql = _MSG_SELECT + " WHERE m.room_id = ?"
    args = [room_id]
    if before_id:
        sql += " AND m.id < ?"
        args.append(before_id)
    sql += " ORDER BY m.id DESC LIMIT ?"
    args.append(limit)
    with session(path) as db:
        rows = db.execute(sql, args).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_messages_after(path, room_id, after_id, limit=200):
    """Messages newer than `after_id` (used to catch up after a reconnect)."""
    with session(path) as db:
        rows = db.execute(
            _MSG_SELECT + " WHERE m.room_id = ? AND m.id > ? ORDER BY m.id LIMIT ?",
            (room_id, after_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
