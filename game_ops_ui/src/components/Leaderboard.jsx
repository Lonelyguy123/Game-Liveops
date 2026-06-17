import { useState, useEffect, useCallback } from "react";
import { api } from "../api";

function RankBadge({ rank }) {
  const cls  = rank <= 3 ? `rank-badge rank-${rank}` : "rank-badge";
  const icon = rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : `#${rank}`;
  return <span className={cls}>{icon}</span>;
}

function KD({ kills, deaths }) {
  const kd = deaths === 0 ? "∞" : (kills / deaths).toFixed(2);
  return <span title={`${kills}K / ${deaths}D`}>{kd}</span>;
}

export default function Leaderboard() {
  const [data, setData]         = useState(null);
  const [filter, setFilter]     = useState("");
  const [applied, setApplied]   = useState("");
  const [seasons, setSeasons]   = useState([]);
  const [seasonId, setSeasonId] = useState("");   // "" = active season
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);

  const load = useCallback(async (region, sid) => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getLeaderboard(region, sid || null);
      setData(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load seasons list and initial leaderboard
  useEffect(() => {
    api.listSeasons().then(setSeasons).catch(() => {});
    load("", null);
  }, [load]);

  const handleFilter = () => {
    setApplied(filter.trim());
    load(filter.trim(), seasonId || null);
  };

  const handleClear = () => {
    setFilter(""); setApplied("");
    load("", seasonId || null);
  };

  const handleSeasonChange = (e) => {
    const sid = e.target.value;
    setSeasonId(sid);
    load(applied, sid || null);
  };

  const entries = data?.entries ?? [];
  const activeSeason = seasons.find((s) => s.is_active);

  return (
    <div>
      {data && (
        <div className="stats-bar">
          <div className="stat-box">
            <div className="stat-box-value">{data.total_players}</div>
            <div className="stat-box-label">Players</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">{entries.filter((e) => e.is_flagged).length}</div>
            <div className="stat-box-label">Flagged</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">
              {entries.length > 0 ? Math.max(...entries.map((e) => e.total_score)).toLocaleString() : "—"}
            </div>
            <div className="stat-box-label">Top Score</div>
          </div>
          <div className="stat-box">
            <div className="stat-box-value">{applied || "All"}</div>
            <div className="stat-box-label">Region</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="lb-controls">
          {/* Season selector */}
          <select
            value={seasonId}
            onChange={handleSeasonChange}
            style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 6, color: "var(--text)", padding: "8px 12px",
              fontSize: ".88rem",
            }}
          >
            <option value="">
              {activeSeason ? `${activeSeason.name} (Active)` : "Active Season"}
            </option>
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}{s.is_active ? " ●" : ""}
              </option>
            ))}
          </select>

          {/* Region filter */}
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by region…"
            onKeyDown={(e) => e.key === "Enter" && handleFilter()}
          />
          <button className="btn btn-primary btn-sm" onClick={handleFilter}>Apply</button>
          {applied && (
            <button className="btn btn-secondary btn-sm" onClick={handleClear}>Clear</button>
          )}
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => load(applied, seasonId || null)}
            style={{ marginLeft: "auto" }}
          >
            ↺ Refresh
          </button>
        </div>

        {loading && <div className="spinner" />}
        {error   && <div className="result-banner error">{error}</div>}

        {!loading && !error && entries.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🏆</div>
            No players for this season yet. Submit some scores first.
          </div>
        )}

        {!loading && entries.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Player</th>
                  <th>Region</th>
                  <th>Score</th>
                  <th>K / D</th>
                  <th>Matches</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.player_id}>
                    <td><RankBadge rank={e.rank} /></td>
                    <td style={{ fontWeight: 700 }}>{e.player_id}</td>
                    <td>{e.region}</td>
                    <td style={{ fontWeight: 700 }}>{e.total_score.toLocaleString()}</td>
                    <td><KD kills={e.total_kills} deaths={e.total_deaths} /></td>
                    <td className="text-muted">{e.matches_played}</td>
                    <td>
                      <span className={`flag-pill ${e.is_flagged ? "flagged" : "clean"}`}>
                        {e.is_flagged ? "🚩 Flagged" : "✓ Clean"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
