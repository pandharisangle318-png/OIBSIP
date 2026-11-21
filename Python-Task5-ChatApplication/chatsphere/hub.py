"""The Hub: in-memory fan-out of chat events to every connected client.

Both the browser (Server-Sent Events) and the CLI (raw TCP sockets) subscribe
here, so a message sent from one shows up in the other instantly.
"""

import queue
import threading
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Subscriber:
    """One live connection listening to one room."""

    def __init__(self, room_id, username, kind):
        self.room_id = room_id
        self.username = username
        self.kind = kind  # "web" or "tcp"
        self.queue = queue.Queue()

    def put(self, event):
        self.queue.put(event)

    def get(self, timeout=None):
        return self.queue.get(timeout=timeout)


class Hub:
    def __init__(self):
        self._lock = threading.RLock()
        self._subs = {}      # room_id -> set(Subscriber)
        self._counts = {}    # room_id -> {username: open connection count}
        self._online = {}    # room_id -> set(usernames announced as online)

    # ---- subscribe / unsubscribe ------------------------------------------

    def subscribe(self, room_id, username, kind="web"):
        sub = Subscriber(room_id, username, kind)
        with self._lock:
            self._subs.setdefault(room_id, set()).add(sub)
            counts = self._counts.setdefault(room_id, {})
            counts[username] = counts.get(username, 0) + 1
            online = self._online.setdefault(room_id, set())
            first_time = username not in online
            online.add(username)
            if first_time:
                self._broadcast(room_id, self._system(room_id, f"{username} joined the room"))
                self._broadcast(room_id, self._presence(room_id))
            else:
                sub.put(self._presence(room_id))
        return sub

    def unsubscribe(self, sub, grace=0):
        """Remove a connection. With grace > 0 we wait before announcing the
        departure, so a page refresh or SSE reconnect doesn't spam the room."""
        with self._lock:
            self._subs.get(sub.room_id, set()).discard(sub)
            counts = self._counts.get(sub.room_id, {})
            counts[sub.username] = max(0, counts.get(sub.username, 1) - 1)
        if grace > 0:
            timer = threading.Timer(grace, self._announce_leave, (sub.room_id, sub.username))
            timer.daemon = True
            timer.start()
        else:
            self._announce_leave(sub.room_id, sub.username)

    def _announce_leave(self, room_id, username):
        with self._lock:
            if self._counts.get(room_id, {}).get(username, 0) > 0:
                return  # they came back in time
            online = self._online.get(room_id, set())
            if username not in online:
                return
            online.discard(username)
            self._counts.get(room_id, {}).pop(username, None)
            self._broadcast(room_id, self._system(room_id, f"{username} left the room"))
            self._broadcast(room_id, self._presence(room_id))

    # ---- publishing -------------------------------------------------------

    def publish_message(self, message):
        event = {"type": "message", "message": message}
        with self._lock:
            self._broadcast(message["room_id"], event)

    def online_users(self, room_id):
        with self._lock:
            return sorted(self._online.get(room_id, set()), key=str.lower)

    def total_connections(self):
        with self._lock:
            return sum(len(s) for s in self._subs.values())

    # ---- internals --------------------------------------------------------

    def _broadcast(self, room_id, event):
        for sub in list(self._subs.get(room_id, ())):
            sub.put(event)

    def _system(self, room_id, text):
        return {"type": "system", "room_id": room_id, "text": text, "created_at": _now()}

    def _presence(self, room_id):
        return {
            "type": "presence",
            "room_id": room_id,
            "users": sorted(self._online.get(room_id, set()), key=str.lower),
        }
