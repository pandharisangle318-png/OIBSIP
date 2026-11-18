# WeatherDesk – Premium Edition

A cinematic desktop weather app built with **Python 3.12 + PySide6** using live **OpenWeatherMap** data.
Developed for the **Oasis Infobyte (OIBSIP) Python Programming Internship – Task 4 (Weather App)**.

## 1. Project overview

WeatherDesk shows current conditions, a next-6-hours outlook and a 5-day forecast for any city (or your approximate
location) on top of an animated background that changes with the weather: sunny, partly cloudy, overcast, rainy,
snowy, foggy and stormy, each with a day and a night variant. Everything is drawn in code (no image assets), the
animation runs on a single lightweight 30 fps timer, and all network calls run on a background thread pool so the
window never freezes.

## 2. Features and technologies

**Features**
- City search (with recent-city suggestions) and current-location detection with automatic fallback to a default city
- Temperature in °C / °F (wind switches km/h ↔ mph, visibility km ↔ mi), feels-like, condition and description
- Humidity, wind speed and direction, pressure, visibility, cloud cover
- Sunrise / sunset with a live sun-position arc, and the city's **local** date and time (ticking every second)
- **Next 6 hours** (real 3-hour forecast points) and a **5-day forecast** aggregated from the 3-hour data
- Weather-dependent animated scenes: sun glow, moon and twinkling stars, drifting clouds, rain, snow, fog, lightning
- Glassmorphism panels, vector weather icons, fade-in transitions, hover effects, resizable/scrollable layout
- Loading bar, dismissable error banners, guided first-run API-key setup, auto-refresh (default 10 min), `F5` refresh
- Remembers your last city, units and recent searches

> **Honest data note:** the free OpenWeatherMap forecast API provides data in **3-hour steps**, not hourly.
> WeatherDesk labels it that way and never invents hourly values.

**Technologies:** Python 3.12, PySide6 (Qt 6), Requests, python-dotenv, pytest.

Shortcuts: `Enter` search · `F5` / `Ctrl+R` refresh · `Ctrl+L` focus search box.

## 3. OpenWeatherMap API key setup

1. Create a free account at <https://openweathermap.org/api> and open **My API keys**.
2. Copy your key. *New keys can take up to ~2 hours to activate* – until then the app reports "API key rejected".
3. In the project folder copy `.env.example` to `.env` and set:
   ```
   OPENWEATHER_API_KEY=paste_your_key_here
   ```
The key is only read from `.env` (or an environment variable). It is never hard-coded, and `.env` is git-ignored.
If the key is missing the app opens a setup screen with a **Reload .env** button.

## 4. Windows installation (10 / 11)

**Easiest:** install Python 3.12 from <https://www.python.org/downloads/> (tick *Add python.exe to PATH*),
extract the ZIP, and double-click **`run_weatherdesk.bat`**. It creates a virtual environment, installs the
dependencies, creates `.env` for you to edit (first run only) and starts the app.

**Manual (Command Prompt / PowerShell):**
```bat
cd Python_Task4_WeatherApp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

## 5. Running the application

```bat
.venv\Scripts\activate
python main.py
```

## 6. Running the automated tests

```bat
.venv\Scripts\activate
python -m pytest -v
```
or double-click **`run_tests.bat`**. The suite (API with mocked HTTP, temperature conversion, data processing,
configuration, location fallback, error handling) needs no internet or API key. `tests/test_gui_smoke.py` runs the
window headlessly and is skipped automatically if PySide6 is not installed.
(Without pytest: `python -m unittest discover -s tests -t .`)

## Configuration (.env)

| Variable | Default | Meaning |
|---|---|---|
| `OPENWEATHER_API_KEY` | – | Your API key (required) |
| `WEATHERDESK_DEFAULT_CITY` | Mumbai | Used if location detection fails |
| `WEATHERDESK_UNITS` | C | Starting units, `C` or `F` |
| `WEATHERDESK_TIMEOUT` | 10 | HTTP timeout (seconds, 3–60) |
| `WEATHERDESK_AUTO_REFRESH_MIN` | 10 | Auto-refresh minutes, `0` = off |
| `WEATHERDESK_EFFECTS` | true | Animated effects on/off (also the **FX** button) |

## Privacy

"My location" uses an **approximate IP-based lookup** (ipapi.co, falling back to ip-api.com) – no GPS and no
permission prompts. If it fails, the default city is shown. Last city/units are saved in `%USERPROFILE%\.weatherdesk\state.json`.

## Troubleshooting

| Message | Fix |
|---|---|
| "API key rejected" | Check the key in `.env`; brand-new keys need up to ~2 hours to activate |
| "Can't reach the weather service" | Check your internet connection / firewall, then press **Refresh** |
| "City not found" | Check spelling or add a country code, e.g. `Paris, FR` |
| High CPU on a weak PC | Click **FX** to turn the animated effects off |

## Project structure

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Entry point: `main.py`. Suggested GitHub folder name: `Python_Task4_WeatherApp`.

## License

MIT – see `LICENSE`.
