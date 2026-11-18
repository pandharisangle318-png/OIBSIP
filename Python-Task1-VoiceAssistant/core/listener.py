"""Speech recognition with clearly separated outcomes.

Every possible result of one listening attempt is mapped to exactly one
``ListenStatus`` so the rest of the program never has to guess:

    RECOGNIZED      speech was converted to text
    UNINTELLIGIBLE  speech was heard but could not be understood (or text was "")
    NO_SPEECH       nothing was said before the timeout (or the result was None)
    MIC_UNAVAILABLE no usable microphone / PyAudio / SpeechRecognition
    NETWORK_ERROR   the recognition web service could not be reached
    STOPPED         the user pressed Stop while listening
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class ListenStatus(enum.Enum):
    RECOGNIZED = "recognized"
    UNINTELLIGIBLE = "unintelligible"
    NO_SPEECH = "no_speech"
    MIC_UNAVAILABLE = "mic_unavailable"
    NETWORK_ERROR = "network_error"
    STOPPED = "stopped"


@dataclass
class ListenResult:
    status: ListenStatus
    text: str = ""
    detail: str = ""


def interpret_recognition(raw: Optional[str]) -> ListenResult:
    """Map a raw recogniser return value to a status.

    ``""`` means speech was heard but not understood; ``None`` means nothing usable was detected.
    """
    if raw is None:
        return ListenResult(ListenStatus.NO_SPEECH)
    text = str(raw).strip()
    if not text:
        return ListenResult(ListenStatus.UNINTELLIGIBLE)
    return ListenResult(ListenStatus.RECOGNIZED, text)


class Listener:
    def __init__(self, settings: dict, sr_module: Any = None, microphone_factory: Optional[Callable[[], Any]] = None) -> None:
        self.language = settings.get("language", "en-IN")
        self.timeout = float(settings.get("listen_timeout", 6))
        self.phrase_limit = float(settings.get("phrase_time_limit", 10))
        self.calibration = float(settings.get("calibration_seconds", 0.6))
        self._sr = sr_module
        self._mic_factory = microphone_factory
        self._recognizer = None
        self._calibrated = False

    def reset_calibration(self) -> None:
        self._calibrated = False

    def _load_sr(self):
        if self._sr is None:
            import speech_recognition as sr  # imported lazily so the GUI starts without it

            self._sr = sr
        return self._sr

    def check_microphone(self) -> ListenResult:
        """Used by diagnostics: can a microphone be opened?"""
        try:
            sr = self._load_sr()
            mic = self._mic_factory() if self._mic_factory else sr.Microphone()
            with mic:
                pass
            return ListenResult(ListenStatus.RECOGNIZED, "Microphone opened successfully.")
        except ImportError as exc:
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=f"SpeechRecognition missing: {exc}")
        except Exception as exc:
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=str(exc))

    def listen_once(self, stop_event: Optional[threading.Event] = None) -> ListenResult:
        """Listen for one phrase. Never raises."""
        try:
            sr = self._load_sr()
        except ImportError as exc:
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=f"SpeechRecognition not installed: {exc}")
        try:
            if self._recognizer is None:
                self._recognizer = sr.Recognizer()
                self._recognizer.dynamic_energy_threshold = True
                self._recognizer.pause_threshold = 0.8
            recognizer = self._recognizer
            mic = self._mic_factory() if self._mic_factory else sr.Microphone()
        except Exception as exc:  # e.g. PyAudio missing -> AttributeError
            log.warning("Microphone initialisation failed: %s", exc)
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=str(exc))

        audio = None
        try:
            with mic as source:
                if not self._calibrated:
                    recognizer.adjust_for_ambient_noise(source, duration=self.calibration)
                    self._calibrated = True
                deadline = time.monotonic() + self.timeout
                while audio is None:
                    if stop_event is not None and stop_event.is_set():
                        return ListenResult(ListenStatus.STOPPED)
                    try:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=self.phrase_limit)
                    except sr.WaitTimeoutError:
                        if time.monotonic() >= deadline:
                            return ListenResult(ListenStatus.NO_SPEECH)
        except (OSError, AttributeError) as exc:
            log.warning("Microphone error while listening: %s", exc)
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=str(exc))
        except Exception as exc:
            log.warning("Unexpected listening error: %s", exc)
            return ListenResult(ListenStatus.MIC_UNAVAILABLE, detail=str(exc))

        if stop_event is not None and stop_event.is_set():
            return ListenResult(ListenStatus.STOPPED)
        try:
            raw = recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return ListenResult(ListenStatus.UNINTELLIGIBLE)
        except sr.RequestError as exc:
            log.warning("Speech service error: %s", exc)
            return ListenResult(ListenStatus.NETWORK_ERROR, detail=str(exc))
        except OSError as exc:  # raw connection problems
            return ListenResult(ListenStatus.NETWORK_ERROR, detail=str(exc))
        except Exception as exc:
            log.warning("Unexpected recognition error: %s", exc)
            return ListenResult(ListenStatus.NETWORK_ERROR, detail=str(exc))
        return interpret_recognition(raw)
