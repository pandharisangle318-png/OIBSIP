"""Tiny persistent user state (last city, units, recent searches)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

DEFAULT_STATE_PATH = Path.home() / ".weatherdesk" / "state.json"
MAX_RECENT = 6


@dataclass
class AppState:
    last_city: str = ""
    units: str = ""
    recent: List[str] = field(default_factory=list)


def add_recent(recent: List[str], city: str, limit: int = MAX_RECENT) -> List[str]:
    city = city.strip()
    if not city:
        return list(recent)
    kept = [c for c in recent if c.casefold() != city.casefold()]
    return ([city] + kept)[:limit]


def load_state(path: Optional[Path] = None) -> AppState:
    target = Path(path) if path else DEFAULT_STATE_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        recent = [str(x) for x in raw.get("recent", []) if str(x).strip()][:MAX_RECENT]
        units = str(raw.get("units", "")).upper()
        return AppState(str(raw.get("last_city", "")), units if units in ("C", "F") else "", recent)
    except (OSError, ValueError, AttributeError, TypeError):
        return AppState()


def save_state(state: AppState, path: Optional[Path] = None) -> None:
    target = Path(path) if path else DEFAULT_STATE_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"last_city": state.last_city, "units": state.units,
                                      "recent": state.recent}, indent=2), encoding="utf-8")
    except OSError:
        pass  # persistence is a convenience; never crash because of it
