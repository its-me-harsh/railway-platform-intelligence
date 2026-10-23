import json
import os
from pathlib import Path
from typing import Optional
import joblib
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, save_snapshot, recent_history

load_dotenv()
BASE_URL = os.getenv("RAILRADAR_BASE_URL", "https://api.railradar.in/v1").rstrip("/")
API_KEY = os.getenv("RAILRADAR_API_KEY", "").strip()
PLATFORM_TEMPLATE = os.getenv("PLATFORM_API_URL_TEMPLATE", "").strip()
MODEL_PATH = os.getenv("MODEL_PATH", "railway_delay_model.pkl")
TIMEOUT = 20

app = FastAPI(title="Railway Platform Live API", version="1.0.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()

def provider_get(url):
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["x-api-key"] = API_KEY
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Railway data provider request failed: {exc}")
    except ValueError:
        raise HTTPException(status_code=502, detail="Railway data provider returned invalid JSON")

def unwrap(data):
    """Handle common API response envelopes without assuming one exact schema."""
    if not isinstance(data, dict):
        return data
    for key in ("data", "result", "response"):
        value = data.get(key)
        if isinstance(value, (dict, list)):
            return value
    return data

def train_list(data):
    data = unwrap(data)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("trains", "results", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    return []

def find_value(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if obj.get(key) is not None:
            return obj[key]
    return None

@app.get("/")
def root():
    return {"success": True, "message": "Railway Platform Live API is running"}

@app.get("/api/stations/{station_code}/platform/{platform_number}")
def platform_trains(station_code: str, platform_number: int):
    station = station_code.upper()
    if PLATFORM_TEMPLATE:
        url = PLATFORM_TEMPLATE.format(station=station, platform=platform_number)
        data = provider_get(url)
        data = unwrap(data)
        trains = train_list(data)
        response = {"success": True, "station": station, "platform": platform_number,
                    "train_count": len(trains), "trains": trains, "source": "provider"}
        save_snapshot(response, station, platform_number)
        return response
    # Safe fallback: return what has actually been collected, not fabricated live trains.
    rows = recent_history(station=station, platform=platform_number, limit=100)
    latest_by_train = {}
    for row in rows:
        key = row.get("train_number") or f"unknown-{row['id']}"
        latest_by_train.setdefault(key, row)
    trains = []
    for row in latest_by_train.values():
        payload = row.get("payload") or {}
        if isinstance(payload, dict):
            item = dict(payload)
            item.setdefault("train_number", row.get("train_number"))
            item.setdefault("train_name", row.get("train_name"))
            item.setdefault("status", row.get("status"))
            item.setdefault("delay_minutes", row.get("delay_minutes"))
            trains.append(item)
    return {"success": True, "station": station, "platform": platform_number,
            "train_count": len(trains), "trains": trains, "source": "local_history",
            "notice": "Configure PLATFORM_API_URL_TEMPLATE for provider live platform data."}

@app.get("/api/trains/{train_number}/live")
def train_live(train_number: str):
    data = provider_get(f"{BASE_URL}/trains/{train_number}/live")
    return {"success": True, "train_number": train_number, "data": unwrap(data)}

@app.get("/api/trains/{train_number}/intelligence")
def train_intelligence(train_number: str):
    raw = unwrap(provider_get(f"{BASE_URL}/trains/{train_number}/live"))
    if not isinstance(raw, dict):
        raw = {"raw": raw}
    route = find_value(raw, "route", "stations", "stops") or []
    current = find_value(raw, "current_location", "currentLocation", "current_station", "currentStation", "current")
    previous = find_value(raw, "previous_station", "previousStation", "last_station", "lastStation")
    nxt = find_value(raw, "next_station", "nextStation", "next_stop", "nextStop")
    delay = find_value(raw, "delay_minutes", "delayMinutes", "delay", "late_by")
    return {
        "success": True,
        "train_number": str(find_value(raw, "train_number", "trainNumber", "number") or train_number),
        "train_name": find_value(raw, "train_name", "trainName", "name"),
        "status": find_value(raw, "status", "running_status", "runningStatus"),
        "is_live": True,
        "from": find_value(raw, "from", "source", "origin"),
        "to": find_value(raw, "to", "destination", "dest"),
        "current_location": current,
        "previous_station": previous,
        "next_station": nxt,
        "delay_minutes": delay,
        "route_stop_count": len(route) if isinstance(route, list) else None,
        "last_updated": find_value(raw, "last_updated", "lastUpdated", "updated_at", "updatedAt"),
        "raw": raw
    }

@app.get("/api/history")
def history(station: Optional[str] = None, platform: Optional[int] = None,
            train_number: Optional[str] = None, limit: int = Query(100, ge=1, le=1000)):
    rows = recent_history(station=station, platform=platform, train_number=train_number, limit=limit)
    return {"success": True, "count": len(rows), "records": rows}

@app.post("/api/collect")
def collect(station: str = Query(..., min_length=2), platform: int = Query(..., ge=1)):
    station = station.upper()
    if not PLATFORM_TEMPLATE:
        raise HTTPException(status_code=503, detail="Set PLATFORM_API_URL_TEMPLATE in .env to enable provider platform collection.")
    url = PLATFORM_TEMPLATE.format(station=station, platform=platform)
    data = unwrap(provider_get(url))
    trains = train_list(data)
    saved = save_snapshot({"trains": trains}, station, platform)
    return {"success": True, "station": station, "platform": platform,
            "train_count": len(trains), "records_saved": saved, "trains": trains}

@app.get("/api/trains/{train_number}/prediction")
def predict_delay(train_number: str):
    if not Path(MODEL_PATH).exists():
        raise HTTPException(status_code=503, detail="Model not found. Collect historical data and run: python train_model.py")
    try:
        bundle = joblib.load(MODEL_PATH)
        model = bundle["model"]
        features = bundle["features"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load model bundle: {exc}")
    rows = recent_history(train_number=train_number, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="No historical snapshot exists for this train yet.")
    row = rows[0]
    # The baseline feature set is intentionally explicit and robust to missing fields.
    feature_values = {
        "platform_number": row.get("platform_number"),
        "delay_minutes": row.get("delay_minutes"),
        "distance_to_next_km": row.get("distance_to_next_km"),
        "station_code_NDLS": 1 if row.get("station_code") == "NDLS" else 0,
        "station_code_ANVT": 1 if row.get("station_code") == "ANVT" else 0,
    }
    import pandas as pd
    x = pd.DataFrame([{f: feature_values.get(f, 0) for f in features}])
    prediction = float(model.predict(x)[0])
    return {"success": True, "train_number": train_number,
            "predicted_delay_minutes": round(prediction, 2),
            "model": "trained scikit-learn model",
            "note": "Experimental estimate from historical observations; not an official ETA."}
