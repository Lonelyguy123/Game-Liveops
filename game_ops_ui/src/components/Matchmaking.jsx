import { useState, useEffect } from "react";
import { api } from "../api";

const TIER_COLORS = { LOW: "#8888cc", MID: "#55cc55", HIGH: "#ffbe0b" };

export default function Matchmaking() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getMatchmaking();
      setData(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const groups = data?.groups ?? [];

  // Derive unique regions for the summary bar
  const regions = [...new Set(groups.map((g) => g.region))];
  const tiers   = [...new Set(groups.map((g) => g.skill_tier))];

  return (
    <div>
      {data && (
        <div className="stats-bar">
          <div className="stat-box">
            <div className="stat-box-value">{data.total_groups}</div>
            <div className="stat-box-label">Groups</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">
              {groups.reduce((a, g) => a + g.player_ids.length, 0)}
            </div>
            <div className="stat-box-label">Eligible Players</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">{regions.length}</div>
            <div className="stat-box-label">Regions</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">{tiers.length}</div>
            <div className="stat-box-label">Skill Tiers</div>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>🎮 Matchmaking Groups</div>
          <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: 14, marginBottom: 20, flexWrap: "wrap" }}>
          {["LOW", "MID", "HIGH"].map((t) => (
            <span key={t} className={`tier-pill tier-${t}`}>{t} tier</span>
          ))}
          <span className="text-muted" style={{ fontSize: ".78rem", alignSelf: "center" }}>
            — grouped by region + skill tier, split by ping (&gt;80ms gap = new group)
          </span>
        </div>

        {loading && <div className="spinner" />}
        {error   && <div className="result-banner error">{error}</div>}

        {!loading && !error && groups.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🎮</div>
            No matchmaking groups. Submit scores for multiple clean players first.
          </div>
        )}

        {!loading && groups.length > 0 && (
          <div className="mm-grid">
            {groups.map((g) => (
              <div className="mm-card" key={g.group_id}>
                <div className="mm-card-header">
                  <span className="mm-group-id">Group #{g.group_id}</span>
                  <span className={`tier-pill tier-${g.skill_tier}`}>{g.skill_tier}</span>
                </div>

                <div className="mm-region">🌍 {g.region}</div>

                <div className="mm-meta">
                  <span className="stat-chip">
                    <strong>{g.player_ids.length}</strong> players
                  </span>
                </div>

                <div className="mm-players">
                  {g.player_ids.map((pid) => (
                    <span className="player-tag" key={pid}>{pid}</span>
                  ))}
                </div>

                <div className="mm-ping">
                  Avg ping: <strong>{g.avg_ping} ms</strong>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
