import json
import os
import sqlite3
from pathlib import Path
import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "railway_history.db")
MODEL_PATH = os.getenv("MODEL_PATH", "railway_delay_model.pkl")
META_PATH = os.getenv("MODEL_METADATA_PATH", "model_metadata.json")
FEATURES = ["platform_number", "distance_to_next_km", "station_code_NDLS", "station_code_ANVT"]

def main():
    if not Path(DB_PATH).exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run the backend/collector first.")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("""
            SELECT collected_at, station_code, platform_number, delay_minutes, distance_to_next_km
            FROM train_history
            WHERE delay_minutes IS NOT NULL
            ORDER BY collected_at ASC
        """, conn)
    if len(df) < 20:
        raise SystemExit(f"Only {len(df)} labeled rows found. Collect at least 20; preferably hundreds across different trains and times.")
    df["station_code_NDLS"] = (df["station_code"] == "NDLS").astype(int)
    df["station_code_ANVT"] = (df["station_code"] == "ANVT").astype(int)
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[FEATURES] = df[FEATURES].fillna(0)
    X, y = df[FEATURES], pd.to_numeric(df["delay_minutes"], errors="coerce")
    valid = y.notna()
    X, y = X.loc[valid], y.loc[valid]
    split = max(1, int(len(X) * 0.8))
    if len(X) - split < 1:
        split = len(X) - 1
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    model = ExtraTreesRegressor(n_estimators=250, random_state=42, min_samples_leaf=2)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    metrics = {
        "rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "mae_minutes": round(float(mean_absolute_error(y_test, predictions)), 3),
        "rmse_minutes": round(float(mean_squared_error(y_test, predictions) ** 0.5), 3),
        "r2": round(float(r2_score(y_test, predictions)), 3) if len(y_test) >= 2 else None,
        "features": FEATURES,
        "warning": "Chronological holdout is only a first check. Sparse or biased historical data can make metrics unstable."
    }
    joblib.dump({"model": model, "features": FEATURES}, MODEL_PATH)
    Path(META_PATH).write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"Saved model: {MODEL_PATH}")

if __name__ == "__main__":
    main()
