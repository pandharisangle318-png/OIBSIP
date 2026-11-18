"""Animated, weather-dependent background (pure QPainter, no assets).

Performance notes: clouds are pre-rendered once into pixmaps, rain is drawn with
one drawLines() call, particle counts scale with window area and are capped,
and the timer is stopped while the window is minimised or effects are off.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List

from PySide6.QtCore import QElapsedTimer, QLineF, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..models import Condition
from .icons import paint_moon

C = Condition
SKY = {
    (C.CLEAR, False): ("#1c6fe0", "#4fa6f2", "#bde2ff"),
    (C.CLEAR, True): ("#050a22", "#0f1b48", "#27366f"),
    (C.PARTLY, False): ("#2873d2", "#68acea", "#c5e1f8"),
    (C.PARTLY, True): ("#070c28", "#132150", "#2c3b72"),
    (C.CLOUDS, False): ("#566679", "#8190a1", "#b3bdc9"),
    (C.CLOUDS, True): ("#151b27", "#232c3b", "#364154"),
    (C.RAIN, False): ("#2a3746", "#415364", "#697c8e"),
    (C.RAIN, True): ("#0a1018", "#15202b", "#26323e"),
    (C.SNOW, False): ("#7b90a6", "#a6bacb", "#dbe6f0"),
    (C.SNOW, True): ("#19243a", "#2c3c53", "#4c5f79"),
    (C.FOG, False): ("#88969f", "#a7b2bb", "#cdd4da"),
    (C.FOG, True): ("#20282f", "#343d46", "#4d5862"),
    (C.STORM, False): ("#141925", "#282f41", "#424c5f"),
    (C.STORM, True): ("#06080e", "#111622", "#222938"),
}
FX = ("sun", "moon", "stars", "clouds", "rain", "snow", "fog", "lightning")


def _rgb(hex_color: str) -> List[float]:
    c = QColor(hex_color)
    return [float(c.red()), float(c.green()), float(c.blue())]


def _qc(rgb: List[float]) -> QColor:
    return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))


class WeatherScene(QWidget):
    FRAME_MS = 33  # ~30 fps

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rng = random.Random(11)
        self._condition = Condition.CLEAR
        self._night = False
        self._sky = [_rgb(h) for h in SKY[(Condition.CLEAR, False)]]
        self._sky_target = [list(c) for c in self._sky]
        self._fx: Dict[str, float] = dict.fromkeys(FX, 0.0)
        self._fx_target: Dict[str, float] = dict.fromkeys(FX, 0.0)
        self._dark = 0.0
        self._dark_target = 0.0
        self._intensity = 1.0
        self._time = 0.0
        self._flash = 0.0
        self._next_flash = 4.0
        self._bolt: List[QPointF] = []
        self._rain: List[List[float]] = []
        self._snow: List[List[float]] = []
        self._stars: List[List[float]] = []
        self._clouds: List[dict] = []
        self._fog: List[dict] = []
        self._cloud_light = self._make_cloud(QColor(255, 255, 255))
        self._cloud_dark = self._make_cloud(QColor(66, 76, 94))
        self._animated = True
        self._paused = False
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(self.FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.set_weather(Condition.CLEAR, False)
        self._snap()
        self._reseed()
        self._start()

    # ------------------------------------------------------------------ API
    def set_weather(self, condition: Condition, night: bool) -> None:
        self._condition, self._night = condition, night
        self._sky_target = [_rgb(h) for h in SKY[(condition, night)]]
        t = dict.fromkeys(FX, 0.0)
        dark, self._intensity = 0.0, 1.0
        body = "moon" if night else "sun"
        if condition == Condition.CLEAR:
            t[body] = 1.0
            t["clouds"] = 0.25
            if night:
                t["stars"] = 1.0
        elif condition == Condition.PARTLY:
            t[body] = 0.85
            t["clouds"] = 0.65
            if night:
                t["stars"] = 0.6
        elif condition == Condition.CLOUDS:
            t["clouds"], dark = 1.0, 0.35
            if not night:
                t["sun"] = 0.12
        elif condition == Condition.RAIN:
            t["clouds"], t["rain"], dark = 1.0, 1.0, 0.7
        elif condition == Condition.SNOW:
            t["clouds"], t["snow"], dark = 0.8, 1.0, 0.25
        elif condition == Condition.FOG:
            t["fog"], t["clouds"], dark = 1.0, 0.3, 0.2
        elif condition == Condition.STORM:
            t["clouds"], t["rain"], t["lightning"], dark = 1.0, 1.0, 1.0, 1.0
            self._intensity = 1.5
        if night and t["clouds"] > 0:
            dark = max(dark, 0.6)
        self._fx_target, self._dark_target = t, dark
        if not self._timer.isActive():
            self._snap()
            self.update()

    def set_animated(self, enabled: bool) -> None:
        self._animated = enabled
        if enabled:
            self._start()
        else:
            self._timer.stop()
            self._snap()
            self.update()

    @property
    def animated(self) -> bool:
        return self._animated

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        if paused:
            self._timer.stop()
        else:
            self._start()

    # ------------------------------------------------------------- internals
    def _start(self) -> None:
        if self._animated and not self._paused:
            self._clock.restart()
            self._timer.start()

    def _snap(self) -> None:
        self._sky = [list(c) for c in self._sky_target]
        self._fx = dict(self._fx_target)
        self._dark = self._dark_target

    def _make_cloud(self, color: QColor) -> QPixmap:
        w, h = 420, 170
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        blobs = ((0.22, 0.62, 0.19), (0.38, 0.45, 0.24), (0.58, 0.40, 0.26), (0.76, 0.55, 0.21),
                 (0.50, 0.68, 0.26), (0.30, 0.72, 0.17), (0.68, 0.72, 0.19))
        for fx, fy, fr in blobs:
            r = fr * w
            g = QRadialGradient(QPointF(fx * w, fy * h), r)
            core, mid, edge = QColor(color), QColor(color), QColor(color)
            core.setAlpha(210)
            mid.setAlpha(120)
            edge.setAlpha(0)
            g.setColorAt(0.0, core)
            g.setColorAt(0.6, mid)
            g.setColorAt(1.0, edge)
            p.setBrush(g)
            p.drawEllipse(QPointF(fx * w, fy * h), r, r * 0.72)
        p.end()
        return pm

    def _reseed(self) -> None:
        rng = self._rng
        w, h = max(self.width(), 640), max(self.height(), 420)
        area = w * h
        self._rain = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(650, 1000), rng.uniform(12, 26)]
                      for _ in range(int(min(260, area / 5200)))]
        self._snow = [[rng.uniform(0, w), rng.uniform(0, h), rng.uniform(30, 80), rng.uniform(1.4, 3.8),
                       rng.uniform(0, 6.28)] for _ in range(int(min(170, area / 8500)))]
        self._stars = [[rng.uniform(0, w), rng.uniform(0, h * 0.62), rng.uniform(0.6, 1.7), rng.uniform(0, 6.28)]
                       for _ in range(110)]
        self._clouds = [{"x": rng.uniform(-200, w), "y": rng.uniform(0.02, 0.48) * h,
                         "w": rng.uniform(0.28, 0.55) * max(w, 700), "speed": rng.uniform(6, 22),
                         "alpha": rng.uniform(0.45, 0.9)} for _ in range(7)]
        self._fog = [{"x": rng.uniform(-w, 0), "y": (0.22 + 0.18 * i) * h, "speed": 8 + 4 * i,
                      "alpha": 0.32} for i in range(4)]

    def resizeEvent(self, event) -> None:
        self._reseed()
        super().resizeEvent(event)

    def _make_bolt(self) -> List[QPointF]:
        w, h = max(self.width(), 1), max(self.height(), 1)
        x, y = self._rng.uniform(0.15, 0.85) * w, 0.0
        pts = [QPointF(x, y)]
        while y < h * 0.55:
            y += self._rng.uniform(25, 55)
            x += self._rng.uniform(-35, 35)
            pts.append(QPointF(x, y))
        return pts

    def _tick(self) -> None:
        dt = min(self._clock.restart() / 1000.0, 0.1)
        if dt <= 0:
            return
        rng, w, h = self._rng, self.width(), self.height()
        self._time += dt
        k = 1 - math.exp(-dt * 2.2)
        for name in FX:
            self._fx[name] += (self._fx_target[name] - self._fx[name]) * k
        self._dark += (self._dark_target - self._dark) * k
        ks = 1 - math.exp(-dt * 2.8)
        for i in range(3):
            for ch in range(3):
                self._sky[i][ch] += (self._sky_target[i][ch] - self._sky[i][ch]) * ks

        if self._fx["clouds"] > 0.02:
            for c in self._clouds:
                c["x"] += c["speed"] * dt
                if c["x"] > w:
                    c["x"] = -c["w"]
        if self._fx["fog"] > 0.02:
            for b in self._fog:
                b["x"] += b["speed"] * dt
                if b["x"] > w:
                    b["x"] = -w * 1.3
        if self._fx["rain"] > 0.02:
            sp = self._intensity
            for d in self._rain:
                d[1] += d[2] * dt * sp
                d[0] += d[2] * 0.2 * dt * sp
                if d[1] > h:
                    d[1], d[0] = -d[3], rng.uniform(-0.2 * h, w)
                elif d[0] > w + 30:
                    d[0] -= w + 60
        if self._fx["snow"] > 0.02:
            for f in self._snow:
                f[1] += f[2] * dt
                f[0] += math.sin(self._time * 0.8 + f[4]) * 18 * dt
                if f[1] > h + 5:
                    f[1], f[0] = -5, rng.uniform(0, w)
        if self._fx["lightning"] > 0.5:
            self._next_flash -= dt
            if self._next_flash <= 0:
                self._flash, self._bolt = 1.0, self._make_bolt()
                self._next_flash = rng.uniform(3.5, 9.0)
        self._flash = max(0.0, self._flash - dt * 3.2)
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        sky = QLinearGradient(0, 0, 0, h)
        for stop, col in zip((0.0, 0.55, 1.0), self._sky):
            sky.setColorAt(stop, _qc(col))
        p.fillRect(self.rect(), QBrush(sky))

        self._paint_stars(p)
        self._paint_bodies(p, w, h)
        self._paint_clouds(p)
        self._paint_fog(p, w, h)
        self._paint_precip(p)
        self._paint_lightning(p, w, h)

        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(0, 0, 0, 70))
        veil.setColorAt(0.35, QColor(0, 0, 0, 0))
        veil.setColorAt(1.0, QColor(0, 0, 0, 115))
        p.fillRect(self.rect(), QBrush(veil))
        p.end()

    def _paint_stars(self, p: QPainter) -> None:
        a = self._fx["stars"]
        if a < 0.02:
            return
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, r, ph in self._stars:
            tw = 0.55 + 0.45 * math.sin(self._time * 1.5 + ph)
            p.setBrush(QColor(255, 255, 255, int(220 * a * tw)))
            p.drawEllipse(QPointF(x, y), r, r)

    def _paint_bodies(self, p: QPainter, w: int, h: int) -> None:
        a = self._fx["sun"]
        if a > 0.02:
            cx, cy = w * 0.78, h * 0.2
            big = min(w, h) * 0.55 * (1 + 0.025 * math.sin(self._time * 0.9))
            g = QRadialGradient(QPointF(cx, cy), big)
            g.setColorAt(0.0, QColor(255, 246, 214, int(230 * a)))
            g.setColorAt(0.12, QColor(255, 226, 140, int(200 * a)))
            g.setColorAt(0.4, QColor(255, 196, 100, int(70 * a)))
            g.setColorAt(1.0, QColor(255, 190, 90, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), big, big)
            core = min(w, h) * 0.055
            p.setBrush(QColor(255, 250, 232, int(255 * a)))
            p.drawEllipse(QPointF(cx, cy), core, core)
        a = self._fx["moon"]
        if a > 0.02:
            p.setOpacity(min(a, 1.0))
            paint_moon(p, w * 0.8, h * 0.18, 30)
            p.setOpacity(1.0)

    def _paint_clouds(self, p: QPainter) -> None:
        a = self._fx["clouds"]
        if a < 0.02:
            return
        src = QRectF(self._cloud_light.rect())
        for c in self._clouds:
            rect = QRectF(c["x"], c["y"], c["w"], c["w"] * 0.405)
            o = c["alpha"] * a
            p.setOpacity(max(0.0, o * (1 - self._dark)))
            p.drawPixmap(rect, self._cloud_light, src)
            if self._dark > 0.02:
                p.setOpacity(max(0.0, o * self._dark))
                p.drawPixmap(rect, self._cloud_dark, src)
        p.setOpacity(1.0)

    def _paint_fog(self, p: QPainter, w: int, h: int) -> None:
        a = self._fx["fog"]
        if a < 0.02:
            return
        src = QRectF(self._cloud_light.rect())
        dim = 0.5 if self._night else 1.0
        for b in self._fog:
            p.setOpacity(min(1.0, a * b["alpha"] * dim))
            p.drawPixmap(QRectF(b["x"], b["y"], w * 1.3, h * 0.3), self._cloud_light, src)
        p.setOpacity(1.0)

    def _paint_precip(self, p: QPainter) -> None:
        a = self._fx["rain"]
        if a > 0.02:
            pen = QPen(QColor(190, 212, 238, int(125 * a)), 1.6 if self._intensity > 1.2 else 1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLines([QLineF(x, y, x - ln * 0.2, y - ln) for x, y, _sp, ln in self._rain])
        a = self._fx["snow"]
        if a > 0.02:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(215 * a)))
            for x, y, _sp, r, _ph in self._snow:
                p.drawEllipse(QPointF(x, y), r, r)

    def _paint_lightning(self, p: QPainter, w: int, h: int) -> None:
        a = self._fx["lightning"]
        if a < 0.02 or self._flash < 0.01:
            return
        p.fillRect(self.rect(), QColor(255, 255, 255, int(95 * self._flash * a)))
        if self._flash > 0.35 and len(self._bolt) > 1:
            glow = QPen(QColor(200, 220, 255, int(70 * self._flash)), 7)
            glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(glow)
            p.drawPolyline(self._bolt)
            core = QPen(QColor(255, 255, 255, int(255 * min(1.0, self._flash))), 2)
            core.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(core)
            p.drawPolyline(self._bolt)
