"""Reusable custom-painted widgets: glass panels, tiles, sun arc, forecast rows..."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient, QTextOption)
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget)

from ..models import Condition
from ..visuals.icons import paint_weather_icon
from .theme import make_font, text_color

AL = Qt.AlignmentFlag


def draw_text(p: QPainter, rect, text: str, align: Qt.AlignmentFlag) -> None:
    option = QTextOption(align)
    option.setWrapMode(QTextOption.WrapMode.NoWrap)
    p.drawText(QRectF(rect), text, option)


def styled_label(text: str = "", px: int = 13, weight: QFont.Weight = QFont.Weight.Normal, alpha: int = 255,
                 spacing: float = 0.0, align: Qt.AlignmentFlag = AL.AlignLeft | AL.AlignVCenter,
                 wrap: bool = False, display: bool = False) -> QLabel:
    label = QLabel(text)
    label.setFont(make_font(px, weight, spacing, display))
    label.setStyleSheet(text_color(alpha))
    label.setAlignment(align)
    label.setWordWrap(wrap)
    return label


class ShadowLabel(QLabel):
    """Large display text with a soft drop shadow, painted without graphics effects
    (graphics effects are expensive on top of an animated background)."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._color = QColor(255, 255, 255)

    def set_text_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setFont(self.font())
        rect = QRectF(self.contentsRect())
        align = self.alignment()
        for dx, dy, alpha in ((0, 4, 40), (0, 2, 70)):
            p.setPen(QColor(0, 10, 30, alpha))
            draw_text(p, rect.translated(dx, dy), self.text(), align)
        p.setPen(self._color)
        draw_text(p, rect, self.text(), align)


class GlassPanel(QFrame):
    """Translucent rounded panel with a soft highlight and hairline border."""

    def __init__(self, radius: int = 24, hoverable: bool = False, parent=None):
        super().__init__(parent)
        self._radius = radius
        self._hoverable = hoverable
        self._hover = False

    def enterEvent(self, event) -> None:
        if self._hoverable:
            self._hover = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hoverable:
            self._hover = False
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        base = 40 if self._hover else 28
        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        fill.setColorAt(0.0, QColor(255, 255, 255, base + 16))
        fill.setColorAt(1.0, QColor(255, 255, 255, max(6, base - 14)))
        p.setBrush(fill)
        border = QLinearGradient(r.topLeft(), r.bottomRight())
        border.setColorAt(0.0, QColor(255, 255, 255, 120))
        border.setColorAt(1.0, QColor(255, 255, 255, 30))
        p.setPen(QPen(QBrush(border), 1.1))
        p.drawRoundedRect(r, self._radius, self._radius)
        shine = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + r.height() * 0.45))
        shine.setColorAt(0.0, QColor(255, 255, 255, 26))
        shine.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shine)
        p.drawRoundedRect(r, self._radius, self._radius)


class WeatherGlyph(QWidget):
    def __init__(self, size: int = 64, parent=None):
        super().__init__(parent)
        self._condition, self._night = Condition.CLEAR, False
        self.setFixedSize(size, size)

    def set_condition(self, condition: Condition, night: bool = False) -> None:
        self._condition, self._night = condition, night
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        paint_weather_icon(p, QRectF(self.rect()), self._condition, self._night)


class MetricTile(GlassPanel):
    def __init__(self, title: str, parent=None):
        super().__init__(radius=20, hoverable=True, parent=parent)
        self._fraction: Optional[float] = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 13, 18, 20)
        lay.setSpacing(1)
        self.title = styled_label(title.upper(), 11, QFont.Weight.DemiBold, 170, 1.4)
        self.value = styled_label("--", 25, QFont.Weight.Light, 255, display=True)
        self.sub = styled_label("", 12, QFont.Weight.Normal, 160)
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)
        self.setMinimumHeight(98)

    def set_content(self, value: str, sub: str, fraction: Optional[float] = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self._fraction = None if fraction is None else min(max(fraction, 0.0), 1.0)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._fraction is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x0, x1, y = 18.0, self.width() - 18.0, self.height() - 12.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawRoundedRect(QRectF(x0, y, x1 - x0, 3.5), 1.75, 1.75)
        fill = QLinearGradient(x0, 0, x1, 0)
        fill.setColorAt(0.0, QColor(150, 210, 255, 230))
        fill.setColorAt(1.0, QColor(255, 255, 255, 240))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(x0, y, max(3.5, (x1 - x0) * self._fraction), 3.5), 1.75, 1.75)


