"""Text-to-speech with a single queue (no overlapping speech) using pyttsx3.

A fresh pyttsx3 engine is created for each utterance inside one dedicated worker
thread.  This avoids the well-known Windows problem where ``runAndWait`` hangs or
stays silent after the first call.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)
_STOP = object()


class NullSpeaker:
    """Silent speaker used in tests and when speech is unavailable."""

    available = False
    muted = True

    def say(self, text: str) -> None: ...
    def set_muted(self, muted: bool) -> None: ...
    def clear(self) -> None: ...
    def wait_idle(self, timeout: float = 30.0) -> bool:
        return True
    def shutdown(self) -> None: ...


class Speaker:
    def __init__(self, settings: dict, on_state: Optional[Callable[[str], None]] = None, engine_factory: Optional[Callable] = None) -> None:
        self.rate = int(settings.get("rate", 175))
        self.volume = float(settings.get("volume", 1.0))
        self.voice_index = int(settings.get("voice_index", 0))
        self.muted = bool(settings.get("muted", False))
        self.available = True
        self._on_state = on_state or (lambda state: None)
        self._factory = engine_factory
        self._queue: "queue.Queue" = queue.Queue()
        self._pending = 0
        self._cond = threading.Condition()
        self._thread: Optional[threading.Thread] = None
        self._stopping = False

    # ------------------------------------------------------------ public API
    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self.muted or not self.available:
            return
        self._ensure_thread()
        with self._cond:
            self._pending += 1
        self._queue.put(text)

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        if muted:
            self.clear()

    def clear(self) -> None:
        """Drop queued sentences (the one being spoken finishes)."""
        dropped = 0
        try:
            while True:
                item = self._queue.get_nowait()
                if item is not _STOP:
                    dropped += 1
                else:
                    self._queue.put(_STOP)
                    break
        except queue.Empty:
            pass
        if dropped:
            self._finish(dropped)

    def wait_idle(self, timeout: float = 30.0) -> bool:
        with self._cond:
            return self._cond.wait_for(lambda: self._pending == 0, timeout=timeout)

    def shutdown(self) -> None:
        self._stopping = True
        self.clear()
        if self._thread and self._thread.is_alive():
            self._queue.put(_STOP)
            self._thread.join(timeout=3)

    # -------------------------------------------------------------- internals
    def _finish(self, count: int = 1) -> None:
        with self._cond:
            self._pending = max(0, self._pending - count)
            if self._pending == 0:
                self._cond.notify_all()

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stopping = False
            self._thread = threading.Thread(target=self._run, name="vyom-tts", daemon=True)
            self._thread.start()

    def _make_engine(self):
        if self._factory:
            engine = self._factory()
        else:
            import pyttsx3

            engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        try:
            voices = engine.getProperty("voices")
            if voices and 0 <= self.voice_index < len(voices):
                engine.setProperty("voice", voices[self.voice_index].id)
        except Exception:
            pass
        return engine

    def _run(self) -> None:
        com = None
        try:
            import pythoncom  # present on Windows through pywin32 (a pyttsx3 dependency)

            pythoncom.CoInitialize()
            com = pythoncom
        except Exception:
            pass
        try:
            while True:
                item = self._queue.get()
                if item is _STOP:
                    break
                try:
                    self._on_state("speaking")
                    engine = self._make_engine()
                    engine.say(item)
                    engine.runAndWait()
                    try:
                        engine.stop()
                    except Exception:
                        pass
                    del engine
                except ImportError:
                    log.error("pyttsx3 is not installed; speech disabled.")
                    self.available = False
                except Exception as exc:
                    log.warning("Speech failed: %s", exc)
                finally:
                    self._finish()
                    if self._queue.empty():
                        self._on_state("idle")
                if not self.available:
                    self.clear()
        finally:
            if com is not None:
                try:
                    com.CoUninitialize()
                except Exception:
                    pass
