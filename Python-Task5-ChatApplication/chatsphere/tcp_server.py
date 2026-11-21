"""Plain TCP socket server for the CLI client.

Protocol: one JSON object per line, in both directions.

Client -> server                                  Server -> client
  {"cmd": "register", "username", "password"}      {"type": "ok", ...} / {"type": "error", "message"}
  {"cmd": "login",    "username", "password"}      {"type": "message", "message": {...}}
  {"cmd": "rooms"}                                 {"type": "system", "text", "created_at"}
  {"cmd": "join",     "room": "Lobby"}             {"type": "presence", "users": [...]}
  {"cmd": "say",      "text": "hello :smile:"}     {"type": "rooms" | "history" | "joined", ...}
  {"cmd": "who"} / {"cmd": "history"} / {"cmd": "quit"}
"""

import json
import socket
import socketserver
import threading

from . import database as db
from .service import ChatError, authenticate, register_user, send_message

MAX_LINE = 8192


class _Handler(socketserver.StreamRequestHandler):
    """One instance per connected client, each running in its own thread."""

    def setup(self):
        super().setup()
        self.user = None
        self.sub = None
        self.room = None
        self.write_lock = threading.Lock()
        self.alive = True

    # -- sending -----------------------------------------------------------

    def send(self, obj):
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self.write_lock:
            try:
                self.wfile.write(data)
                self.wfile.flush()
            except OSError:
                self.alive = False

    def _pump(self, sub):
        """Forward hub events for the current room to this socket."""
        import queue
        while self.alive and sub is self.sub:
            try:
                event = sub.get(timeout=0.5)
            except queue.Empty:
                continue
            self.send(event)

    # -- main loop ---------------------------------------------------------

    def handle(self):
        path = self.server.db_path
        self.send({"type": "hello", "message": "Welcome to ChatSphere. Please login or register."})
        try:
            while self.alive:
                raw = self.rfile.readline(MAX_LINE + 1)
                if not raw:
                    break  # client closed the connection
                if len(raw) > MAX_LINE:
                    self.send({"type": "error", "message": "Line too long."})
                    break
                try:
                    cmd = json.loads(raw.decode("utf-8"))
                    if not isinstance(cmd, dict):
                        raise ValueError
                except ValueError:
                    self.send({"type": "error", "message": "Invalid JSON."})
                    continue
                if cmd.get("cmd") == "quit":
                    self.send({"type": "ok", "message": "Goodbye!"})
                    break
                try:
                    self.dispatch(path, cmd)
                except ChatError as err:
                    self.send({"type": "error", "message": err.message})
        except (ConnectionError, OSError):
            pass

    def finish(self):
        self.alive = False
        self._leave_room()
        try:
            super().finish()
        except OSError:
            pass

    # -- commands ----------------------------------------------------------

    def dispatch(self, path, cmd):
        name = cmd.get("cmd")
        if name in ("login", "register"):
            if self.user:
                raise ChatError("You are already logged in.")
            if name == "register":
                self.user = register_user(path, cmd.get("username"), cmd.get("password"))
            else:
                self.user = authenticate(path, cmd.get("username"), cmd.get("password"))
            self.send({"type": "ok", "message": f"Logged in as {self.user['username']}",
                       "username": self.user["username"]})
            return

        if not self.user:
            raise ChatError("Please login first.", 401)

        if name == "rooms":
            self.send({"type": "rooms", "rooms": db.list_rooms(path)})
        elif name == "join":
            room = db.get_room_by_name(path, (cmd.get("room") or "").strip())
            if room is None:
                raise ChatError("No such room. Type /rooms to see the list.", 404)
            self._join_room(path, room)
        elif name == "say":
            if not self.room:
                raise ChatError("Join a room first with /join <name>.")
            send_message(path, self.server.hub, self.room["id"], self.user["id"], cmd.get("text"))
        elif name == "who":
            if not self.room:
                raise ChatError("Join a room first.")
            self.send({"type": "presence", "room_id": self.room["id"],
                       "users": self.server.hub.online_users(self.room["id"])})
        elif name == "history":
            if not self.room:
                raise ChatError("Join a room first.")
            msgs = db.get_history(path, self.room["id"], limit=20)
            self.send({"type": "history", "messages": msgs})
        else:
            raise ChatError(f"Unknown command: {name}")

    def _join_room(self, path, room):
        self._leave_room()
        self.room = room
        self.sub = self.server.hub.subscribe(room["id"], self.user["username"], kind="tcp")
        self.send({"type": "joined", "room": room["name"]})
        self.send({"type": "history", "messages": db.get_history(path, room["id"], limit=20)})
        threading.Thread(target=self._pump, args=(self.sub,), daemon=True).start()

    def _leave_room(self):
        if self.sub is not None:
            sub, self.sub = self.sub, None
            self.server.hub.unsubscribe(sub)


class ChatTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, db_path, hub):
        super().__init__(address, _Handler)
        self.db_path = db_path
        self.hub = hub


def start_tcp_server(host, port, db_path, hub):
    """Start the socket server in a background thread and return it."""
    server = ChatTCPServer((host, port), db_path, hub)
    thread = threading.Thread(target=server.serve_forever, name="chatsphere-tcp", daemon=True)
    thread.start()
    return server


def stop_tcp_server(server):
    server.shutdown()
    server.server_close()
