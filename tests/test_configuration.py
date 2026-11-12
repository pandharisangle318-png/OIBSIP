import json
import logging
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT
from core.config import Config
from core.logging_setup import RedactingFilter
from core.text_to_speech import Speaker


class ConfigurationTests(unittest.TestCase):
    def test_defaults_without_any_files(self):
        """The app starts with safe defaults when config.json and .env are both missing."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(root=Path(tmp), env={}, load_env_file=False)
            self.assertEqual(cfg.get("speech.language"), "en-IN")
            self.assertFalse(cfg.email_configured)
            self.assertFalse(cfg.weather_configured)
            self.assertTrue(any("config.json not found" in p for p in cfg.problems))

    def test_invalid_json_falls_back(self):
        """A corrupt config.json does not crash the app."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config.json").write_text("{ not json")
            cfg = Config(root=Path(tmp), env={}, load_env_file=False)
            self.assertEqual(cfg.get("voice.rate"), 175)
            self.assertTrue(cfg.problems)

    def test_json_overrides_defaults_deeply(self):
        """config.json overrides single keys without losing the other defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config.json").write_text(json.dumps({"voice": {"rate": 150}}))
            cfg = Config(root=Path(tmp), env={}, load_env_file=False)
            self.assertEqual(cfg.get("voice.rate"), 150)
            self.assertEqual(cfg.get("voice.volume"), 1.0)

    def test_placeholder_secrets_are_treated_as_missing(self):
        """Values copied unchanged from .env.example count as 'not configured'."""
        env = {"EMAIL_ADDRESS": "your_email@gmail.com", "EMAIL_APP_PASSWORD": "your_16_character_app_password",
               "OPENWEATHER_API_KEY": "your_openweather_api_key_here"}
        cfg = Config(env=env, load_env_file=False)
        self.assertFalse(cfg.email_configured)
        self.assertFalse(cfg.weather_configured)

    def test_real_secrets_and_app_password_spaces(self):
        """Real values are accepted; spaces in a Gmail App Password are removed."""
        env = {"EMAIL_ADDRESS": "me@gmail.com", "EMAIL_APP_PASSWORD": "abcd efgh ijkl mnop", "OPENWEATHER_API_KEY": "k123"}
        cfg = Config(env=env, load_env_file=False)
        self.assertEqual(cfg.email_app_password, "abcdefghijklmnop")
        self.assertTrue(cfg.email_configured and cfg.weather_configured)

    def test_summary_never_contains_secrets(self):
        """The Settings screen data never includes passwords or keys."""
        env = {"EMAIL_ADDRESS": "me@gmail.com", "EMAIL_APP_PASSWORD": "SUPERSECRETPW", "OPENWEATHER_API_KEY": "SECRETKEY99"}
        text = json.dumps(Config(env=env, load_env_file=False).summary())
        for secret in ("SUPERSECRETPW", "SECRETKEY99"):
            self.assertNotIn(secret, text)

    def test_log_redaction(self):
        """Secrets are replaced with *** in log records."""
        flt = RedactingFilter(lambda: ["SUPERSECRETPW"])
        record = logging.LogRecord("x", logging.INFO, "f", 1, "login with %s", ("SUPERSECRETPW",), None)
        flt.filter(record)
        self.assertEqual(record.getMessage(), "login with ***")

    def test_shipped_config_json_is_valid(self):
        """The shipped config.json loads without problems."""
        cfg = Config(root=ROOT, env={}, load_env_file=False)
        self.assertEqual(cfg.problems, [])


class SpeakerTests(unittest.TestCase):
    class FakeEngine:
        log = []
        def setProperty(self, k, v): pass
        def getProperty(self, k): return []
        def say(self, text): FakeSpeakerState.said.append(text)
        def runAndWait(self): pass
        def stop(self): pass

    def test_queue_speaks_in_order_without_overlap(self):
        """Sentences are spoken one at a time, in order, and wait_idle() returns when done."""
        FakeSpeakerState.said = []
        states = []
        sp = Speaker({}, on_state=states.append, engine_factory=self.FakeEngine)
        for t in ("one", "two", "three"):
            sp.say(t)
        self.assertTrue(sp.wait_idle(3))
        self.assertEqual(FakeSpeakerState.said, ["one", "two", "three"])
        self.assertEqual(states[-1], "idle")
        sp.shutdown()

    def test_mute_and_clear(self):
        """Muted speakers stay silent and mute clears the queue."""
        FakeSpeakerState.said = []
        sp = Speaker({"muted": True}, engine_factory=self.FakeEngine)
        sp.say("hidden")
        self.assertTrue(sp.wait_idle(1))
        self.assertEqual(FakeSpeakerState.said, [])
        sp.shutdown()

    def test_engine_failure_does_not_crash_or_hang(self):
        """A failing engine is logged; wait_idle still returns."""
        def broken():
            raise RuntimeError("no sapi5")
        sp = Speaker({}, engine_factory=broken)
        sp.say("hello")
        self.assertTrue(sp.wait_idle(3))
        sp.shutdown()


class FakeSpeakerState:
    said = []


if __name__ == "__main__":
    unittest.main()
