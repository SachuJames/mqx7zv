# Day-ahead wind: what the desk knew, and how it held up

I built this app for a power buying desk in the UK day-ahead market.
It answers two questions:

1. When the desk had to commit to buying power for a day, what did the
   latest wind forecast say?
2. How accurate was that forecast?

Live app: https://mqx7zv.vercel.app

The key idea is simple. A forecast should only be scored on what was
published before the buying decision was made. Anything published
later was not available to the desk, so using it makes the forecast
look better than it really was.

## What January 2026 showed

Scope: purchase decisions made in January 2026 (decision days Jan 1 to
31, delivery days Jan 2 to Feb 1), 744 hours in total.

- Average error (MAE) 2,009 MW. Scored the flattering way, against the
  last forecast before delivery, it would look like about 1,800 MW.
- The forecast was too high in 84% of hours, by 1,729 MW on average.
  Most of the error is this bias, not random noise.
- Buying on the raw forecast left the desk about 1.39 million MWh
  short over the month, to be found later in the balancing market.
  Shortfall is an energy amount, not a money figure. What it cost
  depends on balancing prices at the time, which are not in this data,
  so the app does not price it. The opposite case is surplus: power
  bought ahead that was not needed.
- Removing the average bias cuts the error to about 1,399 MW. That
  correction is worked out on the same January data it is applied to,
  so it is an illustration, not a live performance estimate. A live
  desk would correct from past errors only and do a little worse.
  The forecast still beats the simple fallback of using yesterday's
  actuals (MAE 3,974 MW) by about half.

## Run it

With Docker:

```bash
docker compose up --build
```

Open http://localhost:8080 (API on http://localhost:8000).

Without Docker:

```bash
cd api && pip install -r requirements.txt
uvicorn app.main:app --port 8000

cd web && npm install && npm run dev
```

Open http://localhost:5173.

## Files

- `api/app/core.py`: all the logic. Decision cutoff, forecast and
  actual matching, and every metric.
- `api/app/main.py`: the FastAPI app (three read endpoints).
- `api/scripts/ingest.py`: downloads the Elexon data and builds the
  datasets the API serves.
- `api/tests/`: tests, including one that proves forecasts published
  after the decision are never used.
- `web/src/`: the React app. `DecisionView.tsx` is the per day view,
  `AccuracyView.tsx` is the month view.
- `data/`: cached raw Elexon downloads in `raw/`, built datasets in
  `processed/`. The app ships with the data built, so it runs offline.

## How the numbers are worked out

Data is from Elexon BMRS only: FUELHH for actual wind generation
(half-hourly) and WINDFOR for forecasts (hourly, published eight
times a day).

- A delivery (settlement) day runs 23:00 GMT to 23:00 GMT.
- The decision moment is the day-ahead auction gate closure, 09:50 GMT
  the day before. For each delivery hour I take the last forecast
  published at or before 09:50, in practice the 09:30 publish.
- FUELHH is half-hourly and WINDFOR is hourly, so the actual for an
  hour is the mean of the two half hours.
- The corrected forecast in the app is the forecast minus the month's
  average error, and the band is the 10th to 90th percentile of the
  month's errors. Both come from the same January data they are shown
  against. Actual generation fell inside the band in about 80% of
  January hours by construction; that is a description of January,
  not a coverage guarantee for future days.
- The API serves data prepared in advance by the ingest script, it
  does not call Elexon when you open a page. Every number can be
  reproduced from the cached raw files in `data/raw/`.

## A note on AI tools

Most of this is my own work: the data pulls, the definitions above,
the analysis, and the layout of the two views. For parts of the coding
I used AI assistants (Claude and ChatGPT), mostly for boilerplate,
chart setup, and a first draft of some tests. I reviewed everything
they produced and checked the numbers against the live Elexon API
myself.
