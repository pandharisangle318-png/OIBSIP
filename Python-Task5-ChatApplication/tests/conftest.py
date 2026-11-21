import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from chatsphere.tcp_server import start_tcp_server, stop_tcp_server  # noqa: E402


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "SECRET_KEY": "test-secret",
        "CSRF_ENABLED": False,
        "LEAVE_GRACE_SECONDS": 0,
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register(client):
    def _register(username="alice", password="password123", c=None):
        c = c or client
        return c.post("/register", data={"username": username, "password": password,
                                         "confirm": password}, follow_redirects=False)
    return _register


@pytest.fixture
def logged_in(client, register):
    register()
    return client


@pytest.fixture
def tcp_server(app):
    server = start_tcp_server("127.0.0.1", 0, app.config["DATABASE"], app.extensions["hub"])
    yield server
    stop_tcp_server(server)


class LineClient:
    """Tiny helper that speaks the TCP protocol used by client.py."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.file = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def send(self, **payload):
        self.sock.sendall((json.dumps(payload) + "\n").encode())

    def recv(self):
        return json.loads(self.file.readline())

    def recv_until(self, kind, **match):
        for _ in range(30):
            event = self.recv()
            if event.get("type") == kind and all(event.get(k) == v for k, v in match.items()):
                return event
        raise AssertionError(f"never saw {kind}")

    def close(self):
        try:
            self.file.close()
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except OSError:
            pass


@pytest.fixture
def make_tcp_client(tcp_server):
    port = tcp_server.server_address[1]
    made = []

    def _make():
        c = LineClient(port)
        made.append(c)
        c.recv()  # hello banner
        return c

    yield _make
    for c in made:
        c.close()
