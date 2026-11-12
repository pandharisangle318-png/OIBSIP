"""The listen -> understand -> respond loop (Qt-free so it can be unit tested)."""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from core import messages
from core.listener import ListenStatus

log = logging.getLogger(__name__)


class VoiceSession:
    def __init__(self, assistant, listener, max_failures: int = 3,
                 on_state: Optional[Callable[[str], None]] = None,
                 on_action: Optional[Callable[[str], None]] = None) -> None:
        self.assistant = assistant
        self.listener = listener
        self.max_failures = max(1, int(max_failures))
        self._on_state = on_state or (lambda s: None)
        self._on_action = on_action or (lambda a: None)
        self.stop_event = threading.Event()

    def request_stop(self) -> None:
        self.stop_event.set()

    def _wait_for_speech_to_finish(self) -> None:
        speaker = self.assistant.speaker
        while not self.stop_event.is_set():
            if speaker.wait_idle(timeout=0.3):
                return

    def run(self) -> None:
        """Run until stopped. Always ends in the 'standby' state."""
        self.listener.reset_calibration()
        failures = 0
        try:
            while not self.stop_event.is_set():
                self._on_state("listening")
                result = self.listener.listen_once(self.stop_event)
                status = result.status

                if status is ListenStatus.STOPPED:
                    break
                if status is ListenStatus.NO_SPEECH:
                    continue  # silent: nothing was said, just keep listening
                if status is ListenStatus.UNINTELLIGIBLE:
                    failures += 1
                    if failures >= self.max_failures:
                        self.assistant.announce(messages.TROUBLE_HEARING)
                        break
                    self.assistant.announce(messages.UNINTELLIGIBLE)
                    self._wait_for_speech_to_finish()
                    continue
                if status is ListenStatus.MIC_UNAVAILABLE:
                    log.warning("Microphone unavailable: %s", result.detail)
                    self.assistant.announce(messages.MIC_UNAVAILABLE, speak=False)
                    break
                if status is ListenStatus.NETWORK_ERROR:
                    log.warning("Speech network error: %s", result.detail)
                    self.assistant.announce(messages.NETWORK_SPEECH, speak=False)
                    break

                failures = 0
                self._on_state("processing")
                replies = self.assistant.process(result.text, source="voice")
                self._wait_for_speech_to_finish()
                actions = [r.action for r in replies if r.action]
                if "exit" in actions:
                    self._on_action("exit")
                    break
                if "stop_listening" in actions:
                    break
        except Exception:
            log.exception("Voice session crashed")
            self.assistant.announce("Something went wrong with the microphone loop. Please press Start Assistant to try again.", speak=False)
        finally:
            self._on_state("standby")
