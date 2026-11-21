# ChatSphere Architecture

## Overview

```
 Browser (HTML/CSS/JS)                      CLI (client.py)
   |  HTTP (fetch)   ^ SSE stream              |  TCP, JSON lines
   v                 |                         v
 Flask app (auth.py, chat.py) ----+---- TCP server (tcp_server.py)
                                  |
                           service.py   <- validation, emoji, store + broadcast
                             |      |
                    database.py    hub.py
                     (SQLite)   (live fan-out)
```

## Modules

| Module | Responsibility |
|---|---|
| `app.py` | Application factory: config, secret key, blueprints, error pages, security headers |
| `run_server.py` | Starts the TCP server thread and the Flask server |
| `chatsphere/auth.py` | Register/login/logout routes, session loading, CSRF check, `login_required` |
| `chatsphere/chat.py` | Chat page, room/message JSON API, SSE stream endpoint |
| `chatsphere/service.py` | Rules shared by web and CLI: input validation, hashing, emoji conversion, `send_message` |
| `chatsphere/database.py` | SQLite schema and parameterised queries |
| `chatsphere/hub.py` | Thread-safe pub/sub: per-room subscribers, presence, join/leave notices |
| `chatsphere/tcp_server.py` | Threaded socket server speaking JSON lines |
| `chatsphere/emoji.py` | Shortcode table and converter |
| `client.py` | Terminal client |

## Data model (SQLite)

- `users(id, username UNIQUE NOCASE, password_hash, created_at)`
- `rooms(id, name UNIQUE NOCASE, description, created_by, created_at)`
- `messages(id, room_id, user_id, body, created_at)` with index on `(room_id, id)`

Timestamps are stored as UTC ISO-8601 and converted to local time by each client.

## Message flow

1. A client sends text (HTTP POST from the browser, `say` command from the CLI).
2. `service.send_message` validates it (1-1000 chars), converts emoji shortcodes, writes it to SQLite.
3. The saved row is published to the `Hub`, which puts it on the queue of every subscriber in that room.
4. Each browser's open SSE response and each TCP handler thread drains its queue and pushes the event out. The sender receives its own message too; the browser de-duplicates by message id.

## Why SSE + TCP instead of Socket.IO

Flask-SocketIO could not be installed in the build environment (no package network access), so the real-time layer uses the standard library and plain Flask. The hub is transport-agnostic, so a Socket.IO transport could be added later as another subscriber type without changing the service or database layers.

- **Browser to server**: ordinary `fetch` POST. **Server to browser**: Server-Sent Events, which reconnect automatically and send `Last-Event-ID` so missed messages are replayed from SQLite.
- **CLI**: a raw TCP socket, demonstrating socket-based client/server communication. Protocol is one JSON object per line.

## Presence and disconnects

The hub counts open connections per user per room. A user is announced as joined on the first connection and as left when the last one closes. For browsers a short grace period (3 s) hides page refreshes. Flask only notices a closed SSE connection when it next writes, so a 5 s keepalive bounds detection time to about 8 s; TCP disconnects are detected immediately.

## Notifications

`app.js` requests Notification permission (banner or bell button). When a message arrives while `document.hidden` or the window lacks focus, it raises a desktop notification, increments the `(n)` tab-title counter and shows a per-room unread badge. Other rooms are polled every 8 s for new-message counts.

## Security

- Password hashing with Werkzeug (`scrypt`, per-user salt); a dummy hash equalises login timing for unknown users.
- Session cookie is HttpOnly, SameSite=Lax; CSRF token required on all state-changing requests.
- Parameterised SQL only; messages rendered with `textContent`.
- Request size limit, input validation, generic login errors.
- No end-to-end encryption is implemented or claimed.

## Limitations

The hub is in memory, so run a single server process. The Flask development server is suitable for localhost demos; use a production server for anything else.
