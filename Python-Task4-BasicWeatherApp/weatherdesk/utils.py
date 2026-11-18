"""Small, dependency-free helpers (unit conversion, formatting, time)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

CELSIUS = "C"
FAHRENHEIT = "F"

_COMPASS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def round_half_up(value: float) -> int:
    """Round .5 away from zero (Python's round() uses banker's rounding)."""
    return int(math.floor(abs(value) + 0.5)) * (1 if value >= 0 else -1)


def c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def f_to_c(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0


def convert_temp(celsius: float, units: str) -> float:
    return c_to_f(celsius) if units == FAHRENHEIT else celsius


def format_temp(celsius: float, units: str = CELSIUS) -> str:
    value = round_half_up(convert_temp(celsius, units))
    if value == 0:
        value = 0  # avoid "-0"
    return f"{value}\u00b0"


def ms_to_kmh(ms: float) -> float:
    return ms * 3.6


def ms_to_mph(ms: float) -> float:
    return ms * 2.236936


def format_wind(ms: float, units: str = CELSIUS) -> str:
    if units == FAHRENHEIT:
        return f"{round_half_up(ms_to_mph(ms))} mph"
    return f"{round_half_up(ms_to_kmh(ms))} km/h"


def compass_direction(degrees: Optional[float]) -> str:
    if degrees is None:
        return ""
    return _COMPASS[int((degrees % 360) / 22.5 + 0.5) % 16]


def format_visibility(meters: Optional[float], units: str = CELSIUS) -> str:
    if meters is None:
        return "n/a"
    if units == FAHRENHEIT:
        miles = meters / 1609.344
        return f"{miles:.0f} mi" if miles >= 10 else f"{miles:.1f} mi".replace(".0 mi", " mi")
    km = meters / 1000.0
    return f"{km:.0f} km" if km >= 10 or abs(km - round(km)) < 0.05 else f"{km:.1f} km"


def format_coords(lat: float, lon: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}\u00b0 {ns}, {abs(lon):.2f}\u00b0 {ew}"


def local_now(utc_offset: int, utc_now: Optional[datetime] = None) -> datetime:
    """Current time at a place whose UTC offset (seconds) is given."""
    base = utc_now if utc_now is not None else datetime.now(timezone.utc)
    return base.astimezone(timezone(timedelta(seconds=int(utc_offset))))


def format_clock(dt: datetime) -> str:
    return f"{dt:%A}, {dt.day} {dt:%B}   \u00b7   {dt:%H:%M}"


def format_hm(dt: datetime) -> str:
    return f"{dt:%H:%M}"


def minutes_of_day(dt: datetime) -> float:
    return dt.hour * 60 + dt.minute + dt.second / 60.0


def format_duration(minutes: float) -> str:
    total = max(0, int(round(minutes)))
    return f"{total // 60}h {total % 60:02d}m"


def sentence_case(text: str) -> str:
    text = (text or "").strip()
    return text[:1].upper() + text[1:] if text else ""
