"""Loads the precomputed datasets once at startup.

The API never calls Elexon at request time. Ingestion runs separately
(see scripts/ingest.py) and this module just reads its output, from
DATA_DIR if set, otherwise the bundled copy in api/data, falling back
to the repo's data/processed folder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[1] / "data",  # api/data, bundled with the backend
    _HERE.parents[2] / "data" / "processed",  # repo-level data/processed
]
_DEFAULT_DIR = next((p for p in _CANDIDATES if (p / "days.json").exists()), _CANDIDATES[0])


class Store:
    def __init__(self, data_dir: Path | None = None) -> None:
        directory = data_dir or Path(os.environ.get("DATA_DIR", _DEFAULT_DIR))
        with open(directory / "days.json") as fh:
            self.days: list[dict] = json.load(fh)
        with open(directory / "summary.json") as fh:
            self.summary: dict = json.load(fh)
        self._by_date = {day["date"]: day for day in self.days}

    def day(self, day_date: str) -> dict | None:
        return self._by_date.get(day_date)

    def day_summaries(self) -> list[dict]:
        return [
            {
                "date": day["date"],
                "decisionDate": day["decisionDate"],
                "mae": day["stats"]["mae"],
                "bias": day["stats"]["bias"],
                "pctOver": day["stats"]["pctOver"],
                "meanForecast": round(
                    sum(h["forecast"] for h in day["hours"]) / len(day["hours"]), 1
                ),
                "meanActual": round(
                    sum(h["actual"] for h in day["hours"]) / len(day["hours"]), 1
                ),
            }
            for day in self.days
        ]