class SunArc(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(radius=22, parent=parent)
        self._data = None
        self.setMinimumSize(250, 170)

    def set_data(self, sunrise_min: float, sunset_min: float, now_min: float,
                 sunrise_text: str, sunset_text: str, daylight_text: str) -> None:
        self._data = (sunrise_min, sunset_min, now_min, sunrise_text, sunset_text, daylight_text)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        w, h = float(self.width()), float(self.height())
        p.setFont(make_font(11, QFont.Weight.DemiBold, 1.4))
        p.setPen(QColor(255, 255, 255, 170))
        draw_text(p, QRectF(20, 13, w - 40, 16), "SUN & DAYLIGHT", AL.AlignLeft | AL.AlignVCenter)
        if not self._data:
            return
        sr, ss, now, sr_text, ss_text, daylight = self._data
        base_y = h - 46
        radius = max(24.0, min((w - 110) / 2, base_y - 52))
        cx = w / 2
        arc_rect = QRectF(cx - radius, base_y - radius, radius * 2, radius * 2)

        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.drawLine(QPointF(cx - radius - 16, base_y), QPointF(cx + radius + 16, base_y))
        dash = QPen(QColor(255, 255, 255, 95), 2, Qt.PenStyle.DashLine)
        p.setPen(dash)
        p.drawArc(arc_rect, 0, 180 * 16)

        is_day = sr <= now <= ss and ss > sr
        if is_day:
            t = (now - sr) / (ss - sr)
            ang = 180.0 * (1.0 - t)
            done = QPen(QColor(255, 214, 110, 235), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(done)
            p.drawArc(arc_rect, int(ang * 16), int((180.0 - ang) * 16))
            sx = cx + radius * math.cos(math.radians(ang))
            sy = base_y - radius * math.sin(math.radians(ang))
            glow = QRadialGradient(QPointF(sx, sy), 22)
            glow.setColorAt(0.0, QColor(255, 220, 120, 170))
            glow.setColorAt(1.0, QColor(255, 220, 120, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(sx, sy), 22, 22)
            p.setBrush(QColor(255, 240, 180))
            p.drawEllipse(QPointF(sx, sy), 6.5, 6.5)
            centre = daylight + " of daylight"
        else:
            centre = "The sun is down"
        p.setFont(make_font(12, QFont.Weight.Normal))
        p.setPen(QColor(255, 255, 255, 190))
        draw_text(p, QRectF(cx - radius * 0.8, base_y - radius * 0.42, radius * 1.6, 18), centre, AL.AlignCenter)

        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.setPen(QColor(255, 255, 255, 235))
        draw_text(p, QRectF(cx - radius - 34, base_y + 6, 68, 20), sr_text, AL.AlignCenter)
        draw_text(p, QRectF(cx + radius - 34, base_y + 6, 68, 20), ss_text, AL.AlignCenter)
        p.setFont(make_font(11, QFont.Weight.Normal))
        p.setPen(QColor(255, 255, 255, 150))
        draw_text(p, QRectF(cx - radius - 34, base_y + 25, 68, 16), "Sunrise", AL.AlignCenter)
        draw_text(p, QRectF(cx + radius - 34, base_y + 25, 68, 16), "Sunset", AL.AlignCenter)


class ForecastItem(QWidget):
    """One 3-hour forecast point."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)
        center = AL.AlignHCenter | AL.AlignVCenter
        self.time = styled_label("", 13, QFont.Weight.DemiBold, 200, align=center)
        self.glyph = WeatherGlyph(54)
        self.temp = styled_label("", 22, QFont.Weight.Light, 255, align=center, display=True)
        self.pop = styled_label("", 11, QFont.Weight.Normal, 150, align=center)
        lay.addWidget(self.time)
        lay.addWidget(self.glyph, 0, AL.AlignHCenter)
        lay.addWidget(self.temp)
        lay.addWidget(self.pop)

    def set_data(self, time_text: str, condition: Condition, night: bool, temp_text: str, pop_text: str) -> None:
        self.time.setText(time_text)
        self.glyph.set_condition(condition, night)
        self.temp.setText(temp_text)
        self.pop.setText(pop_text)


class RangeBar(QWidget):
    """Capsule showing a day's min..max inside the week's overall range."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vals = (0.0, 1.0, 0.0, 1.0)
        self.setMinimumWidth(80)
        self.setFixedHeight(18)

    def set_range(self, lo: float, hi: float, g_lo: float, g_hi: float) -> None:
        self._vals = (lo, hi, g_lo, g_hi)
        self.update()

    def paintEvent(self, event) -> None:
        lo, hi, g_lo, g_hi = self._vals
        span = max(g_hi - g_lo, 0.001)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, cy = float(self.width()), self.height() / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 42))
        p.drawRoundedRect(QRectF(0, cy - 2.5, w, 5), 2.5, 2.5)
        x0 = (lo - g_lo) / span * w
        x1 = max((hi - g_lo) / span * w, x0 + 6)
        grad = QLinearGradient(x0, 0, x1, 0)
        grad.setColorAt(0.0, QColor(120, 200, 255))
        grad.setColorAt(1.0, QColor(255, 190, 90))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(x0, cy - 3, x1 - x0, 6), 3, 3)


class DayRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)
        self.day = styled_label("", 14, QFont.Weight.DemiBold, 235)
        self.day.setFixedWidth(52)
        self.glyph = WeatherGlyph(36)
        self.desc = styled_label("", 12, QFont.Weight.Normal, 165)
        self.desc.setMinimumWidth(80)
        self.lo = styled_label("", 14, QFont.Weight.Normal, 175, align=AL.AlignRight | AL.AlignVCenter)
        self.lo.setFixedWidth(38)
        self.bar = RangeBar()
        self.hi = styled_label("", 14, QFont.Weight.DemiBold, 245)
        self.hi.setFixedWidth(38)
        for widget, stretch in ((self.day, 0), (self.glyph, 0), (self.desc, 2), (self.lo, 0), (self.bar, 3), (self.hi, 0)):
            lay.addWidget(widget, stretch)

    def set_data(self, day: str, condition: Condition, desc: str, lo_text: str, hi_text: str,
                 lo: float, hi: float, g_lo: float, g_hi: float) -> None:
        self.day.setText(day)
        self.glyph.set_condition(condition, False)
        self.desc.setText(desc)
        self.lo.setText(lo_text)
        self.hi.setText(hi_text)
        self.bar.set_range(lo, hi, g_lo, g_hi)


class LoadingBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._active = False
        self._pos = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step)

    def start(self) -> None:
        self._active = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        self.update()

    @property
    def active(self) -> bool:
        return self._active

    def _step(self) -> None:
        self._pos = (self._pos + 0.013) % 1.5
        self.update()

    def paintEvent(self, event) -> None:
        if not self._active:
            return
        p = QPainter(self)
        w = float(self.width())
        x = (self._pos - 0.35) * w
        grad = QLinearGradient(x, 0, x + 0.35 * w, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 235))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, w, 3), QBrush(grad))


class Banner(QFrame):
    """Dismissable message pill (errors / notes) that auto-hides."""

    STYLES = {"error": "rgba(196, 52, 66, 190)", "info": "rgba(36, 96, 170, 185)"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 8, 8)
        self.label = styled_label("", 13, QFont.Weight.Normal, 255, wrap=True)
        self.close_btn = QPushButton("\u00d7")
        self.close_btn.setObjectName("bannerClose")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.clear)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.close_btn)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)
        self.hide()

    def show_message(self, text: str, kind: str = "error", timeout_ms: int = 9000) -> None:
        bg = self.STYLES.get(kind, self.STYLES["info"])
        self.setStyleSheet(f"QFrame#banner {{ background: {bg}; border: 1px solid rgba(255,255,255,90); "
                           f"border-radius: 17px; }}")
        self.label.setText(text)
        self.show()
        self._timer.start(timeout_ms)

    def clear(self) -> None:
        self._timer.stop()
        self.hide()


class UnitToggle(QWidget):
    changed = Signal(str)

    def __init__(self, units: str = "C", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.c_btn, self.f_btn = QPushButton("\u00b0C"), QPushButton("\u00b0F")
        self.c_btn.setObjectName("segLeft")
        self.f_btn.setObjectName("segRight")
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for btn, code in ((self.c_btn, "C"), (self.f_btn, "F")):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Show temperatures in Celsius" if code == "C" else "Show temperatures in Fahrenheit")
            self._group.addButton(btn)
            lay.addWidget(btn)
            btn.clicked.connect(lambda _checked=False, c=code: self.changed.emit(c))
        self.set_units(units)

    def set_units(self, units: str) -> None:
        (self.f_btn if units == "F" else self.c_btn).setChecked(True)


class StatusPanel(GlassPanel):
    """Centred message card used for loading, setup help and fatal errors."""

    action_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(radius=30, parent=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(44, 34, 44, 34)
        lay.setSpacing(10)
        center = AL.AlignHCenter | AL.AlignVCenter
        self.glyph = WeatherGlyph(96)
        self.title = styled_label("", 26, QFont.Weight.Light, 255, align=center, wrap=True, display=True)
        self.message = styled_label("", 14, QFont.Weight.Normal, 200, align=center, wrap=True)
        self.action = QPushButton("")
        self.action.setObjectName("pill")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self.action_clicked)
        lay.addWidget(self.glyph, 0, AL.AlignHCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.message)
        lay.addSpacing(6)
        lay.addWidget(self.action, 0, AL.AlignHCenter)
        self.setMaximumWidth(620)

    def show_state(self, title: str, message: str, condition: Condition = Condition.PARTLY,
                   action_text: Optional[str] = None) -> None:
        self.glyph.set_condition(condition, False)
        self.title.setText(title)
        self.message.setText(message)
        self.action.setText(action_text or "")
        self.action.setVisible(bool(action_text))
