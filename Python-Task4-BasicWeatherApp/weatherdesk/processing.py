"""Turns raw OpenWeatherMap JSON into typed models and display summaries."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .errors import DataError
from .models import (Condition, CurrentWeather, DailyForecast, ForecastEntry)
from .utils import minutes_of_day


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify_condition(weather_id: int) -> Condition:
    """Map an OpenWeatherMap condition id to a visual category."""
    wid = int(weather_id)
    if 200 <= wid < 300:
        return Condition.STORM
    if 300 <= wid < 600:
        return Condition.RAIN
    if 600 <= wid < 700:
        return Condition.SNOW
    if wid in (771, 781):
        return Condition.STORM
    if 700 <= wid < 800:
        return Condition.FOG
    if wid == 800:
        return Condition.CLEAR
    if wid in (801, 802):
        return Condition.PARTLY
    return Condition.CLOUDS


def is_night_at(local_time: datetime, sunrise: datetime, sunset: datetime) -> bool:
    """Night test by time-of-day, so it also works for forecast days ahead."""
    t, sr, ss = minutes_of_day(local_time), minutes_of_day(sunrise), minutes_of_day(sunset)
    if sr < ss:
        return t < sr or t >= ss
    return ss <= t < sr


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _tz(offset_seconds: Any) -> timezone:
    return timezone(timedelta(seconds=int(offset_seconds or 0)))


def parse_current(data: Dict[str, Any]) -> CurrentWeather:
    try:
        tz = _tz(data.get("timezone", 0))
        weather = data["weather"][0]
        main = data["main"]
        sys_ = data.get("sys") or {}
        wind = data.get("wind") or {}
        observed = datetime.fromtimestamp(int(data["dt"]), tz)
        if "sunrise" in sys_ and "sunset" in sys_:
            sunrise = datetime.fromtimestamp(int(sys_["sunrise"]), tz)
            sunset = datetime.fromtimestamp(int(sys_["sunset"]), tz)
        else:  # polar regions: sensible placeholders keep the UI working
            sunrise = observed.replace(hour=6, minute=0, second=0, microsecond=0)
            sunset = observed.replace(hour=18, minute=0, second=0, microsecond=0)
        visibility = data.get("visibility")
        wind_deg = wind.get("deg")
        return CurrentWeather(
            city=str(data.get("name") or "Unknown location"),
            country=str(sys_.get("country") or ""),
            lat=float(data["coord"]["lat"]),
            lon=float(data["coord"]["lon"]),
            temp_c=float(main["temp"]),
            feels_like_c=float(main.get("feels_like", main["temp"])),
            humidity=int(main["humidity"]),
            pressure_hpa=int(main["pressure"]),
            wind_ms=float(wind.get("speed", 0.0)),
            wind_deg=int(wind_deg) if wind_deg is not None else None,
            visibility_m=int(visibility) if visibility is not None else None,
            cloudiness=int((data.get("clouds") or {}).get("all", 0)),
            main=str(weather.get("main", "")),
            description=str(weather.get("description", "")),
            condition=classify_condition(weather["id"]),
            is_night=is_night_at(observed, sunrise, sunset),
            observed_at=observed,
            sunrise=sunrise,
            sunset=sunset,
            utc_offset=int(tz.utcoffset(None).total_seconds()),
        )
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise DataError() from exc


def parse_forecast(data: Dict[str, Any], sunrise: datetime, sunset: datetime) -> Tuple[ForecastEntry, ...]:
    try:
        items = data["list"]
        tz = _tz((data.get("city") or {}).get("timezone", sunrise.utcoffset().total_seconds()))
    except (KeyError, TypeError, AttributeError) as exc:
        raise DataError() from exc

    entries: List[ForecastEntry] = []
    for item in items:
        try:
            when = datetime.fromtimestamp(int(item["dt"]), tz)
            weather = item["weather"][0]
            pod = (item.get("sys") or {}).get("pod")
            night = (pod == "n") if pod in ("d", "n") else is_night_at(when, sunrise, sunset)
            entries.append(ForecastEntry(
                time=when,
                temp_c=float(item["main"]["temp"]),
                condition=classify_condition(weather["id"]),
                description=str(weather.get("description", "")),
                is_night=night,
                pop=float(item.get("pop", 0.0) or 0.0),
            ))
        except (KeyError, IndexError, TypeError, ValueError):
            continue  # skip a malformed interval rather than failing the whole forecast
    if not entries:
        raise DataError()
    entries.sort(key=lambda e: e.time)
    return tuple(entries)


# --------------------------------------------------------------------------- #
# Forecast summaries
# --------------------------------------------------------------------------- #
def six_hour_outlook(entries: Iterable[ForecastEntry], now: datetime, hours: int = 6) -> List[ForecastEntry]:
    """Forecast intervals covering roughly the next six hours.

    The free API only has 3-hour steps, so this returns real 3-hour data
    points (usually two or three) and never invents hourly values.
    """
    upcoming = [e for e in entries if e.time >= now - timedelta(minutes=30)]
    window = [e for e in upcoming if e.time <= now + timedelta(hours=hours)]
    return window if len(window) >= 2 else upcoming[:2]


def daily_summary(entries: Iterable[ForecastEntry], days: int = 5) -> List[DailyForecast]:
    """Aggregate 3-hour points into per-day min/max and a representative condition."""
    grouped: Dict[Any, List[ForecastEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.time.date()].append(entry)

    result: List[DailyForecast] = []
    for day in sorted(grouped)[:days]:
        group = grouped[day]
        rep = min(group, key=lambda e: abs(e.time.hour * 60 + e.time.minute - 13 * 60))
        result.append(DailyForecast(
            day=day,
            temp_min_c=min(e.temp_c for e in group),
            temp_max_c=max(e.temp_c for e in group),
            condition=rep.condition,
            description=rep.description,
            pop_max=max(e.pop for e in group),
        ))
    return result


# --------------------------------------------------------------------------- #
# Human-readable descriptors for the metric tiles
# --------------------------------------------------------------------------- #
def humidity_label(percent: int) -> str:
    if percent < 30:
        return "Dry air"
    if percent < 60:
        return "Comfortable"
    if percent < 80:
        return "Humid"
    return "Very humid"


def pressure_label(hpa: int) -> str:
    if hpa < 1009:
        return "Low"
    if hpa > 1022:
        return "High"
    return "Normal"


def visibility_label(meters: Optional[int]) -> str:
    if meters is None:
        return "No data"
    if meters >= 8000:
        return "Excellent"
    if meters >= 4000:
        return "Good"
    if meters >= 1000:
        return "Reduced"
    return "Poor"


def cloud_label(percent: int) -> str:
    if percent < 20:
        return "Clear skies"
    if percent < 60:
        return "Partly cloudy"
    if percent < 90:
        return "Mostly cloudy"
    return "Overcast"


def feels_like_label(actual_c: float, feels_c: float) -> str:
    diff = feels_c - actual_c
    if diff >= 1.5:
        return "Warmer than actual"
    if diff <= -1.5:
        return "Cooler than actual"
    return "Close to actual"
