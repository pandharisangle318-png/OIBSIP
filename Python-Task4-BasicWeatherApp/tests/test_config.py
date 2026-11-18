import tempfile
import unittest
from pathlib import Path

from weatherdesk.config import Config, load_config


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = Config.from_env({})
        self.assertEqual((cfg.default_units, cfg.timeout, cfg.auto_refresh_minutes), ("C", 10.0, 10))
        self.assertTrue(cfg.effects_enabled)
        self.assertFalse(cfg.has_api_key)

    def test_valid_key_and_quotes_stripped(self):
        cfg = Config.from_env({"OPENWEATHER_API_KEY": ' "0123456789abcdef0123456789abcdef" '})
        self.assertTrue(cfg.has_api_key)
        self.assertEqual(len(cfg.api_key), 32)

    def test_placeholder_keys_are_not_valid(self):
        for key in ("", "your_api_key_here", "YOUR_API_KEY_HERE", "short"):
            self.assertFalse(Config.from_env({"OPENWEATHER_API_KEY": key}).has_api_key, key)

    def test_value_parsing_and_clamping(self):
        cfg = Config.from_env({"WEATHERDESK_UNITS": "f", "WEATHERDESK_TIMEOUT": "999",
                               "WEATHERDESK_AUTO_REFRESH_MIN": "-5", "WEATHERDESK_EFFECTS": "off",
                               "WEATHERDESK_DEFAULT_CITY": "  Pune "})
        self.assertEqual((cfg.default_units, cfg.timeout, cfg.auto_refresh_minutes), ("F", 60.0, 0))
        self.assertFalse(cfg.effects_enabled)
        self.assertEqual(cfg.default_city, "Pune")

    def test_garbage_values_fall_back_to_defaults(self):
        cfg = Config.from_env({"WEATHERDESK_UNITS": "kelvin", "WEATHERDESK_TIMEOUT": "abc",
                               "WEATHERDESK_AUTO_REFRESH_MIN": "x", "WEATHERDESK_EFFECTS": "maybe"})
        self.assertEqual((cfg.default_units, cfg.timeout, cfg.auto_refresh_minutes), ("C", 10.0, 10))
        self.assertTrue(cfg.effects_enabled)

    def test_load_from_dotenv_file_and_environment_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("OPENWEATHER_API_KEY=filekeyfilekeyfilekey1234\nWEATHERDESK_UNITS=F\n", encoding="utf-8")
            cfg = load_config(env_file, environ={})
            self.assertEqual((cfg.api_key, cfg.default_units), ("filekeyfilekeyfilekey1234", "F"))
            cfg = load_config(env_file, environ={"OPENWEATHER_API_KEY": "realenvrealenvrealenv9999"})
            self.assertEqual(cfg.api_key, "realenvrealenvrealenv9999")      # real env wins
            self.assertEqual(cfg.default_units, "F")

    def test_missing_file_is_fine(self):
        cfg = load_config(Path("/nonexistent/.env"), environ={})
        self.assertFalse(cfg.has_api_key)


if __name__ == "__main__":
    unittest.main()
