import json
import re
from pathlib import Path
from datetime import datetime

from chatsphere import database as db
from chatsphere.emoji import convert_shortcodes

ROOT = Path(__file__).resolve().parent.parent


# ---- emoji -----------------------------------------------------------------

def test_emoji_conversion():
    assert convert_shortcodes("hi :smile:") == "hi \U0001F60A"
    assert convert_shortcodes(":fire::rocket:") == "\U0001F525\U0001F680"
    assert convert_shortcodes(":SMILE:") == "\U0001F60A"
    assert convert_shortcodes(":notreal: stays") == ":notreal: stays"
    assert convert_shortcodes("time 10:30:45 ok") == "time 10:30:45 ok"


# ---- rooms -----------------------------------------------------------------

def test_default_rooms_seeded(logged_in):
    rooms = logged_in.get("/api/rooms").get_json()["rooms"]
    assert {"Lobby", "Study Hall", "Tech Talk", "Random"} <= {r["name"] for r in rooms}


def test_create_room(logged_in):
    resp = logged_in.post("/api/rooms", json={"name": "Python Help", "description": "Ask away"})
    assert resp.status_code == 201
    names = [r["name"] for r in logged_in.get("/api/rooms").get_json()["rooms"]]
    assert "Python Help" in names


def test_create_room_validation(logged_in):
    assert logged_in.post("/api/rooms", json={"name": "x"}).status_code == 400
    assert logged_in.post("/api/rooms", json={"name": "<script>"}).status_code == 400
    assert logged_in.post("/api/rooms", json={"name": "Ok Room", "description": "d" * 200}).status_code == 400
    assert logged_in.post("/api/rooms", json={"name": "lobby"}).status_code == 409


# ---- messages & history ----------------------------------------------------

def _lobby(client):
    return next(r for r in client.get("/api/rooms").get_json()["rooms"] if r["name"] == "Lobby")["id"]


def test_send_message_with_timestamp_and_emoji(logged_in):
    room = _lobby(logged_in)
    resp = logged_in.post(f"/api/rooms/{room}/messages", json={"text": "hello :smile:"})
    assert resp.status_code == 201
    msg = resp.get_json()["message"]
    assert msg["body"] == "hello \U0001F60A"
    assert msg["username"] == "alice"
    stamp = datetime.fromisoformat(msg["created_at"])
    assert stamp.tzinfo is not None


def test_message_validation(logged_in):
    room = _lobby(logged_in)
    assert logged_in.post(f"/api/rooms/{room}/messages", json={"text": "   "}).status_code == 400
    assert logged_in.post(f"/api/rooms/{room}/messages", json={"text": "x" * 1001}).status_code == 400
    assert logged_in.post("/api/rooms/9999/messages", json={"text": "hi"}).status_code == 404
    assert logged_in.post(f"/api/rooms/{room}/messages", data="not json").status_code == 400


def test_history_persisted_in_sqlite_and_paged(logged_in, app):
    room = _lobby(logged_in)
    for i in range(7):
        logged_in.post(f"/api/rooms/{room}/messages", json={"text": f"msg {i}"})
    # straight from the database file
    assert len(db.get_history(app.config["DATABASE"], room, limit=100)) == 7
    page1 = logged_in.get(f"/api/rooms/{room}/messages?limit=3").get_json()
    assert [m["body"] for m in page1["messages"]] == ["msg 4", "msg 5", "msg 6"]
    assert page1["has_more"] is True
    oldest = page1["messages"][0]["id"]
    page2 = logged_in.get(f"/api/rooms/{room}/messages?limit=3&before={oldest}").get_json()
    assert [m["body"] for m in page2["messages"]] == ["msg 1", "msg 2", "msg 3"]


def test_history_is_per_room(logged_in):
    rooms = logged_in.get("/api/rooms").get_json()["rooms"]
    a, b = rooms[0]["id"], rooms[1]["id"]
    logged_in.post(f"/api/rooms/{a}/messages", json={"text": "only in a"})
    assert logged_in.get(f"/api/rooms/{b}/messages").get_json()["messages"] == []


