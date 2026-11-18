import unittest

import requests

from tests.fixtures import FakeResponse, FakeSession, current_json, forecast_json
from weatherdesk.api import WeatherService
from weatherdesk.errors import (ApiError, CityNotFoundError, InvalidApiKeyError, MissingApiKeyError,
                                NetworkError, RateLimitError)

KEY = "0123456789abcdef0123456789abcdef"


def ok_pair():
    return FakeSession(FakeResponse(200, current_json()), FakeResponse(200, forecast_json()))


class ServiceSuccessTests(unittest.TestCase):
    def test_fetch_by_city_makes_two_calls_with_expected_params(self):
        session = ok_pair()
        bundle = WeatherService(KEY, session=session, timeout=7).fetch_by_city("  Mumbai ")
        self.assertEqual(bundle.current.city, "Mumbai")
        self.assertEqual(len(bundle.forecast), 40)
        (url1, p1, t1), (url2, p2, _) = session.calls
        self.assertTrue(url1.endswith("/weather"))
        self.assertTrue(url2.endswith("/forecast"))
        self.assertEqual(p1["q"], "Mumbai")
        self.assertEqual((p1["appid"], p1["units"], t1), (KEY, "metric", 7))
        self.assertAlmostEqual(p2["lat"], 19.0144)          # forecast reuses the resolved coordinates

    def test_fetch_by_coords(self):
        session = ok_pair()
        bundle = WeatherService(KEY, session=session).fetch_by_coords(19.0, 72.8)
        self.assertEqual(bundle.current.country, "IN")
        self.assertEqual(session.calls[0][1]["lat"], 19.0)


class ServiceErrorTests(unittest.TestCase):
    def svc(self, *queue):
        return WeatherService(KEY, session=FakeSession(*queue))

    def test_invalid_key(self):
        with self.assertRaises(InvalidApiKeyError):
            self.svc(FakeResponse(401, {})).fetch_by_city("x")

    def test_city_not_found_mentions_city(self):
        with self.assertRaises(CityNotFoundError) as ctx:
            self.svc(FakeResponse(404, {})).fetch_by_city("Atlantis")
        self.assertIn("Atlantis", ctx.exception.message)

    def test_rate_limit_and_server_error(self):
        with self.assertRaises(RateLimitError):
            self.svc(FakeResponse(429, {})).fetch_by_city("x")
        with self.assertRaises(ApiError) as ctx:
            self.svc(FakeResponse(503, {})).fetch_by_city("x")
        self.assertIn("503", ctx.exception.message)

    def test_connection_errors_become_network_error(self):
        for exc in (requests.exceptions.ConnectionError("down"), requests.exceptions.Timeout("slow"),
                    requests.exceptions.RequestException("boom")):
            with self.assertRaises(NetworkError):
                self.svc(exc).fetch_by_city("x")

    def test_timeout_message_is_specific(self):
        with self.assertRaises(NetworkError) as ctx:
            self.svc(requests.exceptions.Timeout()).fetch_by_city("x")
        self.assertIn("too long", ctx.exception.message)

    def test_invalid_json_body(self):
        with self.assertRaises(ApiError):
            self.svc(FakeResponse(200, bad_json=True)).fetch_by_city("x")

    def test_missing_or_placeholder_key_never_hits_network(self):
        for key in ("", "   ", "your_api_key_here"):
            session = FakeSession()
            with self.assertRaises(MissingApiKeyError):
                WeatherService(key, session=session).fetch_by_city("Pune")
            self.assertEqual(session.calls, [])

    def test_blank_city_is_rejected_locally(self):
        session = FakeSession()
        with self.assertRaises(CityNotFoundError):
            WeatherService(KEY, session=session).fetch_by_city("   ")
        self.assertEqual(session.calls, [])

    def test_forecast_failure_propagates(self):
        with self.assertRaises(RateLimitError):
            self.svc(FakeResponse(200, current_json()), FakeResponse(429, {})).fetch_by_city("Mumbai")


if __name__ == "__main__":
    unittest.main()
