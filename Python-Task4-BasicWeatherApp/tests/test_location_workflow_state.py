import tempfile
import unittest
from pathlib import Path

import requests

from tests.fixtures import FakeResponse, FakeSession, current_json, forecast_json
from weatherdesk import location, state, workflow
from weatherdesk.api import WeatherService
from weatherdesk.errors import LocationError, NetworkError

KEY = "0123456789abcdef0123456789abcdef"


class LocationTests(unittest.TestCase):
    def test_first_provider(self):
        s = FakeSession(FakeResponse(200, {"latitude": 18.5, "longitude": 73.8, "city": "Pune", "country_code": "IN"}))
        place = location.detect_location(session=s)
        self.assertEqual((place.city, place.country, place.lat), ("Pune", "IN", 18.5))

    def test_fallback_to_second_provider(self):
        s = FakeSession(FakeResponse(200, {"error": True, "reason": "RateLimited"}),
                        FakeResponse(200, {"status": "success", "lat": 1.3, "lon": 103.8,
                                           "city": "Singapore", "countryCode": "SG"}))
        self.assertEqual(location.detect_location(session=s).city, "Singapore")
        self.assertEqual(len(s.calls), 2)

    def test_all_providers_fail(self):
        s = FakeSession(requests.exceptions.ConnectionError(), FakeResponse(500, {}))
        with self.assertRaises(LocationError):
            location.detect_location(session=s)


class WorkflowTests(unittest.TestCase):
    def test_locate_success(self):
        svc = WeatherService(KEY, session=FakeSession(FakeResponse(200, current_json()), FakeResponse(200, forecast_json())))
        res = workflow.load_current_location(svc, "Mumbai", detector=lambda: location.GeoLocation(19.0, 72.8, "x", "IN"))
        self.assertTrue(res.located)
        self.assertIsNone(res.note)

    def test_locate_falls_back_to_default_city_with_note(self):
        def failing():
            raise LocationError()
        session = FakeSession(FakeResponse(200, current_json()), FakeResponse(200, forecast_json()))
        res = workflow.load_current_location(WeatherService(KEY, session=session), "Mumbai", detector=failing)
        self.assertFalse(res.located)
        self.assertIn("Mumbai", res.note)
        self.assertEqual(session.calls[0][1]["q"], "Mumbai")

    def test_locate_offline_after_detection_raises_network_error(self):
        svc = WeatherService(KEY, session=FakeSession(requests.exceptions.ConnectionError()))
        with self.assertRaises(NetworkError):
            workflow.load_current_location(svc, "Mumbai", detector=lambda: location.GeoLocation(1, 2, "", ""))


class StateTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "state.json"
            state.save_state(state.AppState("Pune,IN", "F", ["Pune", "Tokyo"]), path)
            loaded = state.load_state(path)
            self.assertEqual((loaded.last_city, loaded.units, loaded.recent), ("Pune,IN", "F", ["Pune", "Tokyo"]))

    def test_corrupt_or_missing_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.assertEqual(state.load_state(path).last_city, "")
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(state.load_state(path).recent, [])

    def test_add_recent_dedupes_and_limits(self):
        recent = ["A", "B", "C"]
        self.assertEqual(state.add_recent(recent, "b"), ["b", "A", "C"])
        many = [str(i) for i in range(10)]
        self.assertEqual(len(state.add_recent(many, "new")), state.MAX_RECENT)
        self.assertEqual(state.add_recent(recent, "  "), recent)


if __name__ == "__main__":
    unittest.main()
