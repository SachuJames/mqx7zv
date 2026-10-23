import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import (
    build_day,
    build_summary,
    decision_cutoff,
    decision_forecast,
    error_stats,
    hourly_actuals,
    index_forecasts,
    settlement_hours,
)

UTC = timezone.utc


def ts(day: int, hour: int, minute: int = 0) -> str:
    return f"2026-01-{day:02d}T{hour:02d}:{minute:02d}:00Z"


def fuelhh_row(day: int, hour: int, minute: int, generation: float, fuel: str = "WIND") -> dict:
    return {
        "startTime": ts(day, hour, minute),
        "publishTime": ts(day, hour, minute),
        "fuelType": fuel,
        "generation": generation,
    }


def windfor_row(publish: str, start: str, generation: float) -> dict:
    return {"publishTime": publish, "startTime": start, "generation": generation}


class TestHourlyJoin:
    def test_half_hours_are_averaged_not_summed(self):
        rows = [fuelhh_row(2, 10, 0, 1000), fuelhh_row(2, 10, 30, 1400)]
        actuals = hourly_actuals(rows)
        assert actuals[datetime(2026, 1, 2, 10, tzinfo=UTC)] == 1200

    def test_other_fuels_ignored(self):
        rows = [
            fuelhh_row(2, 10, 0, 1000),
            fuelhh_row(2, 10, 30, 1000),
            fuelhh_row(2, 10, 0, 9999, fuel="CCGT"),
            fuelhh_row(2, 10, 30, 9999, fuel="CCGT"),
        ]
        actuals = hourly_actuals(rows)
        assert actuals[datetime(2026, 1, 2, 10, tzinfo=UTC)] == 1000

    def test_incomplete_hour_dropped(self):
        rows = [fuelhh_row(2, 10, 0, 1000)]
        assert hourly_actuals(rows) == {}


class TestNoLookAhead:
    def points(self):
        rows = [
            windfor_row(ts(1, 7, 30), ts(2, 12), 5000),
            windfor_row(ts(1, 9, 30), ts(2, 12), 6000),
            # Published after the gate closed. It happens to be spot on,
            # which is exactly why it must never be used.
            windfor_row(ts(1, 11, 30), ts(2, 12), 6100),
            windfor_row(ts(2, 2, 30), ts(2, 12), 6200),
        ]
        indexed = index_forecasts(rows)
        return indexed[datetime(2026, 1, 2, 12, tzinfo=UTC)]

    def test_latest_at_or_before_cutoff_wins(self):
        cutoff = decision_cutoff(date(2026, 1, 2))
        publish, generation = decision_forecast(self.points(), cutoff)
        assert generation == 6000
        assert publish == datetime(2026, 1, 1, 9, 30, tzinfo=UTC)

    def test_publish_exactly_at_cutoff_counts(self):
        points = [(datetime(2026, 1, 1, 9, 50, tzinfo=UTC), 7000.0)]
        cutoff = decision_cutoff(date(2026, 1, 2))
        assert decision_forecast(points, cutoff) == (points[0][0], 7000.0)

    def test_nothing_before_cutoff_returns_none(self):
        points = [(datetime(2026, 1, 1, 11, 30, tzinfo=UTC), 7000.0)]
        cutoff = decision_cutoff(date(2026, 1, 2))
        assert decision_forecast(points, cutoff) is None

    def test_built_day_never_uses_post_cutoff_forecast(self):
        settlement_day = date(2026, 1, 3)
        actual_rows = []
        forecast_rows = []
        for start in settlement_hours(settlement_day):
            d, h = start.day, start.hour
            actual_rows.append(fuelhh_row(d, h, 0, 4000))
            actual_rows.append(fuelhh_row(d, h, 30, 4000))
            start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
            # decision-time forecast
            forecast_rows.append(windfor_row("2026-01-02T09:30:00Z", start_str, 5000))
            # later revision, closer to the actual on purpose
            forecast_rows.append(windfor_row("2026-01-02T22:30:00Z", start_str, 4100))
        day = build_day(settlement_day, hourly_actuals(actual_rows), index_forecasts(forecast_rows))
        assert day is not None
        assert all(h["forecast"] == 5000 for h in day["hours"])
        assert all(
            e["publishTime"] <= day["cutoff"] for e in day["evolution"]
        )


class TestMetrics:
    def test_error_stats(self):
        stats = error_stats([100.0, -50.0, 200.0])
        assert stats["n"] == 3
        assert stats["mae"] == round((100 + 50 + 200) / 3, 1)
        assert stats["bias"] == round(250 / 3, 1)
        assert stats["pctOver"] == 66.7

    def test_error_stats_empty(self):
        stats = error_stats([])
        assert stats["n"] == 0
        assert stats["mae"] is None

    def test_summary_skill_against_persistence(self):
        # Forecast nails every hour; persistence repeats a wrong yesterday,
        # so skill should come out at 1.0.
        settlement_day = date(2026, 1, 3)
        actual_rows = []
        forecast_rows = []
        for start in settlement_hours(settlement_day):
            d, h = start.day, start.hour
            actual_rows.append(fuelhh_row(d, h, 0, 4000))
            actual_rows.append(fuelhh_row(d, h, 30, 4000))
            start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
            forecast_rows.append(windfor_row("2026-01-02T09:30:00Z", start_str, 4000))
        prev_day = date(2026, 1, 2)
        for start in settlement_hours(prev_day):
            d, h = start.day, start.hour
            actual_rows.append(fuelhh_row(d, h, 0, 6000))
            actual_rows.append(fuelhh_row(d, h, 30, 6000))
        actuals = hourly_actuals(actual_rows)
        day = build_day(settlement_day, actuals, index_forecasts(forecast_rows))
        summary = build_summary([day], actuals)
        assert summary["stats"]["mae"] == 0
        assert summary["persistence"]["mae"] == 2000
        assert summary["skillVsPersistence"] == 1.0


class TestSettlementDay:
    def test_cutoff_is_0950_day_before(self):
        cutoff = decision_cutoff(date(2026, 1, 16))
        assert cutoff == datetime(2026, 1, 15, 9, 50, tzinfo=UTC)

    def test_settlement_day_runs_2300_to_2300(self):
        hours = settlement_hours(date(2026, 1, 16))
        assert len(hours) == 24
        assert hours[0] == datetime(2026, 1, 15, 23, tzinfo=UTC)
        assert hours[-1] == datetime(2026, 1, 16, 22, tzinfo=UTC)
