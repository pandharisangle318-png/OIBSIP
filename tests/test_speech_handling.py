import threading
import unittest

from tests.helpers import ROOT  # noqa: F401  (sets sys.path)
from core import messages
from core.listener import Listener, ListenStatus, interpret_recognition
from core.voice_session import VoiceSession
from core.command_handler import Reply


class FakeSR:
    class WaitTimeoutError(Exception): ...
    class UnknownValueError(Exception): ...
    class RequestError(Exception): ...

    def __init__(self, listen=None, recognize=None, recognizer_error=None):
        self._listen, self._recognize, self._rec_err = listen, recognize, recognizer_error
        outer = self

        class Recognizer:
            dynamic_energy_threshold = True
            pause_threshold = 0.8

            def adjust_for_ambient_noise(self, source, duration=0.5):
                outer.calibrated = getattr(outer, "calibrated", 0) + 1

            def listen(self, source, timeout=None, phrase_time_limit=None):
                return outer._behave(outer._listen, "audio")

            def recognize_google(self, audio, language=None):
                return outer._behave(outer._recognize, "text")

        self.Recognizer = Recognizer

    @staticmethod
    def _behave(value, default):
        if isinstance(value, Exception) or (isinstance(value, type) and issubclass(value, Exception)):
            raise value
        return default if value is None else value


class FakeMic:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def listener_with(sr, mic_factory=FakeMic, timeout=0.01):
    lst = Listener({"listen_timeout": timeout, "calibration_seconds": 0}, sr_module=sr, microphone_factory=mic_factory)
    return lst


class ListenerOutcomeTests(unittest.TestCase):
    def test_interpret_empty_string_is_unintelligible(self):
        """Empty string result is UNINTELLIGIBLE."""
        self.assertEqual(interpret_recognition("").status, ListenStatus.UNINTELLIGIBLE)
        self.assertEqual(interpret_recognition("   ").status, ListenStatus.UNINTELLIGIBLE)

    def test_interpret_none_is_no_speech(self):
        """None result is NO_SPEECH."""
        self.assertEqual(interpret_recognition(None).status, ListenStatus.NO_SPEECH)

    def test_interpret_text_is_recognized(self):
        """Normal text is RECOGNIZED and trimmed."""
        r = interpret_recognition("  hello vyom ")
        self.assertEqual((r.status, r.text), (ListenStatus.RECOGNIZED, "hello vyom"))

    def test_recognized_speech(self):
        """Recognised speech returns its text."""
        sr = FakeSR(recognize="what is the time")
        r = listener_with(sr).listen_once()
        self.assertEqual((r.status, r.text), (ListenStatus.RECOGNIZED, "what is the time"))

    def test_unintelligible_speech(self):
        """UnknownValueError becomes UNINTELLIGIBLE."""
        sr = FakeSR(recognize=FakeSR.UnknownValueError)
        self.assertEqual(listener_with(sr).listen_once().status, ListenStatus.UNINTELLIGIBLE)

    def test_no_speech_timeout(self):
        """WaitTimeoutError until the deadline becomes NO_SPEECH."""
        sr = FakeSR(listen=FakeSR.WaitTimeoutError)
        self.assertEqual(listener_with(sr).listen_once().status, ListenStatus.NO_SPEECH)

    def test_recognizer_returns_empty_string(self):
        """A recogniser returning '' is UNINTELLIGIBLE, not an unknown command."""
        sr = FakeSR(recognize="")
        self.assertEqual(listener_with(sr).listen_once().status, ListenStatus.UNINTELLIGIBLE)

    def test_recognizer_returns_none(self):
        """A recogniser returning None is NO_SPEECH."""
        class NoneSR(FakeSR):
            @staticmethod
            def _behave(value, default):
                return None if default == "text" else "audio"
        self.assertEqual(listener_with(NoneSR()).listen_once().status, ListenStatus.NO_SPEECH)

    def test_microphone_unavailable_oserror(self):
        """OSError opening the microphone is MIC_UNAVAILABLE."""
        class Bad:
            def __enter__(self):
                raise OSError("No Default Input Device Available")
            def __exit__(self, *a):
                return False
        self.assertEqual(listener_with(FakeSR(), Bad).listen_once().status, ListenStatus.MIC_UNAVAILABLE)

    def test_microphone_unavailable_missing_pyaudio(self):
        """Missing PyAudio (AttributeError creating the Microphone) is MIC_UNAVAILABLE."""
        def factory():
            raise AttributeError("Could not find PyAudio; check installation")
        self.assertEqual(listener_with(FakeSR(), factory).listen_once().status, ListenStatus.MIC_UNAVAILABLE)

    def test_speech_recognition_not_installed(self):
        """ImportError for speech_recognition is MIC_UNAVAILABLE, not a crash."""
        lst = Listener({}, sr_module=None)
        import builtins
        real = builtins.__import__
        def fake_import(name, *a, **k):
            if name == "speech_recognition":
                raise ImportError("No module named speech_recognition")
            return real(name, *a, **k)
        builtins.__import__ = fake_import
        try:
            self.assertEqual(lst.listen_once().status, ListenStatus.MIC_UNAVAILABLE)
        finally:
            builtins.__import__ = real

    def test_network_failure(self):
        """RequestError becomes NETWORK_ERROR."""
        sr = FakeSR(recognize=FakeSR.RequestError("connection failed"))
        self.assertEqual(listener_with(sr).listen_once().status, ListenStatus.NETWORK_ERROR)

    def test_stop_event_ends_listening(self):
        """Stop pressed while waiting for speech returns STOPPED quickly."""
        sr = FakeSR(listen=FakeSR.WaitTimeoutError)
        stop = threading.Event()
        stop.set()
        self.assertEqual(listener_with(sr, timeout=30).listen_once(stop).status, ListenStatus.STOPPED)

    def test_calibration_only_once_per_session(self):
        """Ambient-noise calibration runs once until reset_calibration()."""
        sr = FakeSR(recognize="hi")
        lst = listener_with(sr)
        lst.listen_once(); lst.listen_once()
        self.assertEqual(sr.calibrated, 1)
        lst.reset_calibration(); lst.listen_once()
        self.assertEqual(sr.calibrated, 2)


