"""Hand-painted vector weather icons and UI line icons (no image assets needed)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QRadialGradient)

from ..models import Condition


def paint_sun(p: QPainter, cx: float, cy: float, r: float) -> None:
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    glow = QRadialGradient(QPointF(cx, cy), r * 2.1)
    glow.setColorAt(0.0, QColor(255, 210, 90, 120))
    glow.setColorAt(1.0, QColor(255, 210, 90, 0))
    p.setBrush(glow)
    p.drawEllipse(QPointF(cx, cy), r * 2.1, r * 2.1)
    pen = QPen(QColor(255, 214, 96), max(1.5, r * 0.16))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for i in range(8):
        a = math.radians(i * 45)
        p.drawLine(QPointF(cx + math.cos(a) * r * 1.38, cy + math.sin(a) * r * 1.38),
                   QPointF(cx + math.cos(a) * r * 1.78, cy + math.sin(a) * r * 1.78))
    disc = QRadialGradient(QPointF(cx - r * 0.25, cy - r * 0.3), r * 1.2)
    disc.setColorAt(0.0, QColor(255, 244, 170))
    disc.setColorAt(1.0, QColor(255, 176, 48))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(disc)
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.restore()


def paint_moon(p: QPainter, cx: float, cy: float, r: float) -> None:
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    glow = QRadialGradient(QPointF(cx, cy), r * 2.2)
    glow.setColorAt(0.0, QColor(190, 210, 255, 90))
    glow.setColorAt(1.0, QColor(190, 210, 255, 0))
    p.setBrush(glow)
    p.drawEllipse(QPointF(cx, cy), r * 2.2, r * 2.2)
    disc = QPainterPath()
    disc.addEllipse(QPointF(cx, cy), r, r)
    cut = QPainterPath()
    cut.addEllipse(QPointF(cx + r * 0.52, cy - r * 0.26), r * 0.88, r * 0.88)
    p.setBrush(QColor(244, 246, 255))
    p.drawPath(disc.subtracted(cut))
    p.restore()


def _cloud_path(cx: float, cy: float, w: float) -> QPainterPath:
    h = w * 0.6
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    path.addEllipse(QPointF(cx - w * 0.22, cy + h * 0.08), w * 0.22, w * 0.22)
    path.addEllipse(QPointF(cx + w * 0.02, cy - h * 0.08), w * 0.28, w * 0.28)
    path.addEllipse(QPointF(cx + w * 0.26, cy + h * 0.10), w * 0.20, w * 0.20)
    path.addRoundedRect(QRectF(cx - w * 0.42, cy + h * 0.10, w * 0.86, h * 0.30), h * 0.15, h * 0.15)
    return path


def paint_cloud(p: QPainter, cx: float, cy: float, w: float, dark: bool = False) -> None:
    p.save()
    path = _cloud_path(cx, cy, w)
    grad = QLinearGradient(QPointF(cx, cy - w * 0.35), QPointF(cx, cy + w * 0.3))
    if dark:
        grad.setColorAt(0.0, QColor(196, 206, 222))
        grad.setColorAt(1.0, QColor(122, 136, 158))
    else:
        grad.setColorAt(0.0, QColor(255, 255, 255))
        grad.setColorAt(1.0, QColor(206, 218, 234))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPath(path)
    p.restore()


def paint_weather_icon(p: QPainter, rect: QRectF, condition: Condition, night: bool) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = min(rect.width(), rect.height())
    cx, cy = rect.center().x(), rect.center().y()
    body = paint_moon if night else paint_sun

    if condition == Condition.CLEAR:
        body(p, cx, cy, s * 0.26)
    elif condition == Condition.PARTLY:
        body(p, cx - s * 0.14, cy - s * 0.16, s * 0.19)
        paint_cloud(p, cx + s * 0.05, cy + s * 0.12, s * 0.74)
    elif condition == Condition.CLOUDS:
        paint_cloud(p, cx - s * 0.14, cy - s * 0.12, s * 0.52, dark=True)
        paint_cloud(p, cx + s * 0.04, cy + s * 0.08, s * 0.76)
    elif condition == Condition.RAIN:
        paint_cloud(p, cx, cy - s * 0.12, s * 0.78, dark=True)
        pen = QPen(QColor(120, 182, 255), max(1.5, s * 0.05))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for i in (-1, 0, 1):
            x = cx + i * s * 0.2
            p.drawLine(QPointF(x + s * 0.03, cy + s * 0.2), QPointF(x - s * 0.04, cy + s * 0.36))
    elif condition == Condition.SNOW:
        paint_cloud(p, cx, cy - s * 0.12, s * 0.78, dark=True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))
        for i, dy in ((-1, 0.0), (0, 0.07), (1, 0.0)):
            p.drawEllipse(QPointF(cx + i * s * 0.2, cy + s * 0.26 + dy * s), s * 0.04, s * 0.04)
    elif condition == Condition.STORM:
        paint_cloud(p, cx, cy - s * 0.14, s * 0.8, dark=True)
        bolt = QPolygonF([QPointF(cx + s * 0.04, cy + s * 0.08), QPointF(cx - s * 0.1, cy + s * 0.3),
                          QPointF(cx, cy + s * 0.3), QPointF(cx - s * 0.06, cy + s * 0.46),
                          QPointF(cx + s * 0.14, cy + s * 0.22), QPointF(cx + s * 0.04, cy + s * 0.22)])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 214, 64))
        p.drawPolygon(bolt)
    else:  # FOG
        paint_cloud(p, cx, cy - s * 0.16, s * 0.74)
        pen = QPen(QColor(226, 233, 242, 230), max(1.5, s * 0.05))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        for dy, half in ((0.16, 0.30), (0.27, 0.22), (0.38, 0.28)):
            p.drawLine(QPointF(cx - s * half, cy + s * dy), QPointF(cx + s * half, cy + s * dy))
    p.restore()


def line_icon(kind: str, size: int = 20) -> QIcon:
    """Crisp white line icons: 'search', 'locate', 'refresh'."""
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(255, 255, 255), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    s = float(size)
    if kind == "search":
        p.drawEllipse(QPointF(s * 0.43, s * 0.43), s * 0.27, s * 0.27)
        p.drawLine(QPointF(s * 0.63, s * 0.63), QPointF(s * 0.86, s * 0.86))
    elif kind == "locate":
        c = QPointF(s / 2, s / 2)
        p.drawEllipse(c, s * 0.27, s * 0.27)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(c, s * 0.08, s * 0.08)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            p.drawLine(QPointF(c.x() + dx * s * 0.34, c.y() + dy * s * 0.34),
                       QPointF(c.x() + dx * s * 0.46, c.y() + dy * s * 0.46))
    elif kind == "refresh":
        rect = QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64)
        p.drawArc(rect, 40 * 16, 280 * 16)
        p.drawLine(QPointF(s * 0.80, s * 0.16), QPointF(s * 0.80, s * 0.38))
        p.drawLine(QPointF(s * 0.80, s * 0.38), QPointF(s * 0.58, s * 0.34))
    p.end()
    return QIcon(pm)


def app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    g = QLinearGradient(0, 0, 256, 256)
    g.setColorAt(0.0, QColor(46, 120, 230))
    g.setColorAt(1.0, QColor(20, 40, 110))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 56, 56)
    paint_weather_icon(p, QRectF(34, 34, 188, 188), Condition.PARTLY, False)
    p.end()
    return QIcon(pm)
