"""Main application window."""
from __future__ import annotations

from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable, Optional, Tuple

from PySide6.QtCore import (QEasingCurve, QEvent, QPropertyAnimation, QStringListModel,
                            Qt, QThreadPool, QTimer)
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCompleter, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import APP_NAME
from ..api import WeatherService
from ..config import DEFAULT_ENV_PATH, Config, load_config
from ..errors import InvalidApiKeyError, MissingApiKeyError, WeatherError
from ..location import detect_location
from ..models import Condition, WeatherBundle
from ..processing import (cloud_label, daily_summary, feels_like_label, humidity_label, pressure_label,
                          six_hour_outlook, visibility_label)
from ..state import AppState, add_recent, load_state, save_state
from ..utils import (compass_direction, convert_temp, format_clock, format_coords, format_duration, format_hm,
                     format_temp, format_visibility, format_wind, local_now, minutes_of_day, sentence_case)
from ..visuals.icons import app_icon, line_icon, paint_weather_icon
from ..visuals.scene import WeatherScene
from ..workers import FetchTask, WorkerSignals
from .theme import STYLESHEET, make_font
from .widgets import (AL, Banner, DayRow, ForecastItem, GlassPanel, LoadingBar, MetricTile, ShadowLabel,
                      StatusPanel, SunArc, UnitToggle, WeatherGlyph, styled_label)
from .. import workflow

Request = Tuple  # ("city", name) | ("locate",) | ("coords", lat, lon)


class LogoMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event) -> None:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QLinearGradient, QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        g = QLinearGradient(0, 0, 36, 36)
        g.setColorAt(0.0, QColor(255, 255, 255, 70))
        g.setColorAt(1.0, QColor(255, 255, 255, 20))
        p.setBrush(g)
        p.setPen(QColor(255, 255, 255, 110))
        p.drawEllipse(QRectF(1, 1, 34, 34))
        paint_weather_icon(p, QRectF(4, 4, 28, 28), Condition.PARTLY, False)


