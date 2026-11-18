"""OpenWeatherMap service layer (no GUI dependencies)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import requests

from .config import API_BASE_URL, PLACEHOLDER_KEYS
from .errors import (ApiError, CityNotFoundError, DataError, InvalidApiKeyError,
                     MissingApiKeyError, NetworkError, RateLimitError)
from .models import WeatherBundle
from .processing import parse_current, parse_forecast


class WeatherService:
    """Fetches current weather and the 3-hour / 5-day forecast."""

    def __init__(self, api_key: str, base_url: str = API_BASE_URL, timeout: float = 10.0,
                 session: Optional[requests.Session] = None):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        if session is None:
            self.session.headers.update({"User-Agent": "WeatherDesk/1.0 (OIBSIP internship project)"})

    # ------------------------------------------------------------------ #
    def _get(self, endpoint: str, params: Dict[str, Any], what: str = "location") -> Dict[str, Any]:
        if self.api_key.lower() in PLACEHOLDER_KEYS:
            raise MissingApiKeyError()
        query = {**params, "appid": self.api_key, "units": "metric"}
        try:
            response = self.session.get(f"{self.base_url}/{endpoint}", params=query, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise NetworkError("The weather service took too long to respond. Please try again.") from exc
        except requests.exceptions.RequestException as exc:
            raise NetworkError() from exc

        status = response.status_code
        if status == 200:
            try:
                payload = response.json()
            except ValueError as exc:
                raise ApiError("The weather service returned an invalid response.") from exc
            if not isinstance(payload, dict):
                raise DataError()
            return payload
        if status == 401:
            raise InvalidApiKeyError()
        if status == 404:
            raise CityNotFoundError(f"\u201c{what}\u201d was not found. Check the spelling or add a country code, e.g. \u201cParis, FR\u201d.")
        if status == 429:
            raise RateLimitError()
        raise ApiError(f"The weather service returned an error (HTTP {status}).")

    def _bundle(self, current_json: Dict[str, Any]) -> WeatherBundle:
        current = parse_current(current_json)
        forecast_json = self._get("forecast", {"lat": current.lat, "lon": current.lon}, current.city)
        entries = parse_forecast(forecast_json, current.sunrise, current.sunset)
        return WeatherBundle(current=current, forecast=entries, fetched_at=datetime.now())

    # ------------------------------------------------------------------ #
    def fetch_by_city(self, city: str) -> WeatherBundle:
        name = (city or "").strip()
        if not name:
            raise CityNotFoundError("Please type a city name to search.")
        return self._bundle(self._get("weather", {"q": name}, name))

    def fetch_by_coords(self, lat: float, lon: float) -> WeatherBundle:
        return self._bundle(self._get("weather", {"lat": lat, "lon": lon}, f"{lat:.2f}, {lon:.2f}"))
