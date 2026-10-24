# Day-ahead wind: what the desk knew, and how it held up

I built this small web app for a power buying desk. It answers two
questions for the UK day-ahead market:

1. When the desk committed to buy power for a delivery day, what did the
   latest wind generation forecast actually say?
2. How accurate was that forecast, in numbers the desk can plan around?

Live deployment: https://mqx7zv.vercel.app

## Why decision time matters

A forecast can look good if you score it against the last revision
published before delivery. That revision did not exist when the buying
decision was made, so scoring against it flatters the numbers. This app
only uses forecasts that were published at or before the decision moment,
and the difference is material: for January 2026 the honest day-ahead MAE
is about 2,009 MW, while scoring against the last revision before
delivery gives roughly 1,800 MW and hides a large systematic bias.

## Headline findings, January 2026

- Day-ahead MAE 2,009 MW, RMSE 2,500 MW, over 744 delivery hours.
- Bias +1,729 MW: the forecast overshot actual wind generation in 84.3%
  of hours. The miss is mostly bias, not noise. Removing the average bias
  would cut MAE to about 1,399 MW.
- Buying on the raw forecast left the desk roughly 1.39 million MWh short
  across the month in hourly terms (sum of hourly over-forecasts), energy
  that then has to be covered at balancing prices.
- The forecast still carries real information: a persistence forecast
  (yesterday's actuals) scores MAE 3,974 MW, so the day-ahead forecast is
  about 49% better than that fallback.

## How to run it

With Docker:

```bash
docker compose up --build
```

Then open http://localhost:8080. The API is on http://localhost:8000.

Without Docker, for development:

```bash
# data, only needed if you want to regenerate it
python3 api/scripts/ingest.py

# API
cd api
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# web, in a second terminal
cd web
npm install
npm run dev
```

Then open http://localhost:5173. Vite proxies /api to the API server.

## Files and directories

- `api/app/core.py`: the decision-time logic. Cutoff handling, the hourly
  join, bias correction inputs, and every metric. Kept free of web code so
  it can be tested on its own.
- `api/app/main.py`: FastAPI app with three read endpoints.
- `api/app/store.py`: loads the precomputed data at startup.
- `api/scripts/ingest.py`: pulls Elexon data, caches it raw, and writes
  the processed datasets the API serves.
- `api/tests/`: pytest suite. The no look-ahead rule is tested directly,
  including a fixture where a post-gate forecast is closer to the actual
  and must still be ignored.
- `web/src/`: React app. `DecisionView.tsx` is the per day view,
  `AccuracyView.tsx` is the month view.
- `data/raw/`: cached Elexon responses, gzipped JSON.
- `data/processed/`: `days.json` (one record per settlement day) and
  `summary.json` (January metrics). The app ships with these built, so it
  runs offline.
- `docker-compose.yml`, `api/Dockerfile`, `web/Dockerfile`: the container
  setup. The web image is nginx serving the built frontend and proxying
  /api to the API container.

## Data and methodology

Data sources, both from Elexon BMRS and nothing else:

- Actuals: FUELHH dataset, filtered to fuelType WIND, half-hourly.
- Forecasts: WINDFOR dataset, hourly, published eight times a day.

Definitions I settled on, applied everywhere in the app:

- Scope is purchase decisions made in January 2026, read literally:
  decision days 1 to 31 January 2026, buying for settlement days
  2 January to 1 February 2026.
- A settlement day runs 23:00 GMT on the previous calendar day to
  23:00 GMT on the day itself.
- The decision moment is the N2EX day-ahead auction gate closure,
  09:50 GMT on the day before the settlement day. The decision forecast
  for each delivery hour is the last WINDFOR publish at or before that
  moment, in practice the 09:30 GMT publish.
- Hourly actual generation is the mean of the two FUELHH half hours in
  that hour, since FUELHH values are MW averaged over a half hour.
- The bias-corrected forecast subtracts the month's mean signed error.
  The band on the day chart runs from the 10th to the 90th percentile of
  the month's signed errors. Both are computed from decision-time errors
  only.
- Shortfall for an hour is forecast minus actual when positive, summed in
  MWh. It is the hourly energy the desk still had to find after buying on
  the forecast.

The API serves precomputed data rather than calling Elexon per request.
The January window is fixed, the raw pulls are slow, and precomputing
makes every number in the app reproducible from the cached raw files.

## A note on AI tools

Most of this is my own work: the data pulls, the decision-time
definitions, the analysis, and how the two views are laid out. For parts
of the coding I used AI assistants (Claude and ChatGPT), mostly for
boilerplate, chart setup, and a first draft of some tests. I reviewed
everything they produced, changed what did not fit, and checked the
numbers in the app against the live Elexon API myself. The tests in
`api/tests/` cover the parts that matter most, the no look-ahead rule
above all.
