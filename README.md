# Railway Platform Live API & Predictive Analytics

A runnable starter project for the railway platform monitoring project:
- FastAPI backend
- RailRadar live train endpoint integration
- SQLite history storage and collection
- ML training/prediction pipeline
- React + Vite dashboard

## Requirements
- Python 3.10+
- Node.js 18+ and npm
- RailRadar API access if the provider requires a key

## 1. Backend setup
From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set `RAILRADAR_API_KEY` if your account/provider requires one.
Then run:

```bash
uvicorn backend:app --reload
```

Backend: http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs

## 2. Frontend setup
In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (normally http://localhost:5173).

## 3. Configure station/platform data
The `/api/stations/{station_code}/platform/{platform_number}` endpoint uses the configured
`PLATFORM_API_URL_TEMPLATE` if your RailRadar account/provider has a station-platform endpoint.
Set it in `.env` using a URL template with `{station}` and `{platform}` placeholders.
If it is not configured, the endpoint returns locally collected snapshots matching that
station/platform, rather than inventing live platform data.

## 4. Collect history
After starting the backend, in another terminal run:

```bash
python collector.py
```

The collector periodically queries the configured station/platform endpoint and saves
observations to `railway_history.db`. Set `COLLECTION_INTERVAL_SECONDS` in `.env`.
Do not run multiple collectors unless you intend to collect duplicate snapshots.

## 5. Train the model
The model is trained only from historical rows that contain a usable delay target.
Once enough data has been collected:

```bash
python train_model.py
```

This creates `railway_delay_model.pkl` and `model_metadata.json`.
The target is `delay_minutes` from collected observations. The script uses a chronological
holdout when there are enough rows. With very little or poor-quality data, metrics are not
reliable; collect more observations before relying on predictions.

## Main endpoints
- `GET /` — health check
- `GET /api/stations/{station_code}/platform/{platform_number}` — platform trains (provider endpoint or stored history)
- `GET /api/trains/{train_number}/live` — live provider response
- `GET /api/trains/{train_number}/intelligence` — normalized train details
- `GET /api/trains/{train_number}/prediction` — model prediction if a trained model and compatible features exist
- `GET /api/history?station=NDLS&platform=4&limit=100` — recent stored snapshots
- `POST /api/collect` — manually collect a station/platform snapshot

## Important notes
- Provider response schemas and API access requirements can change. Check your current RailRadar
  documentation and set the environment variables accordingly.
- This bundle does not include your personal SQLite database or your previously trained model file.
  Run collection and training locally to create them.
- Prediction is an estimate based on available historical data, not an official railway ETA.
