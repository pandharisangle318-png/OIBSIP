"""Authentication: register / login / logout routes plus session helpers."""

import functools
import hmac
import secrets

from flask import (Blueprint, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)

from . import database as db
from .service import ChatError, authenticate, register_user

bp = Blueprint("auth", __name__)


# ---- helpers ---------------------------------------------------------------

def db_path():
    return current_app.config["DATABASE"]


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def login_required(view):
    """Redirect browsers to /login, answer API calls with 401 JSON."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in first."), 401
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@bp.before_app_request
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = db.get_user(db_path(), user_id)
        if user is None:
            session.clear()
        else:
            g.user = user


@bp.before_app_request
def check_csrf():
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        expected = session.get("csrf", "")
        if not expected or not hmac.compare_digest(sent, expected):
            if request.path.startswith("/api/"):
                return jsonify(error="Invalid or missing CSRF token."), 400
            flash("Your session expired. Please try again.", "error")
            return redirect(url_for("auth.login"))


@bp.app_context_processor
def inject_globals():
    return {"csrf_token": csrf_token, "current_user": g.get("user")}


def _start_session(user):
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    csrf_token()


# ---- routes ----------------------------------------------------------------

@bp.route("/")
def index():
    return redirect(url_for("chat.chat_page" if g.user else "auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("chat.chat_page"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if password != request.form.get("confirm", ""):
            flash("The two passwords don't match.", "error")
        else:
            try:
                user = register_user(db_path(), request.form.get("username"), password)
            except ChatError as err:
                flash(err.message, "error")
            else:
                _start_session(user)
                return redirect(url_for("chat.chat_page"))
    return render_template("register.html", username=request.form.get("username", ""))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("chat.chat_page"))
    if request.method == "POST":
        try:
            user = authenticate(db_path(), request.form.get("username"), request.form.get("password"))
        except ChatError as err:
            flash(err.message, "error")
        else:
            _start_session(user)
            return redirect(url_for("chat.chat_page"))
    return render_template("login.html", username=request.form.get("username", ""))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
