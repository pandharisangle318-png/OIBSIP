import threading
import unittest

from tests.helpers import ROOT  # noqa: F401
from core.assistant import Assistant
from features.reminder_service import ReminderService, format_duration, parse_duration, parse_reminder_request


class ParsingTests(unittest.TestCase):
    def test_valid_durations(self):
        """Durations in digits, words and mixed units are understood."""
        cases = {"in 5 minutes": 300, "after ten minutes": 600, "for 30 seconds": 30, "in an hour": 3600,
                 "in half an hour": 1800, "in 1 hour 30 minutes": 5400, "in twenty five minutes": 1500,
                 "in 2 hours": 7200, "after 1 min": 60}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text)[0], expected)

    def test_invalid_duration(self):
        """Text without a duration returns None."""
        self.assertIsNone(parse_duration("remind me to drink water")[0])

    def test_message_extraction(self):
        """The reminder message is separated from the duration in different sentence orders."""
        cases = {
            "Remind me after 5 minutes to drink water": (300, "drink water"),
            "Remind me to call mom in 10 minutes": (600, "call mom"),
            "Set a reminder for 10 minutes": (600, ""),
            "Set a timer for 2 minutes": (120, ""),
            "Remind me about the meeting in 1 hour": (3600, "the meeting"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_reminder_request(text), expected)

    def test_format_duration(self):
        """Durations are spoken naturally."""
        self.assertEqual(format_duration(300), "5 minutes")
        self.assertEqual(format_duration(3661), "1 hour and 1 minute and 1 second")


class ServiceTests(unittest.TestCase):
    def test_trigger_execution(self):
        """A due reminder fires its callback once, in the background."""
        done, got = threading.Event(), []
        svc = ReminderService(lambda r: (got.append(r), done.set()))
        svc.add(0.05, "drink water")
        self.assertTrue(done.wait(2))
        self.assertEqual([r.message for r in got], ["drink water"])
        self.assertEqual(svc.active(), [])
        svc.shutdown()

    def test_multiple_reminders(self):
        """Several reminders can run at the same time and all fire."""
        got, lock, done = [], threading.Lock(), threading.Event()
        def cb(r):
            with lock:
                got.append(r.message)
                if len(got) == 3:
                    done.set()
        svc = ReminderService(cb)
        for i, delay in enumerate((0.05, 0.1, 0.15)):
            svc.add(delay, f"r{i}")
        self.assertEqual(len(svc.active()), 3)
        self.assertTrue(done.wait(3))
        self.assertEqual(sorted(got), ["r0", "r1", "r2"])
        svc.shutdown()

    def test_cancellation(self):
        """A cancelled reminder never fires; cancel_all clears the rest."""
        got = []
        svc = ReminderService(got.append)
        a, b = svc.add(0.1, "a"), svc.add(0.1, "b")
        self.assertTrue(svc.cancel(a.id))
        self.assertFalse(svc.cancel(a.id))
        self.assertEqual(svc.cancel_all(), 1)
        import time; time.sleep(0.3)
        self.assertEqual(got, [])
        svc.shutdown()

    def test_invalid_values_rejected(self):
        """Zero, negative and too-long reminders raise ValueError."""
        svc = ReminderService(lambda r: None, max_seconds=100)
        for bad in (0, -5, None, 101):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                svc.add(bad, "x")
        svc.shutdown()

    def test_shutdown_cancels_pending_and_blocks_new(self):
        """Shutdown stops background timers cleanly."""
        got = []
        svc = ReminderService(got.append)
        svc.add(0.1, "x")
        svc.shutdown()
        with self.assertRaises(RuntimeError):
            svc.add(1, "y")
        import time; time.sleep(0.25)
        self.assertEqual(got, [])

    def test_callback_error_does_not_kill_service(self):
        """An exception inside the callback is logged and swallowed."""
        done = threading.Event()
        calls = []
        def cb(r):
            calls.append(r.message)
            done.set()
            raise RuntimeError("boom")
        svc = ReminderService(cb)
        svc.add(0.05, "x")
        self.assertTrue(done.wait(2))
        svc.add(0.05, "y")
        svc.shutdown()


class AssistantReminderTests(unittest.TestCase):
    def test_alert_speech_and_conversation_message(self):
        """A fired reminder plays the alert, speaks the message and appears in the conversation."""
        from tests.helpers import make_handler
        spoken, shown, alerts, done = [], [], [], threading.Event()
        class Spk:
            def say(self, t): spoken.append(t)
            def shutdown(self): pass
            def wait_idle(self, timeout=0): return True
        handler, parts = make_handler()
        parts["reminders"].shutdown()
        assistant = Assistant(handler.config, speaker=Spk(), on_message=lambda r, t: (shown.append((r, t)), done.set() if t.startswith("Reminder") else None),
                              handler=handler, alert=lambda: alerts.append(1))
        handler.reminders = assistant.reminders
        assistant.reminders.add(0.05, "drink water")
        self.assertTrue(done.wait(2))
        self.assertIn(("assistant", "Reminder: drink water"), shown)
        self.assertEqual(alerts, [1])
        self.assertEqual(spoken, ["Reminder. drink water"])
        assistant.shutdown()

    def test_assistant_process_emits_and_speaks(self):
        """Assistant.process shows the user message and reply and speaks the reply once."""
        from tests.helpers import make_handler
        spoken, shown = [], []
        class Spk:
            def say(self, t): spoken.append(t)
            def shutdown(self): pass
        handler, parts = make_handler()
        assistant = Assistant(handler.config, speaker=Spk(), on_message=lambda r, t: shown.append((r, t)), handler=handler)
        assistant.process("what is the time")
        self.assertEqual(shown, [("user", "what is the time"), ("assistant", "The time is 3:05 PM.")])
        self.assertEqual(spoken, ["The time is 3:05 PM."])
        parts["reminders"].shutdown(); assistant.shutdown()


if __name__ == "__main__":
    unittest.main()
