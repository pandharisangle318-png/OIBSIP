"""GUI checks.

* Static checks (always run): every button is connected to a method that exists, and the
  window uses background workers.
* Runtime checks (need PySide6; skipped with a clear reason otherwise): the window is created
  offscreen and Start/Stop, messages and the single-listening-thread rule are exercised.
"""
import ast
import os
import unittest

from tests.helpers import ROOT

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False

SOURCE = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")


class GuiStaticTests(unittest.TestCase):
    def test_every_connected_slot_exists(self):
        """Every `.connect(self.xxx)` in the window points at a method that is defined."""
        tree = ast.parse(SOURCE)
        window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        methods = {n.name for n in window.body if isinstance(n, ast.FunctionDef)}
        referenced = set()
        for node in ast.walk(window):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
                for arg in node.args:
                    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "self":
                        referenced.add(arg.attr)
        self.assertTrue(referenced)
        self.assertEqual(referenced - methods, set(), "connected to missing methods")

    def test_all_required_controls_are_present(self):
        """Start, Stop, Send, Clear, Mute, Settings and the six quick actions exist."""
        for label in ('"Start Assistant"', '"Stop Assistant"', '"Send"', '"Clear"', '"Mute Voice"', '"Settings"',
                      '("Time"', '("Date"', '("Help"', '("Weather"', '("Search"', '("Email"'):
            self.assertIn(label, SOURCE)

    def test_blocking_work_is_off_the_gui_thread(self):
        """Commands go through CommandTask (thread pool) and voice through VoiceWorker (QThread)."""
        self.assertIn("CommandTask(", SOURCE)
        self.assertIn("VoiceWorker(", SOURCE)
        self.assertNotIn(".process(", SOURCE)       # the window never calls the assistant directly
        self.assertNotIn("listen_once", SOURCE)

    def test_duplicate_listening_guard_and_cleanup_present(self):
        """start_assistant refuses a second worker; closeEvent stops the worker and shuts services down."""
        self.assertRegex(SOURCE, r"def start_assistant\(self\) -> None:\n\s+if self\.voice_running\(\):")
        self.assertIn("self.voice_worker.request_stop()", SOURCE)
        self.assertIn("self.assistant.shutdown()", SOURCE)


@unittest.skipUnless(HAVE_QT, "NOT RUN: PySide6 is not installed in this environment")
class GuiRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        from core.config import Config
        from gui.main_window import MainWindow
        win = MainWindow(Config(env={}, load_env_file=False))
        win.speaker.set_muted(True)
        return win

    def pump(self, ms=300):
        from PySide6.QtCore import QEventLoop, QTimer
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def test_window_creates_and_typed_command_shows_both_bubbles(self):
        """A typed command produces a user bubble and an assistant bubble without freezing."""
        win = self.make_window()
        before = win.chat._layout.count()
        win.input.setText("what is the time")
        win.send_btn.click()
        self.pump(800)
        self.assertGreaterEqual(win.chat._layout.count(), before + 2)
        win.close()

    def test_start_twice_creates_one_worker_and_stop_returns_to_standby(self):
        """Pressing Start twice never creates a second listening thread; Stop returns to standby."""
        win = self.make_window()
        win.start_assistant()
        first = win.voice_worker
        win.start_assistant()
        self.assertIs(win.voice_worker, first)
        win.stop_assistant()
        first.wait(8000)
        self.pump(200)
        self.assertFalse(win.voice_running())
        self.assertTrue(win.start_btn.isEnabled())
        win.close()

    def test_clear_button_empties_conversation(self):
        """Clear removes all bubbles."""
        win = self.make_window()
        win.clear_btn.click()
        self.assertEqual(win.chat._layout.count(), 1)
        win.close()


if __name__ == "__main__":
    unittest.main()
