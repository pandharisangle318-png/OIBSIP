// ChatSphere web client: rooms, live messages (Server-Sent Events), notifications.
(function () {
  "use strict";

  var app = document.getElementById("app");
  var ME = app.dataset.username;
  var CSRF = app.dataset.csrf;

  var $ = function (id) { return document.getElementById(id); };
  var feed = $("feed"), input = $("input"), sendBtn = $("send");

  var state = {
    rooms: [],
    room: null,          // current room object
    source: null,        // EventSource
    seen: {},            // message ids already drawn in this room
    oldestId: null,
    newestId: 0,
    hasMore: false,
    unread: {},          // room id -> count
    lastCounts: {},      // room id -> message_count from last poll
    unreadTotal: 0,
    notifyOn: true
  };

  // ---- small helpers -------------------------------------------------------

  function safeStore(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* storage blocked - ignore */ }
    return null;
  }

  function api(method, url, body) {
    var opts = { method: method, headers: { "X-CSRF-Token": CSRF }, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (res) {
      if (res.status === 401) { window.location = "/login"; throw new Error("Not logged in"); }
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || "Something went wrong.");
        return data;
      });
    });
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function hue(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
    return h;
  }

  function avatar(name, size) {
    var a = el("div", "avatar" + (size ? " " + size : ""), name.charAt(0).toUpperCase());
    a.style.background = "linear-gradient(135deg, hsl(" + hue(name) + " 75% 62%), hsl(" + ((hue(name) + 50) % 360) + " 70% 48%))";
    return a;
  }

  function toast(text, kind) {
    var t = el("div", "toast " + (kind || ""), text);
    $("toasts").appendChild(t);
    setTimeout(function () { t.classList.add("out"); }, 3200);
    setTimeout(function () { t.remove(); }, 3700);
  }

  function parseTime(iso) { return new Date(iso); }
  function fmtTime(d) { return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  function fmtDay(d) {
    var today = new Date(), y = new Date();
    y.setDate(today.getDate() - 1);
    if (d.toDateString() === today.toDateString()) return "Today";
    if (d.toDateString() === y.toDateString()) return "Yesterday";
    return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }

  function nearBottom() { return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 140; }
  function scrollBottom() { feed.scrollTop = feed.scrollHeight; }

  // ---- rooms ---------------------------------------------------------------

  function renderRooms() {
    var list = $("room-list");
    list.textContent = "";
    state.rooms.forEach(function (r) {
      var b = el("button", "room" + (state.room && state.room.id === r.id ? " active" : ""));
      b.type = "button";
      var orb = el("span", "orb", r.name.charAt(0).toUpperCase());
      orb.style.background = "linear-gradient(135deg, hsl(" + hue(r.name) + " 80% 65%), hsl(" + ((hue(r.name) + 60) % 360) + " 75% 45%))";
      var txt = el("span", "room-txt");
      txt.appendChild(el("strong", "", r.name));
      txt.appendChild(el("small", "", r.description || "No description"));
      b.appendChild(orb);
      b.appendChild(txt);
      var n = state.unread[r.id] || 0;
      if (n > 0) b.appendChild(el("span", "badge", n > 99 ? "99+" : String(n)));
      b.addEventListener("click", function () { openRoom(r); closeRail(); });
      list.appendChild(b);
    });
  }

  function loadRooms(isPoll) {
    return api("GET", "/api/rooms").then(function (data) {
      data.rooms.forEach(function (r) {
        var prev = state.lastCounts[r.id];
        var isCurrent = state.room && state.room.id === r.id;
        if (prev !== undefined && !isCurrent && r.message_count > prev) {
          state.unread[r.id] = (state.unread[r.id] || 0) + (r.message_count - prev);
          if (isPoll) notifyOther(r, r.message_count - prev);
        }
        state.lastCounts[r.id] = r.message_count;
      });
      state.rooms = data.rooms;
      renderRooms();
      updateTitleBadge();
      return data.rooms;
    });
  }

  function openRoom(room) {
    if (state.room && state.room.id === room.id) return;
    if (state.source) { state.source.close(); state.source = null; }
    state.room = room;
    state.seen = {};
    state.oldestId = null;
    state.newestId = 0;
    state.unread[room.id] = 0;
    feed.textContent = "";
    lastRendered = { user: null, time: 0, day: "" };
    $("room-title").textContent = room.name;
    $("room-desc").textContent = room.description || "";
    $("online-count").textContent = "0";
    $("people-list").textContent = "";
    input.disabled = false;
    sendBtn.disabled = false;
    input.placeholder = "Message " + room.name + "...  (try :smile: or :fire:)";
    safeStore("chatsphere.room", String(room.id));
    renderRooms();
    updateTitleBadge();

    api("GET", "/api/rooms/" + room.id + "/messages?limit=50").then(function (data) {
      if (state.room.id !== room.id) return;
      state.hasMore = data.has_more;
      addLoadMore();
      data.messages.forEach(function (m) { addMessage(m, { silent: true }); });
      if (!data.messages.length) addSystem("This room is quiet. Say something first!");
      scrollBottom();
      connectStream(room);
    }).catch(function (e) { toast(e.message, "error"); });
  }

  function connectStream(room) {
    setConn("connecting");
    var es = new EventSource("/api/rooms/" + room.id + "/stream?after=" + state.newestId);
    state.source = es;
    es.onopen = function () { setConn("live"); };
    es.onerror = function () { setConn(es.readyState === 2 ? "offline" : "connecting"); };
    es.onmessage = function (ev) {
      if (state.room.id !== room.id) return;
      var data;
      try { data = JSON.parse(ev.data); } catch (e) { return; }
      if (data.type === "message") addMessage(data.message, {});
      else if (data.type === "system") addSystem(data.text);
      else if (data.type === "presence") renderPeople(data.users);
    };
  }

  function setConn(kind) {
    var box = $("conn-state");
    box.className = "live " + kind;
    box.querySelector("em").textContent = { live: "Live", connecting: "Reconnecting", offline: "Offline" }[kind] || "";
  }

  // ---- rendering messages --------------------------------------------------

  var lastRendered = { user: null, time: 0, day: "" };

  function addLoadMore() {
    var old = $("load-more");
    if (old) old.remove();
    if (!state.hasMore) return;
    var b = el("button", "load-more", "Load earlier messages");
    b.id = "load-more";
    b.type = "button";
    b.addEventListener("click", loadEarlier);
    feed.insertBefore(b, feed.firstChild);
  }

  function loadEarlier() {
    if (!state.oldestId) return;
    var room = state.room, prevHeight = feed.scrollHeight;
    api("GET", "/api/rooms/" + room.id + "/messages?limit=50&before=" + state.oldestId).then(function (data) {
      if (state.room.id !== room.id) return;
      state.hasMore = data.has_more;
      var frag = document.createDocumentFragment();
      var oldFirst = feed.querySelector(".msg, .day, .sys");
      data.messages.forEach(function (m) {
        if (state.seen[m.id]) return;
        state.seen[m.id] = true;
        frag.appendChild(buildMessage(m, true));
        if (!state.oldestId || m.id < state.oldestId) state.oldestId = m.id;
      });
      feed.insertBefore(frag, oldFirst);
      addLoadMore();
      feed.scrollTop = feed.scrollHeight - prevHeight;
    }).catch(function (e) { toast(e.message, "error"); });
  }

  function buildMessage(m, standalone) {
    var d = parseTime(m.created_at);
    var mine = m.username === ME;
    var row = el("article", "msg " + (mine ? "mine" : "theirs"));
    row.dataset.id = m.id;
    if (!mine) row.appendChild(avatar(m.username, "sm"));
    var bubble = el("div", "bubble");
    var meta = el("div", "meta");
    if (!mine) meta.appendChild(el("strong", "", m.username));
    var t = el("time", "", fmtTime(d));
    t.dateTime = m.created_at;
    t.title = d.toLocaleString();
    meta.appendChild(t);
    bubble.appendChild(meta);
    bubble.appendChild(el("p", "text", m.body));
    row.appendChild(bubble);
    return row;
  }

  function addMessage(m, opts) {
    if (state.seen[m.id]) return;
    state.seen[m.id] = true;
    var stick = nearBottom() || m.username === ME;
    var d = parseTime(m.created_at);
    var dayKey = d.toDateString();
    if (dayKey !== lastRendered.day) {
      feed.appendChild(el("div", "day", fmtDay(d)));
      lastRendered.day = dayKey;
      lastRendered.user = null;
    }
    var row = buildMessage(m);
    var grouped = lastRendered.user === m.username && (d - lastRendered.time) < 5 * 60 * 1000;
    if (grouped) row.classList.add("grouped");
    lastRendered.user = m.username;
    lastRendered.time = d;
    var empty = feed.querySelector(".sys.hint");
    if (empty) empty.remove();
    feed.appendChild(row);
    if (state.oldestId === null || m.id < state.oldestId) state.oldestId = m.id;
    if (m.id > state.newestId) state.newestId = m.id;
    if (stick) scrollBottom();
    if (!opts.silent && m.username !== ME) notifyMessage(m);
  }

  function addSystem(text) {
    var s = el("div", "sys", text);
    if (/quiet/.test(text)) s.classList.add("hint");
    feed.appendChild(s);
    lastRendered.user = null;
    if (nearBottom()) scrollBottom();
  }

  function renderPeople(users) {
    $("online-count").textContent = String(users.length);
    var ul = $("people-list");
    ul.textContent = "";
    users.forEach(function (u) {
      var li = el("li");
      li.appendChild(avatar(u, "sm"));
      li.appendChild(el("span", "", u + (u === ME ? " (you)" : "")));
      ul.appendChild(li);
    });
  }

  // ---- notifications -------------------------------------------------------

  function windowHidden() { return document.hidden || !document.hasFocus(); }

  function updateTitleBadge() {
    var total = 0;
    Object.keys(state.unread).forEach(function (k) { total += state.unread[k]; });
    total += state.unreadTotal;
    document.title = (total > 0 ? "(" + total + ") " : "") + "ChatSphere";
  }

  function canNotify() {
    return state.notifyOn && "Notification" in window && Notification.permission === "granted";
  }

  function showNotification(title, body, tag) {
    if (!canNotify()) return;
    try {
      var n = new Notification(title, { body: body, tag: tag, icon: "/static/img/logo.svg" });
      n.onclick = function () { window.focus(); n.close(); };
      setTimeout(function () { n.close(); }, 6000);
    } catch (e) { /* some browsers only allow notifications via service workers */ }
  }

  function notifyMessage(m) {
    if (!windowHidden()) return;
    state.unreadTotal += 1;
    updateTitleBadge();
    showNotification(m.username + " in " + state.room.name, m.body, "room-" + m.room_id);
  }

  function notifyOther(room, count) {
    if (!windowHidden()) return;
    showNotification(room.name, count + " new message" + (count > 1 ? "s" : ""), "room-" + room.id);
  }

  function refreshBell() {
    var bell = $("bell-btn");
    var supported = "Notification" in window;
    var on = supported && Notification.permission === "granted" && state.notifyOn;
    bell.classList.toggle("on", on);
    bell.setAttribute("aria-pressed", on ? "true" : "false");
    bell.title = !supported ? "Notifications not supported in this browser"
      : Notification.permission === "denied" ? "Notifications are blocked in browser settings"
      : on ? "Notifications on (click to mute)" : "Turn notifications on";
  }

  function askPermission() {
    if (!("Notification" in window)) { toast("This browser doesn't support notifications.", "error"); return; }
    if (Notification.permission === "denied") {
      toast("Notifications are blocked. Allow them in your browser's site settings.", "error");
      return;
    }
    var result = Notification.requestPermission(function (p) { afterPermission(p); });
    if (result && result.then) result.then(afterPermission);
  }

  function afterPermission(p) {
    $("notify-banner").hidden = true;
    if (p === "granted") {
      state.notifyOn = true;
      safeStore("chatsphere.notify", "1");
      toast("Notifications enabled", "ok");
    }
    refreshBell();
  }

  function setupNotifications() {
    state.notifyOn = safeStore("chatsphere.notify") !== "0";
    if ("Notification" in window && Notification.permission === "default" && safeStore("chatsphere.nobanner") !== "1") {
      $("notify-banner").hidden = false;
    }
    $("notify-enable").addEventListener("click", askPermission);
    $("notify-dismiss").addEventListener("click", function () {
      $("notify-banner").hidden = true;
      safeStore("chatsphere.nobanner", "1");
    });
    $("bell-btn").addEventListener("click", function () {
      if (!("Notification" in window) || Notification.permission !== "granted") { askPermission(); return; }
      state.notifyOn = !state.notifyOn;
      safeStore("chatsphere.notify", state.notifyOn ? "1" : "0");
      toast(state.notifyOn ? "Notifications on" : "Notifications muted");
      refreshBell();
    });
    window.addEventListener("focus", function () { state.unreadTotal = 0; updateTitleBadge(); });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { state.unreadTotal = 0; updateTitleBadge(); }
    });
    refreshBell();
  }

  // ---- composer ------------------------------------------------------------

  function autoGrow() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
    var left = 1000 - input.value.length;
    $("counter").textContent = left < 200 ? String(left) : "";
  }

  function sendMessage(ev) {
    if (ev) ev.preventDefault();
    var text = input.value.trim();
    if (!text || !state.room) return;
    sendBtn.disabled = true;
    api("POST", "/api/rooms/" + state.room.id + "/messages", { text: text }).then(function (data) {
      input.value = "";
      autoGrow();
      addMessage(data.message, { silent: true });  // the stream copy is ignored as a duplicate
    }).catch(function (e) {
      toast(e.message, "error");
    }).then(function () {
      sendBtn.disabled = false;
      input.focus();
    });
  }

  function setupComposer() {
    $("composer").addEventListener("submit", sendMessage);
    input.addEventListener("input", autoGrow);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendMessage(); }
    });
    var pop = $("emoji-pop");
    $("emoji-btn").addEventListener("click", function (e) { e.stopPropagation(); pop.hidden = !pop.hidden; });
    pop.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      input.value += b.textContent;
      autoGrow();
      input.focus();
    });
    document.addEventListener("click", function (e) {
      if (!pop.hidden && !pop.contains(e.target)) pop.hidden = true;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { pop.hidden = true; closeModal(); closeRail(); }
    });
  }

  // ---- panels / modal ------------------------------------------------------

  function closeRail() { $("rail").classList.remove("open"); $("scrim").classList.remove("show"); }
  function openRail() { $("rail").classList.add("open"); $("scrim").classList.add("show"); }
  function closeModal() { $("room-modal").hidden = true; }

  function setupPanels() {
    $("open-rail").addEventListener("click", openRail);
    $("close-rail").addEventListener("click", closeRail);
    $("scrim").addEventListener("click", closeRail);

    var people = $("people");
    $("people-btn").addEventListener("click", function () {
      people.hidden = !people.hidden;
      $("people-btn").setAttribute("aria-expanded", people.hidden ? "false" : "true");
    });
    $("close-people").addEventListener("click", function () {
      people.hidden = true;
      $("people-btn").setAttribute("aria-expanded", "false");
    });

    $("new-room-btn").addEventListener("click", function () {
      $("room-error").textContent = "";
      $("room-form").reset();
      $("room-modal").hidden = false;
      $("room-name").focus();
    });
    $("room-cancel").addEventListener("click", closeModal);
    $("room-modal").addEventListener("click", function (e) { if (e.target === this) closeModal(); });
    $("room-form").addEventListener("submit", function (e) {
      e.preventDefault();
      api("POST", "/api/rooms", { name: $("room-name").value, description: $("room-description").value })
        .then(function (data) {
          closeModal();
          toast("Room created", "ok");
          return loadRooms(false).then(function (rooms) {
            var made = rooms.filter(function (r) { return r.id === data.room.id; })[0];
            if (made) openRoom(made);
          });
        })
        .catch(function (err) { $("room-error").textContent = err.message; });
    });
  }

  // ---- start ---------------------------------------------------------------

  function start() {
    $("me-avatar").replaceWith((function () { var a = avatar(ME); a.id = "me-avatar"; return a; })());
    setupComposer();
    setupPanels();
    setupNotifications();
    loadRooms(false).then(function (rooms) {
      var wanted = parseInt(safeStore("chatsphere.room"), 10);
      var pick = rooms.filter(function (r) { return r.id === wanted; })[0] || rooms[0];
      if (pick) openRoom(pick);
    }).catch(function (e) { toast(e.message, "error"); });
    setInterval(function () { loadRooms(true).catch(function () {}); }, 8000);
  }

  start();
})();
