"""Approximate, IP-based location detection with a provider fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .errors import LocationError


@dataclass(frozen=True)
class GeoLocation:
    lat: float
    lon: float
    city: str
    country: str


def _parse_ipapi_co(data: Dict[str, Any]) -> GeoLocation:
    if data.get("error"):
        raise ValueError(data.get("reason", "error"))
    return GeoLocation(float(data["latitude"]), float(data["longitude"]),
                       str(data.get("city") or ""), str(data.get("country_code") or ""))


def _parse_ip_api_com(data: Dict[str, Any]) -> GeoLocation:
    if data.get("status") != "success":
        raise ValueError(data.get("message", "failed"))
    return GeoLocation(float(data["lat"]), float(data["lon"]),
                       str(data.get("city") or ""), str(data.get("countryCode") or ""))


PROVIDERS: List[Tuple[str, Callable[[Dict[str, Any]], GeoLocation]]] = [
    ("https://ipapi.co/json/", _parse_ipapi_co),
    ("http://ip-api.com/json/", _parse_ip_api_com),
]


def detect_location(session: Optional[requests.Session] = None, timeout: float = 6.0) -> GeoLocation:
    """Return an approximate location, trying each provider in turn."""
    http = session or requests
    for url, parser in PROVIDERS:
        try:
            response = http.get(url, timeout=timeout)
            if response.status_code != 200:
                continue
            return parser(response.json())
        except (requests.exceptions.RequestException, ValueError, KeyError, TypeError):
            continue
    raise LocationError("Couldn't detect your location automatically (are you offline?).")
