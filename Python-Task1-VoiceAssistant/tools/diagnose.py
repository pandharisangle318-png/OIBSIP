"""VYOM environment diagnostics (run through diagnose.bat)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PACKAGES = [("PySide6", "PySide6"), ("speech_recognition", "SpeechRecognition"), ("pyaudio", "PyAudio"),
            ("pyttsx3", "pyttsx3"), ("requests", "requests"), ("dotenv", "python-dotenv")]
FILES = ["main.py", "requirements.txt", "config.json", ".env.example", "data/knowledge_base.json",
         "data/custom_commands.json", "core/assistant.py", "gui/main_window.py"]

problems = 0


def report(ok: bool, text: str, hint: str = "") -> None:
    global problems
    print(f"  [{'OK' if ok else 'FAIL'}] {text}")
    if not ok:
        problems += 1
        if hint:
            print(f"         -> {hint}")


print("VYOM diagnostics")
print("=" * 40)
v = sys.version_info
print("Python / environment")
report((3, 10) <= v[:2] <= (3, 13), f"Python {v.major}.{v.minor}.{v.micro} (3.12 recommended)", "Install Python 3.12 from python.org")
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
report(in_venv, "Running inside a virtual environment", "Run setup.bat, then use run.bat")

print("Packages")
for module, pip_name in PACKAGES:
    try:
        importlib.import_module(module)
        report(True, pip_name)
    except Exception as exc:
        hint = "pip install PyAudio==0.2.14 (needs a Python 3.12 wheel)" if pip_name == "PyAudio" else f"pip install -r requirements.txt ({exc})"
        report(False, f"{pip_name} could not be imported", hint)

print("Project files")
for rel in FILES:
    report((ROOT / rel).is_file(), rel, "File is missing - re-extract the ZIP")

print("Configuration")
from core.config import Config  # noqa: E402

cfg = Config()
print(f"  [{'OK' if cfg.env_file.exists() else 'NOTE'}] .env file {'found' if cfg.env_file.exists() else 'missing (run setup.bat, or copy .env.example to .env)'}")
print(f"  [{'OK' if cfg.email_configured else 'NOTE'}] Email credentials {'configured' if cfg.email_configured else 'not configured - email feature disabled'}")
print(f"  [{'OK' if cfg.weather_configured else 'NOTE'}] Weather key {'configured' if cfg.weather_configured else 'not configured - weather feature disabled'}")
for note in cfg.problems:
    print(f"  [NOTE] {note}")

print("Microphone")
try:
    from core.listener import Listener, ListenStatus

    result = Listener(cfg.get("speech", {})).check_microphone()
    ok = result.status is ListenStatus.RECOGNIZED
    report(ok, result.text if ok else f"Microphone not usable: {result.detail}",
           "Check Windows Settings > Privacy > Microphone, and that a recording device is enabled")
except Exception as exc:
    report(False, f"Microphone check failed: {exc}")

print("=" * 40)
print("All checks passed." if problems == 0 else f"{problems} problem(s) found. Fix the items marked FAIL above.")
sys.exit(0 if problems == 0 else 1)
