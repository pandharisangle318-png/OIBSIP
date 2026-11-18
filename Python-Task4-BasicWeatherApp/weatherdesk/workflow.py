"""High-level load operations used by the GUI (kept Qt-free so they are testable)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .api import WeatherService
from .errors import LocationError
from .location import GeoLocation, detect_location
from .models import WeatherBundle


@dataclass(frozen=True)
class LoadResult:
    bundle: WeatherBundle
    note: Optional[str] = None      # informational message to show the user
    located: bool = False           # True when the coordinates came from auto-detection


def load_city(service: WeatherService, city: str) -> LoadResult:
    return LoadResult(service.fetch_by_city(city))


def load_coords(service: WeatherService, lat: float, lon: float) -> LoadResult:
    return LoadResult(service.fetch_by_coords(lat, lon), located=True)


def load_current_location(service: WeatherService, default_city: str,
                          detector: Callable[[], GeoLocation] = detect_location) -> LoadResult:
    """Detect the user's location; fall back to the default city if that fails."""
    try:
        place = detector()
    except LocationError:
        bundle = service.fetch_by_city(default_city)
        return LoadResult(bundle, note=f"Couldn't detect your location, so showing {bundle.current.city} instead. "
                                       "Search for any city above.")
    return LoadResult(service.fetch_by_coords(place.lat, place.lon), located=True)
