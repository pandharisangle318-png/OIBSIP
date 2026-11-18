"""Colours and Qt style sheet for the VYOM dark-purple theme."""

BG = "#0b0b1e"
PANEL = "#14142e"
PANEL_ALT = "#1b1b3a"
PURPLE = "#7c4dff"
PURPLE_DARK = "#5a33d6"
MINT = "#2de2c0"
TEXT = "#e8e8f5"
MUTED = "#8c8cb0"
DANGER = "#ff5d7a"
WARN = "#ffb74d"

STATE_COLORS = {
    "standby": MUTED,
    "listening": MINT,
    "processing": WARN,
    "speaking": PURPLE,
    "error": DANGER,
}

STYLESHEET = f"""
QWidget {{ background-color: {BG}; color: {TEXT}; font-family: 'Segoe UI', 'Inter', Arial, sans-serif; font-size: 14px; }}
QLabel#brand {{ font-size: 30px; font-weight: 700; letter-spacing: 6px; color: {MINT}; }}
QLabel#tagline {{ color: {MUTED}; font-size: 12px; }}
QLabel#clock {{ font-size: 20px; font-weight: 600; }}
QLabel#date {{ color: {MUTED}; font-size: 12px; }}
QLabel#status {{ background-color: {PANEL}; border-radius: 14px; padding: 6px 16px; font-weight: 600; }}
QScrollArea {{ border: none; background-color: {PANEL}; border-radius: 16px; }}
QWidget#chatContent {{ background-color: {PANEL}; }}
QFrame#userBubble {{ background-color: {PURPLE}; border-radius: 16px; }}
QFrame#assistantBubble {{ background-color: {PANEL_ALT}; border: 1px solid {PURPLE_DARK}; border-radius: 16px; }}
QFrame#userBubble QLabel, QFrame#assistantBubble QLabel {{ background: transparent; }}
QLabel#bubbleRole {{ font-size: 11px; color: {MUTED}; background: transparent; }}
QPushButton {{ background-color: {PANEL_ALT}; border: 1px solid {PURPLE_DARK}; border-radius: 14px; padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background-color: {PURPLE_DARK}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {PANEL_ALT}; }}
QPushButton#start {{ background-color: {PURPLE}; border: none; }}
QPushButton#start:hover {{ background-color: {PURPLE_DARK}; }}
QPushButton#stop {{ border-color: {DANGER}; }}
QPushButton#stop:hover {{ background-color: {DANGER}; }}
QPushButton#quick {{ padding: 6px 12px; border-radius: 12px; border-color: {MINT}; color: {MINT}; }}
QPushButton#quick:hover {{ background-color: {MINT}; color: {BG}; }}
QLineEdit {{ background-color: {PANEL}; border: 1px solid {PURPLE_DARK}; border-radius: 14px; padding: 9px 14px; }}
QLineEdit:focus {{ border-color: {MINT}; }}
QTextEdit {{ background-color: {PANEL}; border: none; border-radius: 10px; padding: 8px; }}
QScrollBar:vertical {{ background: {PANEL}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {PURPLE_DARK}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