class MainWindow(QMainWindow):
    def __init__(self, config: Config, service: Optional[WeatherService] = None,
                 state_path: Optional[Path] = None,
                 config_loader: Callable[[], Config] = load_config,
                 locator: Callable = detect_location, autoload: bool = True):
        super().__init__()
        self.config = config
        self.service = service or WeatherService(config.api_key, config.base_url, config.timeout)
        self._config_loader = config_loader
        self._locator = locator
        self._state_path = state_path
        self.state: AppState = load_state(state_path)
        self.units = self.state.units or config.default_units
        self._bundle: Optional[WeatherBundle] = None
        self._request: Optional[Request] = None
        self._token = 0
        self._busy = False
        self._anim = None
        self._pending: Request = ("locate",)
        self._status_mode = "retry"

        self.setWindowTitle(f"{APP_NAME} \u2013 Premium Edition")
        self.setWindowIcon(app_icon())
        self.resize(1280, 820)
        self.setMinimumSize(980, 660)
        self.setStyleSheet(STYLESHEET)

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._signals = WorkerSignals(self)
        self._signals.result.connect(self._on_result)
        self._signals.error.connect(self._on_error)

        self.scene = WeatherScene(self)
        self.setCentralWidget(self.scene)
        self.scene.set_animated(config.effects_enabled)
        self._build_ui()
        self.fx_btn.setChecked(self.scene.animated)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        if config.auto_refresh_minutes > 0:
            self._refresh_timer.start(config.auto_refresh_minutes * 60 * 1000)

        for seq, fn in (("F5", self.refresh), ("Ctrl+R", self.refresh),
                        ("Ctrl+L", lambda: (self.search_edit.setFocus(), self.search_edit.selectAll()))):
            QShortcut(QKeySequence(seq), self).activated.connect(fn)

        if autoload:
            QTimer.singleShot(50, self._initial_load)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self.scene)
        root.setContentsMargins(30, 0, 30, 12)
        root.setSpacing(12)

        self.loading = LoadingBar()
        root.addWidget(self.loading)
        root.addSpacing(10)

        # ---- top bar
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(LogoMark())
        brand = styled_label("WEATHERDESK", 16, QFont.Weight.DemiBold, 255, 4.0)
        badge = QLabel("PREMIUM")
        badge.setObjectName("badge")
        badge.setFont(make_font(9, QFont.Weight.DemiBold, 2.0))
        top.addWidget(brand)
        top.addWidget(badge)
        top.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search a city\u2026  e.g. Tokyo, Paris, Pune")
        self.search_edit.setMinimumWidth(300)
        self.search_edit.setMaximumWidth(380)
        self.search_edit.returnPressed.connect(self.search)
        self._recent_model = QStringListModel(self.state.recent)
        completer = QCompleter(self._recent_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_edit.setCompleter(completer)
        top.addWidget(self.search_edit)

        self.search_btn = self._button("Search", "search", self.search, "Search for this city (Enter)")
        self.locate_btn = self._button("My location", "locate", self.locate, "Detect my approximate location")
        self.refresh_btn = self._button("", "refresh", self.refresh, "Refresh now (F5)", icon_only=True)
        for b in (self.search_btn, self.locate_btn, self.refresh_btn):
            top.addWidget(b)
        self.unit_toggle = UnitToggle(self.units)
        self.unit_toggle.changed.connect(self.set_units)
        top.addWidget(self.unit_toggle)
        self.fx_btn = QPushButton("FX")
        self.fx_btn.setObjectName("fxBtn")
        self.fx_btn.setCheckable(True)
        self.fx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fx_btn.setToolTip("Animated weather effects on/off (turn off to save CPU)")
        self.fx_btn.toggled.connect(self.scene.set_animated)
        top.addWidget(self.fx_btn)
        root.addLayout(top)

        self.banner = Banner()
        root.addWidget(self.banner)

        # ---- pages
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.status = StatusPanel()
        self.status.action_clicked.connect(self._status_action)
        status_page = QWidget()
        sp = QVBoxLayout(status_page)
        sp.addStretch(1)
        sp.addWidget(self.status, 0, AL.AlignHCenter)
        sp.addStretch(2)
        self.stack.addWidget(status_page)

        self.content = QWidget()
        self._build_content(self.content)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setWidget(self.content)
        self.content.setAutoFillBackground(False)   # QScrollArea.setWidget() turns this on
        self.stack.addWidget(self.scroll)

        self.footer = styled_label("Data: OpenWeatherMap   \u00b7   Forecast uses 3-hour intervals", 11,
                                   QFont.Weight.Normal, 140, align=AL.AlignRight | AL.AlignVCenter)
        root.addWidget(self.footer)

    def _button(self, text: str, icon: str, slot, tip: str, icon_only: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setIcon(line_icon(icon))
        if icon_only:
            btn.setObjectName("iconBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tip)
        btn.clicked.connect(slot)
        return btn

    def _build_content(self, parent: QWidget) -> None:
        outer = QHBoxLayout(parent)
        outer.setContentsMargins(4, 6, 8, 6)
        outer.setSpacing(26)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(14)
        right.setSpacing(14)
        outer.addLayout(left, 11)
        outer.addLayout(right, 9)

        # ---- hero (left)
        self.city_label = ShadowLabel("")
        self.city_label.setFont(make_font(40, QFont.Weight.Light, 0, True))
        self.city_label.setMinimumHeight(56)
        self.place_label = styled_label("", 13, QFont.Weight.Normal, 175, 0.6)
        self.clock_label = styled_label("", 15, QFont.Weight.DemiBold, 225)
        left.addWidget(self.city_label)
        left.addWidget(self.place_label)
        left.addWidget(self.clock_label)
        left.addSpacing(6)

        hero = QHBoxLayout()
        hero.setSpacing(22)
        self.temp_label = ShadowLabel("--\u00b0")
        self.temp_label.setFont(make_font(150, QFont.Weight.Light, -2, True))
        self.temp_label.setMinimumWidth(300)
        hero.addWidget(self.temp_label, 0, AL.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(4)
        self.hero_glyph = WeatherGlyph(104)
        self.cond_label = styled_label("", 24, QFont.Weight.DemiBold, 255, wrap=True)
        self.feels_label = styled_label("", 15, QFont.Weight.Normal, 190)
        self.hilo_label = styled_label("", 15, QFont.Weight.Normal, 215)
        for w in (self.hero_glyph, self.cond_label, self.feels_label, self.hilo_label):
            info.addWidget(w)
        info.addStretch(1)
        hero.addLayout(info, 1)
        left.addLayout(hero)
        left.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        self.hours_panel = GlassPanel(radius=24)
        hp = QVBoxLayout(self.hours_panel)
        hp.setContentsMargins(18, 14, 18, 12)
        hp.setSpacing(4)
        hp.addWidget(styled_label("NEXT 6 HOURS", 11, QFont.Weight.DemiBold, 170, 1.4))
        hp.addWidget(styled_label("Real 3-hour forecast intervals (not hourly)", 11, QFont.Weight.Normal, 135))
        row = QHBoxLayout()
        row.setSpacing(4)
        self.hour_items = [ForecastItem() for _ in range(3)]
        for item in self.hour_items:
            row.addWidget(item, 1)
        hp.addLayout(row)
        bottom.addWidget(self.hours_panel, 5)
        self.sun_arc = SunArc()
        bottom.addWidget(self.sun_arc, 4)
        left.addLayout(bottom)

        # ---- metrics + 5-day (right)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.tiles = {name: MetricTile(name) for name in
                      ("Feels like", "Humidity", "Wind", "Pressure", "Visibility", "Cloud cover")}
        for i, tile in enumerate(self.tiles.values()):
            grid.addWidget(tile, i // 2, i % 2)
        right.addLayout(grid)

        self.days_panel = GlassPanel(radius=24)
        dp = QVBoxLayout(self.days_panel)
        dp.setContentsMargins(20, 14, 20, 14)
        dp.setSpacing(4)
        dp.addWidget(styled_label("5-DAY FORECAST", 11, QFont.Weight.DemiBold, 170, 1.4))
        dp.addWidget(styled_label("Daily range from 3-hour data", 11, QFont.Weight.Normal, 135))
        self.day_rows = [DayRow() for _ in range(5)]
        for r in self.day_rows:
            dp.addWidget(r)
        right.addWidget(self.days_panel, 1)

    # --------------------------------------------------------- loading flow
    def _initial_load(self) -> None:
        if not self.config.has_api_key:
            self._show_setup()
            return
        if self.state.last_city:
            self._start(("city", self.state.last_city))
        else:
            self._start(("locate",))

    def search(self) -> None:
        text = self.search_edit.text().strip()
        if not text:
            self.banner.show_message("Type a city name to search, e.g. \u201cTokyo\u201d or \u201cParis, FR\u201d.", "info")
            self.search_edit.setFocus()
            return
        self._start(("city", text))

    def locate(self) -> None:
        self._start(("locate",))

    def refresh(self) -> None:
        self._start(self._request or (("city", self.state.last_city) if self.state.last_city else ("locate",)))

    def _auto_refresh(self) -> None:
        if not self._busy and self._bundle is not None and self.config.has_api_key:
            self._start(self._request or ("city", self._bundle.current.city))

    def _start(self, request: Request) -> None:
        if not self.config.has_api_key:
            self._show_setup()
            return
        self.banner.clear()
        self._token += 1
        self._busy = True
        self.loading.start()
        self.refresh_btn.setEnabled(False)
        self.locate_btn.setEnabled(False)
        self.footer.setText("Fetching weather\u2026")
        if self._bundle is None:
            label = "your location" if request[0] == "locate" else str(request[1])
            self.status.show_state("Loading weather\u2026", f"Fetching live conditions for {label}.")
            self.stack.setCurrentIndex(0)
        self._pending = request
        svc = self.service
        if request[0] == "city":
            fn = partial(workflow.load_city, svc, request[1])
        elif request[0] == "coords":
            fn = partial(workflow.load_coords, svc, request[1], request[2])
        else:
            fn = partial(workflow.load_current_location, svc, self.config.default_city, self._locator)
        self._pool.start(FetchTask(self._token, self._signals, fn))

    def _finish_busy(self) -> None:
        self._busy = False
        self.loading.stop()
        self.refresh_btn.setEnabled(True)
        self.locate_btn.setEnabled(True)

    def _on_result(self, token: int, result) -> None:
        if token != self._token:
            return  # a newer request superseded this one
        self._finish_busy()
        bundle: WeatherBundle = result.bundle
        if result.located:
            self._request = ("coords", bundle.current.lat, bundle.current.lon)
        elif self._pending[0] == "locate":      # fell back to the default city
            self._request = ("city", bundle.current.city)
        else:
            self._request = self._pending
        self.show_bundle(bundle)
        if result.note:
            self.banner.show_message(result.note, "info", 12000)

        c = bundle.current
        self.state.last_city = f"{c.city},{c.country}" if c.country else c.city
        self.state.recent = add_recent(self.state.recent, c.city)
        self.state.units = self.units
        self._recent_model.setStringList(self.state.recent)
        save_state(self.state, self._state_path)

    def _on_error(self, token: int, exc: Exception) -> None:
        if token != self._token:
            return
        self._finish_busy()
        self._show_error(exc)
        if self._bundle is not None:
            self.footer.setText(self._footer_text())

    def _show_error(self, exc: Exception) -> None:
        if isinstance(exc, MissingApiKeyError):
            self._show_setup()
            return
        if isinstance(exc, WeatherError):
            title, message = exc.title, exc.message
        else:
            title, message = "Unexpected error", f"Something unexpected happened ({type(exc).__name__}). Please try again."
        if self._bundle is not None:
            self.banner.show_message(message, "error", 12000)
        else:
            self._status_mode = "retry"
            self.status.show_state(title, message, Condition.FOG,
                                   "Reload .env" if isinstance(exc, InvalidApiKeyError) else "Try again")
            self.stack.setCurrentIndex(0)
            self.scene.set_weather(Condition.FOG, False)

    def _show_setup(self) -> None:
        self._status_mode = "setup"
        self.status.show_state(
            "Add your OpenWeatherMap API key",
            "WeatherDesk needs a free API key to load live weather.\n\n"
            "1.  Create a free account at openweathermap.org and copy your key (My API keys).\n"
            f"2.  Copy .env.example to .env and set OPENWEATHER_API_KEY=your_key\n"
            f"     (expected at: {DEFAULT_ENV_PATH})\n"
            "3.  Click \u201cReload .env\u201d below.\n\n"
            "New keys can take up to a couple of hours to activate.",
            Condition.PARTLY, "Reload .env")
        self.stack.setCurrentIndex(0)
        self.scene.set_weather(Condition.PARTLY, False)
        self.footer.setText("Waiting for API key")

    def _status_action(self) -> None:
        mode = self._status_mode
        if mode == "setup" or self.status.action.text() == "Reload .env":
            self.config = self._config_loader()
            self.service = WeatherService(self.config.api_key, self.config.base_url, self.config.timeout)
            if not self.config.has_api_key:
                self._show_setup()
                self.banner.show_message("Still no valid OPENWEATHER_API_KEY found in your .env file.", "error")
                return
            self._initial_load()
        else:
            self.refresh()

    # ----------------------------------------------------------- rendering
    def show_bundle(self, bundle: WeatherBundle) -> None:
        """Display a bundle (also used directly by tests)."""
        self._bundle = bundle
        self._render()
        self.stack.setCurrentIndex(1)
        self.scene.set_weather(bundle.current.condition, bundle.current.is_night)
        self.footer.setText(self._footer_text())
        if self.scene.animated:
            self._fade_in()

    def _footer_text(self) -> str:
        stamp = self._bundle.fetched_at.strftime("%H:%M") if self._bundle else "--:--"
        return f"Data: OpenWeatherMap   \u00b7   Forecast uses 3-hour intervals   \u00b7   Updated {stamp}"

    def set_units(self, units: str) -> None:
        self.units = units if units in ("C", "F") else "C"
        self.unit_toggle.set_units(self.units)
        self.state.units = self.units
        save_state(self.state, self._state_path)
        self._render()

    def _render(self) -> None:
        if self._bundle is None:
            return
        b, u = self._bundle, self.units
        c = b.current
        days = daily_summary(b.forecast, 5)

        self.city_label.setText(c.city)
        self.place_label.setText(f"{c.country}   \u00b7   {format_coords(c.lat, c.lon)}" if c.country
                                 else format_coords(c.lat, c.lon))
        self.temp_label.setText(format_temp(c.temp_c, u))
        self.hero_glyph.set_condition(c.condition, c.is_night)
        self.cond_label.setText(sentence_case(c.description))
        self.feels_label.setText(f"Feels like {format_temp(c.feels_like_c, u)}")
        if days:
            hi = max(days[0].temp_max_c, c.temp_c)
            lo = min(days[0].temp_min_c, c.temp_c)
            self.hilo_label.setText(f"H {format_temp(hi, u)}    L {format_temp(lo, u)}")
        self.tick_time_widgets()

        t = self.tiles
        t["Feels like"].set_content(format_temp(c.feels_like_c, u), feels_like_label(c.temp_c, c.feels_like_c))
        t["Humidity"].set_content(f"{c.humidity}%", humidity_label(c.humidity), c.humidity / 100)
        direction = compass_direction(c.wind_deg)
        t["Wind"].set_content(format_wind(c.wind_ms, u), f"From {direction}" if direction and c.wind_ms >= 0.5 else "Calm",
                              c.wind_ms / 20.0)
        t["Pressure"].set_content(f"{c.pressure_hpa} hPa", pressure_label(c.pressure_hpa),
                                  (c.pressure_hpa - 960) / 100.0)
        vis = c.visibility_m
        t["Visibility"].set_content(format_visibility(vis, u), visibility_label(vis),
                                    None if vis is None else vis / 10000.0)
        t["Cloud cover"].set_content(f"{c.cloudiness}%", cloud_label(c.cloudiness), c.cloudiness / 100.0)

        now_local = local_now(c.utc_offset)
        outlook = six_hour_outlook(b.forecast, now_local)[:3]
        for i, item in enumerate(self.hour_items):
            if i < len(outlook):
                e = outlook[i]
                pct = int(round(e.pop * 100))
                item.set_data(format_hm(e.time), e.condition, e.is_night, format_temp(e.temp_c, u),
                              f"{pct}% precip." if pct >= 10 else "")
                item.show()
            else:
                item.hide()

        g_lo = min((convert_temp(d.temp_min_c, u) for d in days), default=0.0)
        g_hi = max((convert_temp(d.temp_max_c, u) for d in days), default=1.0)
        for i, row in enumerate(self.day_rows):
            if i < len(days):
                d = days[i]
                label = "Today" if d.day == now_local.date() else f"{d.day:%a}"
                row.set_data(label, d.condition, sentence_case(d.description), format_temp(d.temp_min_c, u),
                             format_temp(d.temp_max_c, u), convert_temp(d.temp_min_c, u),
                             convert_temp(d.temp_max_c, u), g_lo, g_hi)
                row.show()
            else:
                row.hide()

    def tick_time_widgets(self) -> None:
        if self._bundle is None:
            return
        c = self._bundle.current
        now = local_now(c.utc_offset)
        self.clock_label.setText(format_clock(now))
        sr, ss = minutes_of_day(c.sunrise), minutes_of_day(c.sunset)
        self.sun_arc.set_data(sr, ss, minutes_of_day(now), format_hm(c.sunrise), format_hm(c.sunset),
                              format_duration(ss - sr if ss > sr else 0))

    def _tick_clock(self) -> None:
        self.tick_time_widgets()

    def _fade_in(self) -> None:
        effect = QGraphicsOpacityEffect(self.content)
        self.content.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(450)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: QTimer.singleShot(0, lambda: self.content.setGraphicsEffect(None)))
        self._anim = anim
        anim.start()

    # ---------------------------------------------------------------- events
    def resizeEvent(self, event) -> None:
        px = max(90, min(170, int(self.height() * 0.19)))
        font = self.temp_label.font()
        font.setPixelSize(px)
        self.temp_label.setFont(font)
        self.temp_label.setMinimumWidth(int(px * 2.1))
        super().resizeEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            self.scene.set_paused(self.isMinimized())
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        self._clock_timer.stop()
        self._refresh_timer.stop()
        self.loading.stop()
        self._token += 1                      # ignore anything still in flight
        self._pool.waitForDone(2000)
        super().closeEvent(event)