class ScriptedListener:
    def __init__(self, results):
        self.results = list(results)
        self.reset = 0

    def reset_calibration(self):
        self.reset += 1

    def listen_once(self, stop_event=None):
        if not self.results:
            stop_event.set()
            from core.listener import ListenResult
            return ListenResult(ListenStatus.STOPPED)
        return self.results.pop(0)


class FakeSpeaker:
    def wait_idle(self, timeout=0.3):
        return True


class FakeAssistant:
    def __init__(self, actions=None):
        self.announced, self.processed, self.speaker = [], [], FakeSpeaker()
        self.actions = actions or {}

    def announce(self, text, speak=True):
        self.announced.append((text, speak))

    def process(self, text, source="text"):
        self.processed.append(text)
        return [Reply("ok", action=self.actions.get(text))]


from core.listener import ListenResult as LR  # noqa: E402


def run_session(results, actions=None, max_failures=3):
    assistant = FakeAssistant(actions)
    states = []
    session = VoiceSession(assistant, ScriptedListener(results), max_failures, on_state=states.append)
    session.run()
    return assistant, states


class VoiceSessionTests(unittest.TestCase):
    def test_unintelligible_asks_to_repeat(self):
        """CASE 1: unintelligible speech -> assistant says the exact 'please repeat' sentence, then keeps listening."""
        a, _ = run_session([LR(ListenStatus.UNINTELLIGIBLE), LR(ListenStatus.RECOGNIZED, "hello")])
        self.assertEqual(a.announced[0], (messages.UNINTELLIGIBLE, True))
        self.assertEqual(a.processed, ["hello"])
        self.assertEqual(messages.UNINTELLIGIBLE, "Sorry, I didn't understand that. Could you please repeat?")

    def test_no_speech_is_silent(self):
        """CASE 2: no speech -> nothing is announced and it is not treated as a command."""
        a, _ = run_session([LR(ListenStatus.NO_SPEECH)] * 5 + [LR(ListenStatus.RECOGNIZED, "hello")])
        self.assertEqual(a.announced, [])
        self.assertEqual(a.processed, ["hello"])

    def test_unknown_command_message_text(self):
        """CASE 3: the unknown-command sentence matches the specification."""
        self.assertEqual(messages.UNKNOWN_COMMAND, "Sorry, I am not sure how to help with that. Say help to hear what I can do.")

    def test_microphone_unavailable_ends_session_without_crash(self):
        """CASE 4: microphone unavailable -> clear message (not spoken), session ends in standby."""
        a, states = run_session([LR(ListenStatus.MIC_UNAVAILABLE, detail="x")])
        self.assertEqual(a.announced, [(messages.MIC_UNAVAILABLE, False)])
        self.assertEqual(states[-1], "standby")

    def test_network_error_ends_session_with_retry_hint(self):
        """CASE 5: network error -> useful message (not spoken) and no retry loop."""
        a, states = run_session([LR(ListenStatus.NETWORK_ERROR, detail="x"), LR(ListenStatus.RECOGNIZED, "never reached")])
        self.assertEqual(a.announced, [(messages.NETWORK_SPEECH, False)])
        self.assertEqual(a.processed, [])
        self.assertEqual(states[-1], "standby")

    def test_repeated_failures_do_not_loop_forever(self):
        """Three unintelligible results in a row stop the session instead of looping."""
        a, states = run_session([LR(ListenStatus.UNINTELLIGIBLE)] * 10)
        spoken = [t for t, _ in a.announced]
        self.assertEqual(spoken, [messages.UNINTELLIGIBLE, messages.UNINTELLIGIBLE, messages.TROUBLE_HEARING])
        self.assertEqual(states[-1], "standby")

    def test_success_resets_failure_counter(self):
        """A recognised command resets the consecutive-failure counter."""
        seq = [LR(ListenStatus.UNINTELLIGIBLE), LR(ListenStatus.UNINTELLIGIBLE), LR(ListenStatus.RECOGNIZED, "hello"),
               LR(ListenStatus.UNINTELLIGIBLE), LR(ListenStatus.UNINTELLIGIBLE)]
        a, _ = run_session(seq)
        self.assertNotIn(messages.TROUBLE_HEARING, [t for t, _ in a.announced])

    def test_stop_listening_and_exit_actions(self):
        """'stop listening' ends the loop; 'exit' also reports the exit action."""
        a, _ = run_session([LR(ListenStatus.RECOGNIZED, "stop listening"), LR(ListenStatus.RECOGNIZED, "after")],
                           actions={"stop listening": "stop_listening"})
        self.assertEqual(a.processed, ["stop listening"])
        seen = []
        assistant = FakeAssistant({"exit assistant": "exit"})
        VoiceSession(assistant, ScriptedListener([LR(ListenStatus.RECOGNIZED, "exit assistant")]), 3, on_action=seen.append).run()
        self.assertEqual(seen, ["exit"])

    def test_session_stops_on_request(self):
        """request_stop() ends the loop and the final state is standby."""
        assistant = FakeAssistant()
        session = VoiceSession(assistant, ScriptedListener([]), 3)
        states = []
        session._on_state = states.append
        session.request_stop()
        session.run()
        self.assertEqual(states[-1], "standby")


if __name__ == "__main__":
    unittest.main()
