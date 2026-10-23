import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "railway_history.db")

def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True) if Path(DB_PATH).parent != Path(".") else None
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS train_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TEXT NOT NULL,
                station_code TEXT,
                platform_number INTEGER,
                train_number TEXT,
                train_name TEXT,
                status TEXT,
                delay_minutes REAL,
                current_station TEXT,
                next_station TEXT,
                distance_to_next_km REAL,
                payload_json TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_station_platform ON train_history(station_code, platform_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_train_time ON train_history(train_number, collected_at)")
        conn.commit()

def _number(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def _first(d, *keys):
    if not isinstance(d, dict):
        return None
    for key in keys:
        val = d.get(key)
        if val is not None:
            return val
    return None

def save_snapshot(data, station_code=None, platform_number=None):
    """Save a raw provider payload or normalized platform response."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    trains = data.get("trains") if isinstance(data, dict) else None
    if not isinstance(trains, list):
        # A live train payload may itself describe one train.
        trains = [data] if isinstance(data, dict) else []
    saved = 0
    with connect() as conn:
        for train in trains:
            if not isinstance(train, dict):
                continue
            train_number = _first(train, "train_number", "trainNumber", "number", "train_no")
            train_name = _first(train, "train_name", "trainName", "name")
            status = _first(train, "status", "running_status", "runningStatus")
            delay = _number(_first(train, "delay_minutes", "delayMinutes", "delay", "late_by"))
            current = _first(train, "current_station", "currentStation", "current_location", "currentLocation")
            nxt = _first(train, "next_station", "nextStation", "next_stop")
            distance = _number(_first(train, "distance_to_next_km", "distanceToNextStationKm", "distance_to_next_station_km"))
            conn.execute("""
                INSERT INTO train_history
                (collected_at, station_code, platform_number, train_number, train_name, status,
                 delay_minutes, current_station, next_station, distance_to_next_km, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, station_code, platform_number, str(train_number) if train_number is not None else None,
                  str(train_name) if train_name is not None else None, str(status) if status is not None else None,
                  delay, str(current) if current is not None else None, str(nxt) if nxt is not None else None,
                  distance, json.dumps(train, ensure_ascii=False)))
            saved += 1
        conn.commit()
    return saved

def recent_history(station=None, platform=None, train_number=None, limit=100):
    init_db()
    query = "SELECT * FROM train_history WHERE 1=1"
    args = []
    if station:
        query += " AND station_code = ?"; args.append(station.upper())
    if platform is not None:
        query += " AND platform_number = ?"; args.append(int(platform))
    if train_number:
        query += " AND train_number = ?"; args.append(str(train_number))
    query += " ORDER BY id DESC LIMIT ?"; args.append(max(1, min(int(limit), 1000)))
    with connect() as conn:
        rows = conn.execute(query, args).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try: item["payload"] = json.loads(item.pop("payload_json"))
        except Exception: item["payload"] = item.pop("payload_json", None)
        result.append(item)
    return result
