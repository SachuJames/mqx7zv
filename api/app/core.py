"""Decision-time dataset building and forecast accuracy metrics.

Everything here works off two raw Elexon series:

- FUELHH actuals, half-hourly, filtered to fuelType WIND
- WINDFOR forecasts, hourly, many publishes per forecast hour

The one rule that shapes the module: a forecast only counts if it was
published at or before the decision cutoff for its delivery day. The
cutoff is the N2EX day-ahead gate closure, 09:50 GMT on the day before
the settlement day starts.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone

UTC = timezone.utc
GATE_CLOSURE = time(9, 50)  # N2EX day-ahead auction, GMT


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def decision_cutoff(settlement_day: date) -> datetime:
    """Moment the buying decision for a settlement day is locked in.

    The settlement day starts at 23:00 GMT on the previous calendar day,
    and the day-ahead auction for it closes at 09:50 GMT that same
    previous day.
    """
    day_before = settlement_day - timedelta(days=1)
    return datetime.combine(day_before, GATE_CLOSURE, tzinfo=UTC)


def settlement_hours(settlement_day: date) -> list[datetime]:
    start = datetime.combine(
        settlement_day - timedelta(days=1), time(23, 0), tzinfo=UTC
    )
    return [start + timedelta(hours=i) for i in range(24)]


def hourly_actuals(fuelhh_rows: list[dict]) -> dict[datetime, float]:
    """Collapse half-hourly WIND rows to hourly means.

    FUELHH generation is MW over a half-hour period, so the hourly figure
    is the mean of the two half hours, not the sum. Hours missing either
    half are dropped rather than guessed.
    """
    halves: dict[datetime, list[float]] = {}
    for row in fuelhh_rows:
        if row.get("fuelType") != "WIND":
            continue
        start = parse_ts(row["startTime"])
        hour = start.replace(minute=0, second=0, microsecond=0)
        halves.setdefault(hour, []).append(float(row["generation"]))
    return {
        hour: sum(values) / 2
        for hour, values in halves.items()
        if len(values) == 2
    }


def index_forecasts(windfor_rows: list[dict]) -> dict[datetime, list[tuple[datetime, float]]]:
    """Group forecast points by target hour, sorted by publish time."""
    by_start: dict[datetime, list[tuple[datetime, float]]] = {}
    for row in windfor_rows:
        start = parse_ts(row["startTime"])
        publish = parse_ts(row["publishTime"])
        by_start.setdefault(start, []).append((publish, float(row["generation"])))
    for points in by_start.values():
        points.sort()
    return by_start


def decision_forecast(
    points: list[tuple[datetime, float]], cutoff: datetime
) -> tuple[datetime, float] | None:
    """Latest forecast published at or before the cutoff, if any.

    Points must be sorted by publish time. Anything published after the
    cutoff is information the desk did not have, so it never counts.
    """
    chosen = None
    for publish, generation in points:
        if publish > cutoff:
            break
        chosen = (publish, generation)
    return chosen


def quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("quantile of empty series")
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def error_stats(errors: list[float]) -> dict:
    """Summary stats for a list of signed errors (forecast minus actual)."""
    n = len(errors)
    if n == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "pctOver": None}
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    bias = sum(errors) / n
    pct_over = 100.0 * sum(1 for e in errors if e > 0) / n
    return {
        "n": n,
        "mae": round(mae, 1),
        "rmse": round(rmse, 1),
        "bias": round(bias, 1),
        "pctOver": round(pct_over, 1),
    }


def horizon_bucket(hours_ahead: float) -> str:
    lo = int(hours_ahead // 6) * 6
    return f"{lo}-{lo + 6}h"


def build_day(
    settlement_day: date,
    actuals: dict[datetime, float],
    forecasts: dict[datetime, list[tuple[datetime, float]]],
) -> dict | None:
    """Decision-time record for one settlement day, hours joined to actuals."""
    cutoff = decision_cutoff(settlement_day)
    hours = []
    for start in settlement_hours(settlement_day):
        if start not in actuals:
            continue
        points = forecasts.get(start, [])
        picked = decision_forecast(points, cutoff)
        if picked is None:
            continue
        publish, generation = picked
        actual = actuals[start]
        hours.append(
            {
                "startTime": start.isoformat().replace("+00:00", "Z"),
                "hourUtc": start.hour,
                "forecast": generation,
                "actual": round(actual, 1),
                "error": round(generation - actual, 1),
                "publishTime": publish.isoformat().replace("+00:00", "Z"),
                "horizonHours": round((start - publish).total_seconds() / 3600, 1),
                "_publish": publish,
                "_start": start,
            }
        )
    if not hours:
        return None

    evolution = build_evolution(settlement_day, forecasts, cutoff)
    errors = [h["error"] for h in hours]
    stats = error_stats(errors)
    shortfall = round(sum(e for e in errors if e > 0))
    surplus = round(-sum(e for e in errors if e < 0))
    day = {
        "date": settlement_day.isoformat(),
        "decisionDate": (settlement_day - timedelta(days=1)).isoformat(),
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "hours": hours,
        "evolution": evolution,
        "stats": stats,
        "shortfallMwh": shortfall,
        "surplusMwh": surplus,
        "takeaway": takeaway(stats, shortfall, surplus),
    }
    return day


def build_evolution(
    settlement_day: date,
    forecasts: dict[datetime, list[tuple[datetime, float]]],
    cutoff: datetime,
) -> list[dict]:
    """How the day's forecast moved across publishes up to the cutoff.

    One entry per publish that covers most of the settlement day, holding
    the mean forecast for the day plus the hourly values.
    """
    hours = settlement_hours(settlement_day)
    publishes: dict[datetime, dict[datetime, float]] = {}
    for start in hours:
        for publish, generation in forecasts.get(start, []):
            if publish > cutoff:
                break
            publishes.setdefault(publish, {})[start] = generation
    evolution = []
    for publish in sorted(publishes):
        values = publishes[publish]
        if len(values) < 20:
            continue
        ordered = [values[h] for h in hours if h in values]
        evolution.append(
            {
                "publishTime": publish.isoformat().replace("+00:00", "Z"),
                "meanForecast": round(sum(ordered) / len(ordered), 1),
                "hourly": ordered,
            }
        )
    return evolution


def takeaway(stats: dict, shortfall: int, surplus: int) -> str:
    bias = stats["bias"]
    if bias is None:
        return "No decision-time forecast overlap for this day."
    direction = "below" if bias > 0 else "above"
    return (
        f"Wind came in {abs(bias):,.0f} MW {direction} the day-ahead forecast "
        f"on average. Buying on the raw forecast left the desk roughly "
        f"{shortfall:,} MWh short and {surplus:,} MWh long across the day."
    )


def build_summary(days: list[dict], actuals: dict[datetime, float]) -> dict:
    """January-wide metrics across all decision days."""
    all_hours = [h for day in days for h in day["hours"]]
    errors = [h["error"] for h in all_hours]
    stats = error_stats(errors)

    sorted_errors = sorted(errors)
    q10 = quantile(sorted_errors, 0.10)
    q90 = quantile(sorted_errors, 0.90)
    bias = stats["bias"] or 0.0

    by_horizon: dict[str, list[float]] = {}
    by_hour: dict[int, list[float]] = {}
    for h in all_hours:
        by_horizon.setdefault(horizon_bucket(h["horizonHours"]), []).append(h["error"])
        by_hour.setdefault(h["hourUtc"], []).append(h["error"])

    # Persistence baseline: yesterday's actual at the same hour, which is
    # what a desk with no forecast at all would fall back on.
    persistence_errors = []
    for h in all_hours:
        prev = h["_start"] - timedelta(hours=24)
        if prev in actuals:
            persistence_errors.append(actuals[prev] - h["actual"])
    persistence = error_stats(persistence_errors)
    skill = None
    if persistence["mae"]:
        skill = round(1 - stats["mae"] / persistence["mae"], 3)

    # What the numbers would have looked like with the bias removed.
    corrected = error_stats([e - bias for e in errors])

    bins: dict[int, int] = {}
    for e in errors:
        edge = int(math.floor(e / 1000.0)) * 1000
        bins[edge] = bins.get(edge, 0) + 1
    distribution = [
        {"binStart": edge, "count": bins[edge]} for edge in sorted(bins)
    ]

    worst = sorted(
        (
            {
                "date": day["date"],
                "mae": day["stats"]["mae"],
                "bias": day["stats"]["bias"],
            }
            for day in days
        ),
        key=lambda d: d["mae"],
        reverse=True,
    )[:8]

    return {
        "stats": stats,
        "meanForecast": round(
            sum(h["forecast"] for h in all_hours) / len(all_hours), 1
        ),
        "meanActual": round(
            sum(h["actual"] for h in all_hours) / len(all_hours), 1
        ),
        "errorQuantiles": {"p10": round(q10, 1), "p90": round(q90, 1)},
        "biasCorrectedMae": corrected["mae"],
        "byHorizon": [
            {"bucket": bucket, **error_stats(errs)}
            for bucket, errs in sorted(
                by_horizon.items(), key=lambda kv: int(kv[0].split("-")[0])
            )
        ],
        "byHourOfDay": [
            {"hourUtc": hour, **error_stats(by_hour[hour])}
            for hour in sorted(by_hour)
        ],
        "distribution": distribution,
        "worstDays": worst,
        "persistence": persistence,
        "skillVsPersistence": skill,
        "totalShortfallMwh": sum(d["shortfallMwh"] for d in days),
        "totalSurplusMwh": sum(d["surplusMwh"] for d in days),
    }
