"""Fonts and the global stylesheet. Colours use 0-255 alpha (Qt stylesheet safe)."""
from __future__ import annotations

from PySide6.QtGui import QFont

UI_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]
DISPLAY_FAMILIES = ["Segoe UI Variable Display", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]


def make_font(px: int, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0.0,
              display: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(DISPLAY_FAMILIES if display else UI_FAMILIES)
    font.setPixelSize(int(px))
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def text_color(alpha: int = 255) -> str:
    return f"color: rgba(255, 255, 255, {alpha});"


# NOTE: no font-size / font-family rules for widgets whose fonts are set in code
# (stylesheet font rules would silently override QFont).
STYLESHEET = """
QWidget { color: rgb(244, 248, 255); }
QLabel { background: transparent; }
QToolTip { background: rgb(18, 26, 44); color: white; border: 1px solid rgba(255,255,255,70);
           padding: 5px 8px; border-radius: 6px; }

QLineEdit { background: rgba(255,255,255,36); border: 1px solid rgba(255,255,255,70);
            border-radius: 20px; padding: 9px 18px; font-size: 14px;
            selection-background-color: rgba(255,255,255,90); }
QLineEdit:hover { background: rgba(255,255,255,46); }
QLineEdit:focus { border: 1px solid rgba(255,255,255,190); background: rgba(255,255,255,56); }

QPushButton { background: rgba(255,255,255,36); border: 1px solid rgba(255,255,255,64);
              border-radius: 20px; padding: 9px 18px; font-size: 13px; font-weight: 600; }
QPushButton:hover { background: rgba(255,255,255,70); border-color: rgba(255,255,255,150); }
QPushButton:pressed { background: rgba(255,255,255,24); }
QPushButton:disabled { color: rgba(255,255,255,110); background: rgba(255,255,255,18); }
QPushButton:focus { border-color: rgba(255,255,255,170); }

QPushButton#iconBtn { padding: 9px 12px; }
QPushButton#fxBtn { padding: 9px 14px; font-size: 12px; }
QPushButton#fxBtn:checked { background: rgba(255,255,255,92); border-color: rgba(255,255,255,170); }

QPushButton#segLeft, QPushButton#segRight { padding: 9px 16px; min-width: 22px; }
QPushButton#segLeft { border-top-right-radius: 0px; border-bottom-right-radius: 0px; }
QPushButton#segRight { border-top-left-radius: 0px; border-bottom-left-radius: 0px; border-left: none; }
QPushButton#segLeft:checked, QPushButton#segRight:checked
    { background: rgba(255,255,255,120); border-color: rgba(255,255,255,190); }

QPushButton#pill { padding: 10px 22px; background: rgba(255,255,255,70); border-color: rgba(255,255,255,140); }
QPushButton#pill:hover { background: rgba(255,255,255,110); }

QFrame#banner { border-radius: 17px; }
QPushButton#bannerClose { background: transparent; border: none; padding: 2px 8px; font-size: 16px; }
QPushButton#bannerClose:hover { background: rgba(255,255,255,50); }

QLabel#badge { border: 1px solid rgba(255,255,255,110); border-radius: 9px; padding: 1px 8px;
               color: rgba(255,255,255,200); }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,70); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,120); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QListView { background: rgb(20, 30, 50); color: white; border: 1px solid rgba(255,255,255,70);
            padding: 4px; outline: 0; font-size: 13px; }
QListView::item { padding: 7px 12px; border-radius: 6px; }
QListView::item:selected, QListView::item:hover { background: rgba(255,255,255,40); }
"""
