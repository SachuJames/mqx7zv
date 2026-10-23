"""Pull the January 2026 decision window from Elexon and precompute the app data.

Raw responses are cached under data/raw as gzipped JSON so the build can be
re-run offline. Processed output lands in data/processed:

- days.json: one decision-time record per settlement day
- summary.json: January accuracy metrics

Run from the repo root:  python api/scripts/ingest.py [--offline]
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import build_day, build_summary, hourly_actuals, index_forecasts

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_DIR = REPO_ROOT / "data" / "processed"

# Decisions made Jan 1-31 2026 buy for settlement days Jan 2 to Feb 1.
# Fetch windows are wider than that on both sides: forecasts for a
# delivery hour are published up to three days ahead, and the
# persistence baseline needs the previous day's actuals.
WINDFOR_WINDOW = (datetime(2025, 12, 29, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc))
FUELHH_WINDOW = (datetime(2025, 12, 30, tzinfo=timezone.utc), datetime(2026, 2, 3, tzinfo=timezone.utc))
DECISION_DAYS = [date(2026, 1, d) for d in range(1, 32)]


def fetch_stream(dataset: str, start: datetime, end: datetime, chunk_days: int) -> list[dict]:
    rows: list[dict] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        url = (
            f"{BASE}/{dataset}/stream"
            f"?publishDateTimeFrom={cursor.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f"&publishDateTimeTo={chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        )
        with urllib.request.urlopen(url, timeout=60) as resp:
            rows.extend(json.loads(resp.read().decode()))
        cursor = chunk_end
    return rows


def dedupe(rows: list[dict], extra_key: str | None = None) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for row in rows:
        key = (row["publishTime"], row["startTime"]) + (
            (row[extra_key],) if extra_key else ()
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def load_or_fetch(name: str, dataset: str, window, chunk_days: int, offline: bool, extra_key=None) -> list[dict]:
    cache = RAW_DIR / name
    if offline:
        with gzip.open(cache, "rt") as fh:
            return json.load(fh)
    rows = dedupe(fetch_stream(dataset, window[0], window[1], chunk_days), extra_key)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(cache, "wt") as fh:
        json.dump(rows, fh)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="rebuild from the raw cache only")
    args = parser.parse_args()

    fuelhh = load_or_fetch("fuelhh.json.gz", "FUELHH", FUELHH_WINDOW, 5, args.offline, "fuelType")
    windfor = load_or_fetch("windfor.json.gz", "WINDFOR", WINDFOR_WINDOW, 4, args.offline)
    print(f"raw rows: FUELHH {len(fuelhh)}, WINDFOR {len(windfor)}")

    actuals = hourly_actuals(fuelhh)
    forecasts = index_forecasts(windfor)

    days = []
    for decision_day in DECISION_DAYS:
        settlement_day = decision_day + timedelta(days=1)
        day = build_day(settlement_day, actuals, forecasts)
        if day is None:
            print(f"warning: no data for settlement day {settlement_day}")
            continue
        days.append(day)

    summary = build_summary(days, actuals)

    # Bias correction and band come from the whole month's decision-time
    # errors, so they are applied in a second pass once the summary exists.
    bias = summary["stats"]["bias"]
    q10 = summary["errorQuantiles"]["p10"]
    q90 = summary["errorQuantiles"]["p90"]
    for day in days:
        for hour in day["hours"]:
            hour["corrected"] = round(hour["forecast"] - bias, 1)
            # actual = forecast - error, so the band flips the quantiles
            hour["bandLow"] = round(hour["forecast"] - q90, 1)
            hour["bandHigh"] = round(hour["forecast"] - q10, 1)
            del hour["_publish"], hour["_start"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "days.json", "w") as fh:
        json.dump(days, fh)
    with open(OUT_DIR / "summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    s = summary["stats"]
    print(f"days built: {len(days)}")
    print(
        f"headline: n={s['n']} MAE={s['mae']} RMSE={s['rmse']} "
        f"bias={s['bias']:+} pctOver={s['pctOver']}%"
    )
    print(
        f"persistence MAE={summary['persistence']['mae']} "
        f"skill={summary['skillVsPersistence']}"
    )


if __name__ == "__main__":
    main()
