"""GUI smoke test. Runs headless (offscreen) and is skipped automatically if PySide6 is missing."""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False

from tests.fixtures import current_json, forecast_json


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_bundle(self, weather_id=500):
        from weatherdesk.models import WeatherBundle
        from weatherdesk.processing import parse_current, parse_forecast
        cur = parse_current(current_json(weather=[{"id": weather_id, "main": "x", "description": "test sky", "icon": "01d"}]))
        return WeatherBundle(cur, parse_forecast(forecast_json(), cur.sunrise, cur.sunset), datetime.now())

    def make_window(self, tmp):
        from weatherdesk.config import Config
        from weatherdesk.ui.main_window import MainWindow
        cfg = Config(api_key="0123456789abcdef0123456789abcdef", effects_enabled=False)
        return MainWindow(cfg, state_path=Path(tmp) / "state.json", autoload=False)

    def test_renders_and_converts_units(self):
        from weatherdesk.models import Condition
        with tempfile.TemporaryDirectory() as tmp:
            win = self.make_window(tmp)
            win.resize(1280, 820)
            win.show_bundle(self.make_bundle())
            self.assertEqual(win.city_label.text(), "Mumbai")
            self.assertEqual(win.temp_label.text(), "29\u00b0")
            win.set_units("F")
            self.assertEqual(win.temp_label.text(), "85\u00b0")      # 29.4 C -> 84.9 F
            self.assertFalse(win.grab().isNull())
            for cond in Condition:
                win.scene.set_weather(cond, False)
                win.scene.set_weather(cond, True)
                self.assertFalse(win.scene.grab().isNull())
            win.close()

    def test_error_states_do_not_crash(self):
        from weatherdesk.errors import CityNotFoundError, MissingApiKeyError, NetworkError
        with tempfile.TemporaryDirectory() as tmp:
            win = self.make_window(tmp)
            for exc in (NetworkError(), CityNotFoundError("nope"), MissingApiKeyError(), ValueError("x")):
                win._show_error(exc)
            win.show_bundle(self.make_bundle())
            win._show_error(NetworkError())          # now shown as a banner over existing data
            win.close()


if __name__ == "__main__":
    unittest.main()
