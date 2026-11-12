import unittest

import requests

from tests.helpers import FakeResponse, FakeSession
from features.weather_service import WeatherError, WeatherService

GOOD = {"name": "Mumbai", "sys": {"country": "IN"}, "main": {"temp": 29.4, "feels_like": 33.1, "humidity": 74},
        "weather": [{"description": "haze"}], "wind": {"speed": 3.5}}


def svc(response=None, error=None, key="abc123"):
    return WeatherService(key, session=FakeSession(response, error))


class WeatherTests(unittest.TestCase):
    def kind(self, service, city="Mumbai"):
        with self.assertRaises(WeatherError) as ctx:
            service.get_weather(city)
        return ctx.exception.kind

    def test_missing_api_key(self):
        """No API key gives a configuration message and makes no request."""
        s = svc(key=None)
        self.assertEqual(self.kind(s), "no_key")
        self.assertEqual(s._session.calls, [])

    def test_invalid_api_key(self):
        """HTTP 401 is reported as an invalid / inactive key."""
        self.assertEqual(self.kind(svc(FakeResponse(401, {"cod": 401}))), "invalid_key")

    def test_city_not_found(self):
        """HTTP 404 is reported as city not found."""
        self.assertEqual(self.kind(svc(FakeResponse(404, {"cod": "404"})), "Nowhereville"), "city_not_found")

    def test_rate_limit(self):
        """HTTP 429 is reported as a rate limit."""
        self.assertEqual(self.kind(svc(FakeResponse(429, {}))), "rate_limit")

    def test_other_http_error(self):
        """Other HTTP errors are reported without crashing."""
        self.assertEqual(self.kind(svc(FakeResponse(500, {}))), "http_error")

    def test_network_failure_and_timeout(self):
        """Connection failure and timeout are separate friendly errors."""
        self.assertEqual(self.kind(svc(error=requests.exceptions.ConnectionError())), "network")
        self.assertEqual(self.kind(svc(error=requests.exceptions.Timeout())), "timeout")

    def test_malformed_response(self):
        """Missing fields or invalid JSON are handled as a bad response."""
        self.assertEqual(self.kind(svc(FakeResponse(200, {"name": "x"}))), "bad_response")
        self.assertEqual(self.kind(svc(FakeResponse(200, bad_json=True))), "bad_response")

    def test_valid_response(self):
        """A valid response yields every required field and a readable sentence."""
        s = svc(FakeResponse(200, GOOD))
        report = s.get_weather("Mumbai")
        self.assertEqual((report.city, report.humidity, report.description), ("Mumbai", 74, "haze"))
        text = report.to_text()
        for part in ("Mumbai, IN", "haze", "29 degrees Celsius", "feels like 33", "Humidity 74 percent", "13 kilometres per hour"):
            self.assertIn(part, text)
        url, kwargs = s._session.calls[0]
        self.assertEqual(kwargs["params"]["q"], "Mumbai")
        self.assertEqual(kwargs["timeout"], 10)

    def test_empty_city(self):
        """An empty city asks which city."""
        self.assertEqual(self.kind(svc(FakeResponse(200, GOOD)), "  "), "no_city")

    def test_weather_through_command_handler(self):
        """The command handler turns a weather request into the weather sentence."""
        from tests.helpers import make_handler
        h, parts = make_handler(env={"OPENWEATHER_API_KEY": "abc123"}, weather_session=FakeSession(FakeResponse(200, GOOD)))
        self.assertIn("Weather in Mumbai, IN", h.handle("What is the weather in Mumbai?")[0].text)
        self.assertEqual(parts["weather"]._session.calls[0][1]["params"]["q"], "Mumbai")
        parts["reminders"].shutdown()

    def test_weather_asks_for_city_when_missing(self):
        """'weather' with no city (and none configured) asks for one, then answers."""
        from tests.helpers import make_handler
        h, parts = make_handler(env={"OPENWEATHER_API_KEY": "abc123"}, weather_session=FakeSession(FakeResponse(200, GOOD)))
        self.assertIn("Which city", h.handle("what's the weather")[0].text)
        self.assertIn("Weather in Mumbai", h.handle("Mumbai")[0].text)
        parts["reminders"].shutdown()


if __name__ == "__main__":
    unittest.main()
