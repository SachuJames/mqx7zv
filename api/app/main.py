from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.store import Store

app = FastAPI(title="Day-ahead wind forecast review", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

store = Store()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "days": len(store.days)}


@app.get("/api/days")
def days() -> list[dict]:
    return store.day_summaries()


@app.get("/api/days/{day_date}")
def day_detail(day_date: str) -> dict:
    day = store.day(day_date)
    if day is None:
        raise HTTPException(status_code=404, detail="No data for that settlement day")
    return day


@app.get("/api/summary")
def summary() -> dict:
    return store.summary