def test_html_is_stored_as_text_not_executed(logged_in):
    room = _lobby(logged_in)
    logged_in.post(f"/api/rooms/{room}/messages", json={"text": "<b>hi</b>"})
    body = logged_in.get(f"/api/rooms/{room}/messages").get_json()["messages"][0]["body"]
    assert body == "<b>hi</b>"  # the browser inserts it with textContent, never innerHTML
    js = open(ROOT / "static/js/app.js", encoding="utf-8").read()
    assert "innerHTML" not in js


# ---- real-time hub ---------------------------------------------------------

def test_message_reaches_subscribers_in_real_time(logged_in, app):
    room = _lobby(logged_in)
    hub = app.extensions["hub"]
    sub = hub.subscribe(room, "bob", kind="web")
    logged_in.post(f"/api/rooms/{room}/messages", json={"text": "live!"})
    events = []
    while not sub.queue.empty():
        events.append(sub.get())
    assert any(e["type"] == "message" and e["message"]["body"] == "live!" for e in events)


def test_join_leave_and_presence(app):
    hub = app.extensions["hub"]
    watcher = hub.subscribe(1, "watcher")
    hub.subscribe(1, "dave")
    assert hub.online_users(1) == ["dave", "watcher"]
    bob = hub.subscribe(1, "erin")
    hub.unsubscribe(bob)  # grace 0 -> announces immediately
    texts = []
    while not watcher.queue.empty():
        e = watcher.get()
        if e["type"] == "system":
            texts.append(e["text"])
    assert "dave joined the room" in texts
    assert "erin left the room" in texts
    assert "erin" not in hub.online_users(1)


def test_second_tab_does_not_announce_twice(app):
    hub = app.extensions["hub"]
    watcher = hub.subscribe(1, "watcher")
    t1 = hub.subscribe(1, "frank")
    t2 = hub.subscribe(1, "frank")
    hub.unsubscribe(t1)
    assert "frank" in hub.online_users(1)  # still connected via the second tab
    hub.unsubscribe(t2)
    assert "frank" not in hub.online_users(1)
    joins = [e for e in list(watcher.queue.queue) if e["type"] == "system" and "frank joined" in e["text"]]
    assert len(joins) == 1


def test_sse_stream_delivers_events(logged_in, app):
    """Open the real SSE endpoint and read the first events."""
    room = _lobby(logged_in)
    first = logged_in.post(f"/api/rooms/{room}/messages", json={"text": "old"}).get_json()["message"]
    logged_in.post(f"/api/rooms/{room}/messages", json={"text": "missed while offline"})
    # reconnecting with the last id seen replays only what was missed
    resp = logged_in.get(f"/api/rooms/{room}/stream?after={first['id']}", buffered=False)
    assert resp.mimetype == "text/event-stream"
    it = iter(resp.response)
    seen = []
    for _ in range(4):
        chunk = next(it)
        chunk = chunk.decode() if isinstance(chunk, bytes) else chunk
        for line in chunk.splitlines():
            if line.startswith("data: "):
                seen.append(json.loads(line[6:]))
        if any(e["type"] == "presence" for e in seen):
            break
    types = {e["type"] for e in seen}
    assert "message" in types and "presence" in types
    bodies = [e["message"]["body"] for e in seen if e["type"] == "message"]
    assert bodies == ["missed while offline"]
    resp.close()


# ---- notification support (static checks on shipped front-end) -------------

def test_notification_code_present():
    js = open(ROOT / "static/js/app.js", encoding="utf-8").read()
    for needle in ("Notification.requestPermission", "new Notification", "document.hidden",
                   "hasFocus", "visibilitychange"):
        assert needle in js
    html = open(ROOT / "templates/chat.html", encoding="utf-8").read()
    for el_id in ("notify-enable", "bell-btn", "notify-banner"):
        assert el_id in html


def test_every_button_in_chat_template_is_wired():
    html = open(ROOT / "templates/chat.html", encoding="utf-8").read()
    js = open(ROOT / "static/js/app.js", encoding="utf-8").read()
    ids = set(re.findall(r'<button[^>]*\bid="([^"]+)"', html))
    assert ids
    for i in ids:
        assert f'$("{i}")' in js, f"button #{i} has no handler"
