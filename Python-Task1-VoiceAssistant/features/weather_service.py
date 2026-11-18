"""Live weather through the OpenWeatherMap current-weather API."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:  # handled at call time
    requests = None  # type: ignore[assignment]

log = logging.getLogger(__name__)
API_URL = "https://api.openweathermap.org/data/2.5/weather"

NO_KEY_MESSAGE = (
    "Weather is not set up yet. Create a free key at openweathermap.org, then put it in the "
    ".env file as OPENWEATHER_API_KEY and restart VYOM. Everything else still works."
)


class WeatherError(Exception):
    def __init__(self, kind: str, user_message: str) -> None:
        super().__init__(user_message)
        self.kind = kind
        self.user_message = user_message


@dataclass
class WeatherReport:
    city: str
    country: str
    temperature: float
    feels_like: float
    description: str
    humidity: int
    wind_speed: float  # metres/second (metric) or miles/hour (imperial)
    units: str

    def to_text(self) -> str:
        unit_word = "Celsius" if self.units == "metric" else "Fahrenheit"
        place = f"{self.city}, {self.country}" if self.country else self.city
        if self.units == "metric":
            wind = f"{self.wind_speed * 3.6:.0f} kilometres per hour"
        else:
            wind = f"{self.wind_speed:.0f} miles per hour"
        return (
            f"Weather in {place}: {self.description}. Temperature {self.temperature:.0f} degrees {unit_word}, "
            f"feels like {self.feels_like:.0f}. Humidity {self.humidity} percent. Wind speed {wind}."
        )


class WeatherService:
    def __init__(self, api_key: Optional[str], units: str = "metric", timeout: float = 10, session=None) -> None:
        self.api_key = api_key
        self.units = units if units in ("metric", "imperial") else "metric"
        self.timeout = timeout
        self._session = session

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def get_weather(self, city: str) -> WeatherReport:
        city = " ".join((city or "").split())
        if not self.api_key:
            raise WeatherError("no_key", NO_KEY_MESSAGE)
        if not city:
            raise WeatherError("no_city", "Which city would you like the weather for?")
        http = self._session or requests
        if http is None:
            raise WeatherError("network", "The requests library is not installed. Run setup.bat again.")
        params = {"q": city, "appid": self.api_key, "units": self.units}
        try:
            response = http.get(API_URL, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise WeatherError("timeout", "The weather service took too long to answer. Please try again.")
        except requests.exceptions.RequestException:
            raise WeatherError("network", "I could not reach the weather service. Please check your internet connection.")
        return self._parse(response, city)

    def _parse(self, response, city: str) -> WeatherReport:
        status = response.status_code
        if status == 401:
            raise WeatherError(
                "invalid_key",
                "The weather API key was rejected. Check OPENWEATHER_API_KEY in your .env file. "
                "A brand new key can take up to a couple of hours to become active.",
            )
        if status == 404:
            raise WeatherError("city_not_found", f"I could not find a city called {city}. Please check the spelling.")
        if status == 429:
            raise WeatherError("rate_limit", "The weather service rate limit was reached. Please try again in a minute.")
        if status != 200:
            raise WeatherError("http_error", f"The weather service returned an error (code {status}). Please try again later.")
        try:
            data = response.json()
            return WeatherReport(
                city=str(data.get("name") or city),
                country=str((data.get("sys") or {}).get("country") or ""),
                temperature=float(data["main"]["temp"]),
                feels_like=float(data["main"]["feels_like"]),
                description=str(data["weather"][0]["description"]),
                humidity=int(data["main"]["humidity"]),
                wind_speed=float((data.get("wind") or {}).get("speed", 0.0)),
                units=self.units,
            )
        except (ValueError, KeyError, IndexError, TypeError):
            raise WeatherError("bad_response", "The weather service sent an unexpected reply. Please try again later.")
