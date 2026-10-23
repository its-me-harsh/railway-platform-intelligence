import os
import time
import requests
from dotenv import load_dotenv
from database import save_snapshot

load_dotenv()
TEMPLATE = os.getenv("PLATFORM_API_URL_TEMPLATE", "").strip()
INTERVAL = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "7200"))
BASE_URL = os.getenv("RAILRADAR_BASE_URL", "https://api.railradar.in/v1").rstrip("/")
API_KEY = os.getenv("RAILRADAR_API_KEY", "").strip()
STATIONS = os.getenv("DEFAULT_STATIONS", "NDLS:4,ANVT:1")

def fetch(url):
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["x-api-key"] = API_KEY
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()

def unwrap(data):
    if isinstance(data, dict):
        for k in ("data", "result", "response"):
            if isinstance(data.get(k), (dict, list)):
                return data[k]
    return data

def get_trains(data):
    data = unwrap(data)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("trains", "results", "items"):
            if isinstance(data.get(k), list):
                return data[k]
    return []

def main():
    if not TEMPLATE:
        raise SystemExit("Set PLATFORM_API_URL_TEMPLATE in .env to your valid provider platform endpoint.")
    pairs = []
    for token in STATIONS.split(","):
        if ":" in token:
            station, platform = token.strip().split(":", 1)
            pairs.append((station.upper(), int(platform)))
    print(f"Collector running for {pairs}; interval={INTERVAL}s. Ctrl+C to stop.")
    while True:
        for station, platform in pairs:
            try:
                url = TEMPLATE.format(station=station, platform=platform)
                trains = get_trains(fetch(url))
                saved = save_snapshot({"trains": trains}, station, platform)
                print(f"{station} platform {platform}: {len(trains)} trains, saved {saved}")
            except Exception as exc:
                print(f"Collection failed for {station}/{platform}: {exc}")
        time.sleep(max(60, INTERVAL))

if __name__ == "__main__":
    main()
