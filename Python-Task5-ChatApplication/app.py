"""Flask application factory for ChatSphere."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from chatsphere import auth, chat
from chatsphere import database as db
from chatsphere.hub import Hub

BASE_DIR = Path(__file__).resolve().parent


def _load_secret_key(instance_dir):
    """Use SECRET_KEY from the environment, else make one and keep it in
    instance/secret.key so logins survive a server restart."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key and env_key != "change-me":
        return env_key
    key_file = Path(instance_dir) / "secret.key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key


def create_app(test_config=None):
    load_dotenv(BASE_DIR / ".env")
    instance_dir = BASE_DIR / "instance"
    instance_dir.mkdir(exist_ok=True)

    app = Flask(__name__, instance_path=str(instance_dir))
    app.config.update(
        DATABASE=os.environ.get("DATABASE_PATH", str(instance_dir / "chatsphere.db")),
        CSRF_ENABLED=True,
        LEAVE_GRACE_SECONDS=3,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_secret_key(instance_dir)

    db.init_db(app.config["DATABASE"])
    app.extensions["hub"] = Hub()

    app.register_blueprint(auth.bp)
    app.register_blueprint(chat.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(404)
    def not_found(_err):
        return render_template("error.html", code=404, text="That page doesn't exist."), 404

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify(error="Request too large."), 413

    @app.errorhandler(500)
    def server_error(_err):
        return render_template("error.html", code=500, text="Something went wrong on our side."), 500

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
