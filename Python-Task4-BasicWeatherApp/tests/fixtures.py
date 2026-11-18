"""Shared sample data that mimics real OpenWeatherMap responses."""
from datetime import datetime, timezone
import math

TZ = 19800  # +05:30
BASE = datetime(2024, 11, 15, 7, 0, tzinfo=timezone.utc)          # 12:30 local
SUNRISE = datetime(2024, 11, 15, 1, 0, tzinfo=timezone.utc)       # 06:30 local
SUNSET = datetime(2024, 11, 15, 12, 20, tzinfo=timezone.utc)      # 17:50 local


def ts(dt):
    return int(dt.timestamp())


def current_json(**over):
    data = {
        "coord": {"lon": 72.8479, "lat": 19.0144},
        "weather": [{"id": 802, "main": "Clouds", "description": "scattered clouds", "icon": "03d"}],
        "main": {"temp": 29.4, "feels_like": 33.1, "pressure": 1009, "humidity": 70},
        "visibility": 6000,
        "wind": {"speed": 4.12, "deg": 250},
        "clouds": {"all": 40},
        "dt": ts(BASE),
        "sys": {"country": "IN", "sunrise": ts(SUNRISE), "sunset": ts(SUNSET)},
        "timezone": TZ,
        "name": "Mumbai",
        "cod": 200,
    }
    data.update(over)
    return data


def forecast_json(count=40, start=None, weather_id=500):
    start = start or ts(BASE) + 3 * 3600
    items = []
    for i in range(count):
        t = start + i * 3 * 3600
        local_hour = ((t + TZ) // 3600) % 24
        items.append({
            "dt": t,
            "main": {"temp": round(25 + 6 * math.sin((local_hour - 9) / 24 * 2 * math.pi), 2)},
            "weather": [{"id": weather_id, "main": "Rain", "description": "light rain", "icon": "10d"}],
            "pop": 0.4,
            "sys": {"pod": "n" if local_hour < 6 or local_hour >= 18 else "d"},
        })
    return {"cod": "200", "cnt": count, "list": items,
            "city": {"name": "Mumbai", "timezone": TZ, "coord": {"lat": 19.0144, "lon": 72.8479}}}


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Returns queued responses (or raises queued exceptions) and records calls."""

    def __init__(self, *queue):
        self.queue = list(queue)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {}), timeout))
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
