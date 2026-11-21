import threading
import time

import client as cli
from chatsphere import database as db


def login(c, name="tina", pw="password123", cmd="register"):
    c.send(cmd=cmd, username=name, password=pw)
    return c.recv()


def test_server_accepts_connections_and_greets(tcp_server):
    import socket
    s = socket.create_connection(("127.0.0.1", tcp_server.server_address[1]), timeout=3)
    assert b"hello" in s.recv(1024)
    s.close()


def test_register_login_over_socket(make_tcp_client):
    c = make_tcp_client()
    assert login(c)["type"] == "ok"
    c2 = make_tcp_client()
    assert login(c2, pw="wrongpass12", cmd="login")["type"] == "error"
    assert login(c2, cmd="login")["type"] == "ok"


def test_commands_need_login(make_tcp_client):
    c = make_tcp_client()
    c.send(cmd="say", text="hi")
    assert c.recv()["type"] == "error"


def test_two_way_realtime_chat_with_timestamps_and_emoji(make_tcp_client):
    a, b = make_tcp_client(), make_tcp_client()
    login(a, "ann")
    login(b, "ben")
    a.send(cmd="join", room="Lobby")
    a.recv_until("joined")
    b.send(cmd="join", room="Lobby")
    b.recv_until("joined")

    a.send(cmd="say", text="hi ben :smile:")
    got = b.recv_until("message")["message"]
    assert got["body"] == "hi ben \U0001F60A" and got["username"] == "ann"
    assert got["created_at"]

    b.send(cmd="say", text="hello ann")
    seen = [a.recv_until("message")["message"]["body"] for _ in range(2)]
    assert seen == ["hi ben \U0001F60A", "hello ann"]  # sender also gets their own echo, in order


def test_disconnect_notifies_others(make_tcp_client):
    a, b = make_tcp_client(), make_tcp_client()
    login(a, "ann")
    login(b, "ben")
    for c in (a, b):
        c.send(cmd="join", room="Lobby")
        c.recv_until("joined")
    b.close()
    event = a.recv_until("system", text="ben left the room")
    assert event["created_at"]


def test_history_after_join(make_tcp_client, app):
    a = make_tcp_client()
    login(a, "hist")
    a.send(cmd="join", room="Random")
    a.recv_until("history")
    a.send(cmd="say", text="remember me")
    a.recv_until("message")
    b = make_tcp_client()
    login(b, "other")
    b.send(cmd="join", room="Random")
    hist = b.recv_until("history")
    assert [m["body"] for m in hist["messages"]] == ["remember me"]


def test_bad_room_and_bad_json(make_tcp_client):
    c = make_tcp_client()
    login(c)
    c.send(cmd="join", room="Nope")
    assert c.recv()["type"] == "error"
    c.sock.sendall(b"this is not json\n")
    assert c.recv()["type"] == "error"


def test_web_and_tcp_clients_share_rooms(make_tcp_client, logged_in, app):
    c = make_tcp_client()
    login(c, "cliuser")
    c.send(cmd="join", room="Lobby")
    c.recv_until("joined")
    room = db.get_room_by_name(app.config["DATABASE"], "Lobby")["id"]
    logged_in.post(f"/api/rooms/{room}/messages", json={"text": "from the browser"})
    assert c.recv_until("message")["message"]["body"] == "from the browser"


def test_cli_formatting_helpers():
    line = cli.format_event({"type": "message", "message": {
        "created_at": "2026-01-01T10:00:00+00:00", "username": "x", "body": "hey"}})
    assert line.startswith("[") and "x: hey" in line
    assert cli.format_event({"type": "error", "message": "nope"}) == "! nope"
    assert "online: a, b" in cli.format_event({"type": "presence", "users": ["a", "b"]})


def test_cli_client_class_end_to_end(tcp_server, capsys):
    c = cli.Client("127.0.0.1", tcp_server.server_address[1])
    t = threading.Thread(target=c.listen, daemon=True)
    t.start()
    c.send(cmd="register", username="clibot", password="password123")
    assert c.logged_in.wait(3) and c.login_ok
    c.send(cmd="join", room="Lobby")
    c.send(cmd="say", text="ping :tada:")
    time.sleep(0.6)
    c.close()
    out = capsys.readouterr().out
    assert "clibot: ping \U0001F389" in out
