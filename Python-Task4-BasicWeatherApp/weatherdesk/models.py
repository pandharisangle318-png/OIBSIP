"""Plain data containers shared by the service, processing and GUI layers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional, Tuple


class Condition(str, Enum):
    CLEAR = "clear"
    PARTLY = "partly"
    CLOUDS = "clouds"
    RAIN = "rain"
    SNOW = "snow"
    FOG = "fog"
    STORM = "storm"


@dataclass(frozen=True)
class CurrentWeather:
    city: str
    country: str
    lat: float
    lon: float
    temp_c: float
    feels_like_c: float
    humidity: int
    pressure_hpa: int
    wind_ms: float
    wind_deg: Optional[int]
    visibility_m: Optional[int]
    cloudiness: int
    main: str
    description: str
    condition: Condition
    is_night: bool
    observed_at: datetime      # timezone-aware, in the city's local time
    sunrise: datetime          # timezone-aware, city-local
    sunset: datetime           # timezone-aware, city-local
    utc_offset: int            # seconds east of UTC


@dataclass(frozen=True)
class ForecastEntry:
    """One OpenWeatherMap forecast point. The free API provides 3-hour steps."""

    time: datetime             # timezone-aware, city-local
    temp_c: float
    condition: Condition
    description: str
    is_night: bool
    pop: float                 # probability of precipitation, 0..1


@dataclass(frozen=True)
class DailyForecast:
    day: date
    temp_min_c: float
    temp_max_c: float
    condition: Condition
    description: str
    pop_max: float


@dataclass(frozen=True)
class WeatherBundle:
    current: CurrentWeather
    forecast: Tuple[ForecastEntry, ...]
    fetched_at: datetime       # system-local time of the request
