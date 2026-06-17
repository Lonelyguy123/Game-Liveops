import { useState, useEffect } from "react";
import { api } from "../api";

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function FlaggedPlayers() {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getFlagged();
      setData(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const players = data?.players ?? [];

  return (
    <div>
      {data && (
        <div className="stats-bar">
          <div className="stat-box">
            <div className="stat-box-value" style={{ color: "var(--danger)" }}>
              {data.total_flagged}
            </div>
            <div className="stat-box-label">Total Flagged</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">
              {[...new Set(players.map((p) => p.player_id))].length}
            </div>
            <div className="stat-box-label">Unique Players</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">
              {players.reduce((acc, p) => acc + p.reasons.length, 0)}
            </div>
            <div className="stat-box-label">Total Violations</div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>🚩 Suspicious Players</div>
          <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
        </div>

        {loading && <div className="spinner" />}
        {error   && <div className="result-banner error">{error}</div>}

        {!loading && !error && players.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🛡️</div>
            No flagged players. Everyone is playing fair.
          </div>
        )}

        {!loading && players.length > 0 && (
          <div className="flagged-grid">
            {players.map((p, i) => (
              <div className="flagged-card" key={i}>
                <div className="flagged-card-header">
                  <div>
                    <div className="flagged-pid">{p.player_id}</div>
                    <div className="flagged-mid">Match: {p.match_id}</div>
                  </div>
                  <div className="flagged-at">{formatDate(p.flagged_at)}</div>
                </div>
                <div>
                  {p.reasons.map((r, j) => (
                    <span className="reason-tag" key={j}>{r}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
