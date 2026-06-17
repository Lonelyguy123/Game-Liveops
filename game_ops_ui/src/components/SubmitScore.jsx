import { useState } from "react";
import { api } from "../api";

const SAMPLE_PLAYERS = [
  { player_id: "P001", match_id: "M001", region: "India",  device: "Android", ping: 55,  score: 3200,  kills: 18,  deaths: 4, match_duration_seconds: 420 },
  { player_id: "P002", match_id: "M002", region: "India",  device: "iOS",     ping: 62,  score: 2800,  kills: 14,  deaths: 6, match_duration_seconds: 390 },
  { player_id: "P003", match_id: "M003", region: "Europe", device: "PC",      ping: 20,  score: 99000, kills: 250, deaths: 0, match_duration_seconds: 60  },
  { player_id: "P004", match_id: "M004", region: "Europe", device: "Android", ping: 75,  score: 2500,  kills: 12,  deaths: 5, match_duration_seconds: 360 },
  { player_id: "P005", match_id: "M005", region: "India",  device: "PC",      ping: 145, score: 3100,  kills: 16,  deaths: 3, match_duration_seconds: 410 },
];

const BLANK = {
  player_id: "", match_id: "", region: "", device: "",
  ping: "", score: "", kills: "", deaths: "", match_duration_seconds: "",
};

export default function SubmitScore() {
  const [form, setForm]       = useState(BLANK);
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        ...form,
        ping: Number(form.ping),
        score: Number(form.score),
        kills: Number(form.kills),
        deaths: Number(form.deaths),
        match_duration_seconds: Number(form.match_duration_seconds),
      };
      const data = await api.submitScore(payload);
      setResult({ ok: true, data });
    } catch (err) {
      setResult({ ok: false, message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const loadSample = (s) => {
    setForm({ ...s, ping: String(s.ping), score: String(s.score),
      kills: String(s.kills), deaths: String(s.deaths),
      match_duration_seconds: String(s.match_duration_seconds) });
    setResult(null);
  };

  return (
    <div>
      <div className="card">
        <div className="section-title">Quick-load sample players</div>
        <div className="sample-row">
          {SAMPLE_PLAYERS.map((s) => (
            <button
              key={s.player_id}
              className={`btn btn-sm btn-secondary`}
              onClick={() => loadSample(s)}
            >
              {s.player_id}
              {s.player_id === "P003" && " 🚩"}
            </button>
          ))}
        </div>
        <p className="text-muted" style={{ fontSize: ".78rem" }}>
          P003 is intentionally suspicious (250 kills, 99k score, 60s match).
        </p>
      </div>

      <div className="card mt-16">
        <div className="section-title">Submit Match Score</div>
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label>Player ID</label>
              <input value={form.player_id} onChange={(e) => set("player_id", e.target.value)} placeholder="P001" required />
            </div>
            <div className="field">
              <label>Match ID</label>
              <input value={form.match_id} onChange={(e) => set("match_id", e.target.value)} placeholder="M001" required />
            </div>
            <div className="field">
              <label>Region</label>
              <input value={form.region} onChange={(e) => set("region", e.target.value)} placeholder="India" required />
            </div>
            <div className="field">
              <label>Device</label>
              <select value={form.device} onChange={(e) => set("device", e.target.value)} required>
                <option value="">— select —</option>
                <option>Android</option>
                <option>iOS</option>
                <option>PC</option>
                <option>Console</option>
              </select>
            </div>
            <div className="field">
              <label>Ping (ms)</label>
              <input type="number" min="0" value={form.ping} onChange={(e) => set("ping", e.target.value)} placeholder="55" required />
            </div>
            <div className="field">
              <label>Score</label>
              <input type="number" min="0" value={form.score} onChange={(e) => set("score", e.target.value)} placeholder="3200" required />
            </div>
            <div className="field">
              <label>Kills</label>
              <input type="number" min="0" value={form.kills} onChange={(e) => set("kills", e.target.value)} placeholder="18" required />
            </div>
            <div className="field">
              <label>Deaths</label>
              <input type="number" min="0" value={form.deaths} onChange={(e) => set("deaths", e.target.value)} placeholder="4" required />
            </div>
            <div className="field">
              <label>Duration (seconds)</label>
              <input type="number" min="0" value={form.match_duration_seconds} onChange={(e) => set("match_duration_seconds", e.target.value)} placeholder="420" required />
            </div>
          </div>

          <div className="form-actions">
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? "Submitting…" : "Submit Score"}
            </button>
            <button className="btn btn-secondary" type="button" onClick={() => { setForm(BLANK); setResult(null); }}>
              Clear
            </button>
          </div>
        </form>

        {result && (
          result.ok ? (
            <div className={`result-banner ${result.data.flagged ? "flagged" : "success"}`}>
              {result.data.flagged ? (
                <>
                  <strong>🚩 Player flagged!</strong> — {result.data.player_id} / {result.data.match_id}
                  <ul className="reason-list">
                    {result.data.flag_reasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </>
              ) : (
                <strong>✅ Score submitted — {result.data.player_id} / {result.data.match_id} — clean</strong>
              )}
            </div>
          ) : (
            <div className="result-banner error">
              <strong>Error:</strong> {result.message}
            </div>
          )
        )}
      </div>
    </div>
  );
}
