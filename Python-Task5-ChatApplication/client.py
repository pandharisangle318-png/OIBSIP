"""ChatSphere command-line client.

Connects to the TCP server started by run_server.py, so you can chat from a
terminal while other people use the web app.

    python client.py                      # localhost:5001
    python client.py --host 127.0.0.1 --port 5001
"""

import argparse
import getpass
import json
import socket
import sys
import threading
from datetime import datetime

HELP = """Commands:
  /rooms          list chat rooms
  /join <room>    join a room (e.g. /join Lobby)
  /who            who is online in this room
  /history        show the last 20 messages again
  /help           show this help
  /quit           leave ChatSphere
Anything else you type is sent as a message. Try :smile: or :fire:"""


def local_time(iso_string):
    """Turn the server's UTC timestamp into local HH:MM:SS."""
    try:
        return datetime.fromisoformat(iso_string).astimezone().strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return datetime.now().strftime("%H:%M:%S")


def format_event(event):
    """Return a printable line for a server event, or None to stay quiet."""
    kind = event.get("type")
    if kind == "message":
        m = event["message"]
        return f"[{local_time(m['created_at'])}] {m['username']}: {m['body']}"
    if kind == "system":
        return f"[{local_time(event.get('created_at'))}] * {event['text']}"
    if kind == "presence":
        return f"  online: {', '.join(event['users']) or 'nobody'}"
    if kind == "history":
        lines = [f"[{local_time(m['created_at'])}] {m['username']}: {m['body']}" for m in event["messages"]]
        return "--- recent messages ---\n" + "\n".join(lines) + "\n-----------------------" if lines else "--- no messages yet ---"
    if kind == "rooms":
        return "Rooms:\n" + "\n".join(f"  {r['name']} - {r['description']}" for r in event["rooms"])
    if kind == "joined":
        return f"Joined room: {event['room']}"
    if kind == "error":
        return f"! {event['message']}"
    if kind in ("ok", "hello"):
        return event.get("message")
    return None


class Client:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.reader = self.sock.makefile("r", encoding="utf-8", newline="\n")
        self.logged_in = threading.Event()
        self.login_ok = False
        self.closed = threading.Event()
        self.print_lock = threading.Lock()

    def send(self, **payload):
        self.sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

    def say(self, text):
        with self.print_lock:
            print(text)

    def listen(self):
        """Background thread: print everything the server sends."""
        try:
            for line in self.reader:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "ok" and "username" in event:
                    self.login_ok = True
                    self.logged_in.set()
                elif event.get("type") == "error" and not self.login_ok:
                    self.logged_in.set()  # login/register was rejected
                text = format_event(event)
                if text:
                    self.say(text)
        except (OSError, ValueError):
            pass
        finally:
            self.closed.set()
            self.logged_in.set()  # unblock the login prompt if we're still waiting

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def login_flow(client):
    """Ask for credentials until the server accepts them."""
    while not client.closed.is_set():
        choice = input("Do you have an account? [l]ogin / [r]egister: ").strip().lower()
        if choice not in ("l", "r", "login", "register"):
            continue
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        client.logged_in.clear()
        client.send(cmd="register" if choice.startswith("r") else "login",
                    username=username, password=password)
        client.logged_in.wait(timeout=10)
        if client.closed.is_set():
            return False
        if client.login_ok:
            return True
        # otherwise the server already printed the error - ask again
    return False


def main():
    # Windows consoles often default to a legacy encoding that can't print emoji.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="ChatSphere CLI client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()

    try:
        client = Client(args.host, args.port)
    except OSError as err:
        print(f"Could not connect to {args.host}:{args.port} - is run_server.py running? ({err})")
        return 1

    threading.Thread(target=client.listen, daemon=True).start()

    try:
        if not login_flow(client):
            print("Disconnected from server.")
            return 1
        client.send(cmd="join", room="Lobby")
        client.say(HELP)
        while not client.closed.is_set():
            try:
                line = input().strip()
            except EOFError:
                break
            if not line:
                continue
            if line.startswith("/"):
                parts = line[1:].split(maxsplit=1)
                command, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
                if command in ("quit", "exit"):
                    client.send(cmd="quit")
                    break
                if command == "help":
                    client.say(HELP)
                elif command == "join":
                    client.send(cmd="join", room=arg)
                elif command in ("rooms", "who", "history"):
                    client.send(cmd=command)
                else:
                    client.say("Unknown command. Type /help")
            else:
                client.send(cmd="say", text=line)
    except (KeyboardInterrupt, BrokenPipeError, ConnectionError):
        pass
    finally:
        client.closed.wait(timeout=0.3)
        client.close()
        print("\nBye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
