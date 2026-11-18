"""Exception types. Every message is written to be shown directly to the user."""
from __future__ import annotations


class WeatherError(Exception):
    """Base class for all expected, user-presentable errors."""

    title = "Something went wrong"
    default_message = "An unexpected problem occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class MissingApiKeyError(WeatherError):
    title = "API key needed"
    default_message = "No OpenWeatherMap API key found. Add OPENWEATHER_API_KEY to your .env file."


class InvalidApiKeyError(WeatherError):
    title = "API key rejected"
    default_message = (
        "OpenWeatherMap rejected the API key. Check the key in your .env file. "
        "Newly created keys can take up to a couple of hours to activate."
    )


class CityNotFoundError(WeatherError):
    title = "City not found"
    default_message = "That city was not found. Check the spelling or add a country code, e.g. \u201cParis, FR\u201d."


class NetworkError(WeatherError):
    title = "No connection"
    default_message = "Can't reach the weather service. Check your internet connection and try again."


class RateLimitError(WeatherError):
    title = "Too many requests"
    default_message = "The weather service is rate-limiting requests. Please wait a minute and try again."


class ApiError(WeatherError):
    title = "Weather service error"
    default_message = "The weather service returned an unexpected error."


class DataError(WeatherError):
    title = "Unreadable data"
    default_message = "The weather service returned data WeatherDesk couldn't understand."


class LocationError(WeatherError):
    title = "Location unavailable"
    default_message = "Couldn't detect your location automatically."
