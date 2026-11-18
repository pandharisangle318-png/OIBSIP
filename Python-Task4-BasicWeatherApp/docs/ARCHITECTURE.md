# WeatherDesk – Architecture

```
main.py                     entry point (python main.py)
weatherdesk/
  app.py                    QApplication bootstrap
  config.py                 .env + environment loading (python-dotenv), validation, defaults
  api.py                    WeatherService – OpenWeatherMap calls, HTTP error -> typed exceptions
  location.py               approximate IP geolocation with provider fallback
  workflow.py               load_city / load_current_location (+ default-city fallback), Qt-free
  processing.py             JSON -> models, condition classification, 6-hour & 5-day summaries, labels
  models.py                 dataclasses (CurrentWeather, ForecastEntry, DailyForecast, WeatherBundle)
  errors.py                 user-presentable exception hierarchy
  utils.py                  unit conversion, formatting, local-time helpers
  state.py                  tiny JSON persistence (last city, units, recents)
  workers.py                QRunnable + signals: network work off the GUI thread
  visuals/
    scene.py                animated weather background (QPainter)
    icons.py                vector weather icons, line icons, app icon
  ui/
    main_window.py          layout, request lifecycle, rendering
    widgets.py              glass panel, tiles, sun arc, forecast rows, banner, loading bar...
    theme.py                fonts and global stylesheet
tests/                      unittest-style tests (pytest-compatible) + headless GUI smoke test
```

## Design decisions

* **Layering:** everything except `workers`, `visuals` and `ui` is Qt-free, so all logic is unit-tested without a display.
* **Responsiveness:** every request runs in `QThreadPool`. Each request carries a token; results from superseded
  requests are ignored, so rapid searches can never show stale data.
* **Honest forecast data:** the free API returns 3-hour points. "Next 6 hours" shows the real points inside that
  window; the 5-day view aggregates them per local day (min/max, representative midday condition).
* **Performance:** clouds are pre-rendered pixmaps; rain is one `drawLines` call; particle counts scale with window
  area and are capped; the timer stops when minimised or when FX is off; no `QGraphicsEffect` runs over the
  animated background (text shadows are painted manually).
* **Local time:** every timestamp is converted with the city's UTC offset from the API, not the PC's time zone.
* **Security:** the API key lives only in `.env` / the environment; `.env` is git-ignored; no secrets are packaged.
