import { useCallback, useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function App() {
  const [station, setStation] = useState("NDLS");
  const [platform, setPlatform] = useState("4");
  const [trainNumber, setTrainNumber] = useState("12616");
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [intelligence, setIntelligence] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);

  const loadPlatform = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [platformRes, historyRes] = await Promise.all([
        fetch(`${API}/api/stations/${encodeURIComponent(station)}/platform/${encodeURIComponent(platform)}`),
        fetch(`${API}/api/history?station=${encodeURIComponent(station)}&platform=${encodeURIComponent(platform)}&limit=30`)
      ]);
      const platformJson = await platformRes.json();
      const historyJson = await historyRes.json();
      if (!platformRes.ok) throw new Error(platformJson.detail || "Unable to load platform trains.");
      setData(platformJson);
      setHistory(historyJson.records || []);
      setUpdatedAt(new Date());
    } catch (e) {
      setError(`${e.message}. Check that the backend is running at ${API}.`);
    } finally { setBusy(false); }
  }, [station, platform]);

  const loadTrain = async () => {
    setError(""); setIntelligence(null); setPrediction(null);
    try {
      const res = await fetch(`${API}/api/trains/${encodeURIComponent(trainNumber)}/intelligence`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Unable to load train intelligence.");
      setIntelligence(json);
      const pRes = await fetch(`${API}/api/trains/${encodeURIComponent(trainNumber)}/prediction`);
      const pJson = await pRes.json();
      if (pRes.ok) setPrediction(pJson);
      else setPrediction({ error: pJson.detail || "Prediction is not available yet." });
    } catch (e) { setError(e.message); }
  };

  useEffect(() => { loadPlatform(); }, [loadPlatform]);
  useEffect(() => {
    const id = setInterval(loadPlatform, 60000);
    return () => clearInterval(id);
  }, [loadPlatform]);

  const trains = data?.trains || [];
  const get = (obj, ...keys) => {
    for (const key of keys) if (obj?.[key] !== undefined && obj?.[key] !== null) return obj[key];
    return "—";
  };

  return <main className="shell">
    <header className="topbar">
      <div className="brand"><div className="brand-icon">↗</div><div><div className="eyebrow">LIVE • ML • ANALYTICS</div><h1>Railway Intelligence</h1></div></div>
      <div className="live-pill"><span /> System dashboard</div>
    </header>

    <section className="hero">
      <div><p className="eyebrow">OPERATIONAL OVERVIEW</p><h2>Know what’s moving.<br/><span>Understand what’s next.</span></h2>
      <p className="muted">Live train data, collected history, and experimental delay predictions in one place.</p></div>
      <div className="hero-mark">🚆</div>
    </section>

    <section className="controls panel">
      <div className="section-heading"><div><p className="eyebrow">PLATFORM MONITOR</p><h3>Trains at a glance</h3></div>
        <button className="secondary" onClick={loadPlatform} disabled={busy}>{busy ? "Refreshing…" : "↻ Refresh"}</button></div>
      <div className="form-row">
        <label>Station code<input value={station} onChange={e => setStation(e.target.value.toUpperCase())} placeholder="NDLS"/></label>
        <label>Platform<input type="number" min="1" value={platform} onChange={e => setPlatform(e.target.value)}/></label>
        <button onClick={loadPlatform}>Load platform</button>
      </div>
      <div className="stats">
        <div className="stat"><span>Trains returned</span><strong>{data?.train_count ?? "—"}</strong></div>
        <div className="stat"><span>Data source</span><strong className="small-strong">{data?.source === "provider" ? "Provider live" : data?.source === "local_history" ? "Local history" : "—"}</strong></div>
        <div className="stat"><span>Last refreshed</span><strong className="small-strong">{updatedAt ? updatedAt.toLocaleTimeString() : "—"}</strong></div>
      </div>
      {data?.notice && <p className="notice">{data.notice}</p>}
      {error && <p className="error">{error}</p>}
      <div className="train-grid">
        {trains.map((train, i) => <article className="train-card" key={`${get(train,"train_number","trainNumber","number")}-${i}`}>
          <div className="train-card-top"><span className="train-symbol">🚆</span><span className="badge">{get(train,"status","running_status","runningStatus")}</span></div>
          <h4>{get(train,"train_name","trainName","name")}</h4>
          <p className="muted">Train #{get(train,"train_number","trainNumber","number")}</p>
          <div className="train-meta"><span>Delay</span><strong>{get(train,"delay_minutes","delayMinutes","delay")} min</strong></div>
          <div className="train-meta"><span>Next station</span><strong>{get(train,"next_station","nextStation","next_stop")}</strong></div>
        </article>)}
        {!trains.length && !busy && <div className="empty"><strong>No train records to display</strong><p>Configure a provider platform endpoint or run the collector to populate local history.</p></div>}
      </div>
    </section>

    <section className="two-col">
      <div className="panel">
        <p className="eyebrow">TRAIN INTELLIGENCE</p><h3>Inspect a train</h3>
        <div className="form-row train-search"><label>Train number<input value={trainNumber} onChange={e => setTrainNumber(e.target.value)} placeholder="12616"/></label><button onClick={loadTrain}>Analyze train</button></div>
        {intelligence && <div className="intel">
          <h4>{intelligence.train_name || `Train ${intelligence.train_number}`}</h4>
          <p className="muted">#{intelligence.train_number} · {intelligence.status || "Status unavailable"}</p>
          <div className="detail-grid">
            <div><span>Current location</span><strong>{typeof intelligence.current_location === "object" ? JSON.stringify(intelligence.current_location) : intelligence.current_location || "—"}</strong></div>
            <div><span>Previous station</span><strong>{typeof intelligence.previous_station === "object" ? JSON.stringify(intelligence.previous_station) : intelligence.previous_station || "—"}</strong></div>
            <div><span>Next station</span><strong>{typeof intelligence.next_station === "object" ? JSON.stringify(intelligence.next_station) : intelligence.next_station || "—"}</strong></div>
            <div><span>Current delay</span><strong>{intelligence.delay_minutes ?? "—"} min</strong></div>
          </div>
          {prediction && <div className="prediction"><span>Experimental predicted delay</span><strong>{prediction.predicted_delay_minutes !== undefined ? `${prediction.predicted_delay_minutes} min` : "Unavailable"}</strong><small>{prediction.note || prediction.error}</small></div>}
        </div>}
        {!intelligence && <p className="muted helper">Enter a train number to load live intelligence and an available model prediction.</p>}
      </div>
      <div className="panel">
        <p className="eyebrow">HISTORICAL STORAGE</p><h3>Recent observations</h3>
        <p className="muted">Latest stored snapshots for {station || "selected station"} · Platform {platform || "—"}</p>
        <div className="history-list">
          {history.slice(0, 8).map(row => <div className="history-row" key={row.id}><div><strong>{row.train_name || `Train ${row.train_number || "—"}`}</strong><small>{row.train_number || "No number"} · {row.collected_at ? new Date(row.collected_at).toLocaleString() : "Time unavailable"}</small></div><span>{row.delay_minutes == null ? "—" : `${row.delay_minutes} min`}</span></div>)}
          {!history.length && <div className="empty compact">No stored observations yet.</div>}
        </div>
      </div>
    </section>
    <footer>Railway Intelligence · Prototype dashboard · Predictions are experimental and not official railway information.</footer>
  </main>;
}
