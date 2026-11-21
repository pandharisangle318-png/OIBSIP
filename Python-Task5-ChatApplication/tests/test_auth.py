from chatsphere import database as db


def test_register_creates_user_and_logs_in(client, register, app):
    resp = register()
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/chat")
    assert client.get("/chat").status_code == 200
    assert db.get_user_by_name(app.config["DATABASE"], "alice") is not None


def test_password_is_hashed_not_stored_plain(client, register, app):
    register(password="supersecret1")
    user = db.get_user_by_name(app.config["DATABASE"], "alice")
    assert "supersecret1" not in user["password_hash"]
    assert user["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_register_rejects_bad_input(client):
    for name, pw in [("ab", "password123"), ("bad name!", "password123"), ("okname", "short")]:
        resp = client.post("/register", data={"username": name, "password": pw, "confirm": pw})
        assert resp.status_code == 200  # form re-rendered with an error
        assert b"flash error" in resp.data


def test_register_password_mismatch(client):
    resp = client.post("/register", data={"username": "bob_1", "password": "password123", "confirm": "different123"})
    assert b"don&#39;t match" in resp.data


def test_duplicate_username_case_insensitive(client, register):
    register("Alice")
    other = client.application.test_client()
    resp = other.post("/register", data={"username": "alice", "password": "password123", "confirm": "password123"})
    assert b"already taken" in resp.data


def test_login_success_and_failure(client, register):
    register()
    client.post("/logout")
    bad = client.post("/login", data={"username": "alice", "password": "wrongpass1"})
    assert b"Invalid username or password" in bad.data
    ghost = client.post("/login", data={"username": "nobody", "password": "password123"})
    assert b"Invalid username or password" in ghost.data
    good = client.post("/login", data={"username": "alice", "password": "password123"})
    assert good.status_code == 302


def test_logout_ends_session(logged_in):
    assert logged_in.get("/chat").status_code == 200
    logged_in.post("/logout")
    assert logged_in.get("/chat").status_code == 302
    assert logged_in.get("/api/rooms").status_code == 401


def test_protected_routes_require_login(client):
    assert client.get("/chat").headers["Location"].endswith("/login")
    assert client.get("/api/rooms").status_code == 401
    assert client.post("/api/rooms/1/messages", json={"text": "hi"}).status_code == 401
    assert client.get("/api/rooms/1/stream").status_code == 401


def test_csrf_enforced_when_enabled(tmp_path):
    from app import create_app
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "c.db"), "SECRET_KEY": "k"})
    c = app.test_client()
    resp = c.post("/register", data={"username": "carol", "password": "password123", "confirm": "password123"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/login")
    page = c.get("/register").data.decode()
    token = page.split('name="csrf_token" value="')[1].split('"')[0]
    ok = c.post("/register", data={"csrf_token": token, "username": "carol",
                                   "password": "password123", "confirm": "password123"})
    assert ok.headers["Location"].endswith("/chat")


def test_pages_render_and_no_secrets_leak(client):
    for path in ("/login", "/register"):
        resp = client.get(path)
        assert resp.status_code == 200 and b"ChatSphere" in resp.data
    assert client.get("/missing").status_code == 404
    assert b"test-secret" not in client.get("/login").data


def test_app_generates_persistent_secret_key_when_none_given(tmp_path, monkeypatch):
    """Regression: a fresh install (no .env, no SECRET_KEY) must still serve pages."""
    from app import create_app
    monkeypatch.delenv("SECRET_KEY", raising=False)
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "k.db")})
    assert app.config["SECRET_KEY"]
    assert app.test_client().get("/login").status_code == 200
