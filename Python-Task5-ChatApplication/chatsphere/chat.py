"""Chat pages and JSON/SSE endpoints used by the browser."""

import json
import queue

from flask import (Blueprint, Response, current_app, g, jsonify, render_template,
                   request, stream_with_context)

from . import database as db
from .auth import db_path, login_required
from .emoji import picker_list
from .service import ChatError, make_room, send_message

bp = Blueprint("chat", __name__)

KEEPALIVE_SECONDS = 5  # also how quickly a closed tab is noticed


def hub():
    return current_app.extensions["hub"]


@bp.errorhandler(ChatError)
def handle_chat_error(err):
    return jsonify(error=err.message), err.status


@bp.route("/chat")
@login_required
def chat_page():
    return render_template("chat.html", emojis=picker_list())


# ---- rooms -----------------------------------------------------------------

@bp.route("/api/rooms", methods=["GET"])
@login_required
def rooms():
    return jsonify(rooms=db.list_rooms(db_path()))


@bp.route("/api/rooms", methods=["POST"])
@login_required
def create_room():
    data = request.get_json(silent=True) or {}
    room = make_room(db_path(), data.get("name"), data.get("description"), g.user["id"])
    return jsonify(room=room), 201


# ---- messages --------------------------------------------------------------

@bp.route("/api/rooms/<int:room_id>/messages", methods=["GET"])
@login_required
def history(room_id):
    if db.get_room(db_path(), room_id) is None:
        raise ChatError("Room not found.", 404)
    before = request.args.get("before", type=int)
    limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
    messages = db.get_history(db_path(), room_id, limit=limit, before_id=before)
    return jsonify(messages=messages, has_more=len(messages) == limit)


@bp.route("/api/rooms/<int:room_id>/messages", methods=["POST"])
@login_required
def post_message(room_id):
    data = request.get_json(silent=True) or {}
    message = send_message(db_path(), hub(), room_id, g.user["id"], data.get("text"))
    return jsonify(message=message), 201


# ---- live stream (Server-Sent Events) --------------------------------------

def _sse(event, event_id=None):
    out = ""
    if event_id is not None:
        out += f"id: {event_id}\n"
    return out + f"data: {json.dumps(event)}\n\n"


@bp.route("/api/rooms/<int:room_id>/stream")
@login_required
def stream(room_id):
    path = db_path()
    if db.get_room(path, room_id) is None:
        raise ChatError("Room not found.", 404)

    username = g.user["username"]
    hub_ = hub()
    grace = current_app.config["LEAVE_GRACE_SECONDS"]
    # The browser sends Last-Event-ID itself when it reconnects; on the very
    # first connect the page passes ?after=<newest id it already has>.
    last_id = request.headers.get("Last-Event-ID", type=int) or request.args.get("after", type=int)

    @stream_with_context
    def generate():
        sub = hub_.subscribe(room_id, username, kind="web")
        try:
            # Subscribe first, then catch up, so nothing is lost in between.
            # The browser ignores any message id it has already drawn.
            if last_id:
                for msg in db.get_messages_after(path, room_id, last_id):
                    yield _sse({"type": "message", "message": msg}, msg["id"])
            while True:
                try:
                    event = sub.get(timeout=KEEPALIVE_SECONDS)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                event_id = event["message"]["id"] if event["type"] == "message" else None
                yield _sse(event, event_id)
        finally:
            hub_.unsubscribe(sub, grace=grace)

    resp = Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp
