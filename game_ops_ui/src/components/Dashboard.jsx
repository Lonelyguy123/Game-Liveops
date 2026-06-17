import { useState, useEffect } from "react";
import { api } from "../api";

function StatCard({ icon, value, label, color }) {
  return (
    <div className="stat-box" style={{ textAlign: "center" }}>
      <div style={{ fontSize: "1.6rem", marginBottom: 4 }}>{icon}</div>
      <div className="stat-box-value" style={color ? { color } : {}}>
        {value ?? "—"}
      </div>
      <div className="stat-box-label">{label}</div>
    </div>
  );
}

function SeasonBadge({ season }) {
  if (!season) return <span className="text-muted">None</span>;
  return (
    <span style={{
      background: "linear-gradient(90deg,#6c63ff22,#00d4aa22)",
      border: "1px solid #6c63ff55",
      borderRadius: 6,
      padding: "3px 12px",
      color: "#a89cff",
      fontWeight: 700,
      fontSize: ".9rem",
    }}>
      {season.name}
    </span>
  );
}

function CleanRateBar({ pct }) {
  const danger = pct < 60;
  const warn   = pct < 85;
  const color  = danger ? "var(--danger)" : warn ? "var(--warn)" : "var(--accent2)";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span className="text-muted" style={{ fontSize: ".8rem" }}>Clean player rate</span>
        <span style={{ fontWeight: 800, color }}>{pct}%</span>
      </div>
      <div style={{ background: "var(--border)", borderRadius: 99, height: 8, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%",
          background: color,
          borderRadius: 99,
          transition: "width .5s ease",
        }} />
      </div>
    </div>
  );
}

function SeasonCard({ season, active }) {
  const formatDate = (iso) => iso
    ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : null;

  return (
    <div style={{
      background: "var(--surface2)",
      border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
      borderRadius: 8,
      padding: "12px 16px",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      gap: 12,
    }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: ".95rem" }}>{season.name}</div>
        <div className="text-muted" style={{ fontSize: ".75rem", marginTop: 2 }}>
          Started {formatDate(season.started_at)}
          {season.ended_at && ` → Ended ${formatDate(season.ended_at)}`}
        </div>
      </div>
      <span className={`flag-pill ${active ? "clean" : ""}`} style={!active ? { background: "#1a1a2e", color: "#888", border: "1px solid #444" } : {}}>
        {active ? "● Active" : "Closed"}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats]         = useState(null);
  const [seasons, setSeasons]     = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [resetName, setResetName] = useState("");
  const [resetMsg, setResetMsg]   = useState(null);
  const [resetting, setResetting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, seas] = await Promise.all([api.getDashboard(), api.listSeasons()]);
      setStats(s);
      setSeasons(seas);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleReset = async () => {
    const name = resetName.trim() || `Season ${(seasons.length ?? 0) + 1}`;
    setResetting(true);
    setResetMsg(null);
    try {
      const res = await api.resetSeason(name);
      setResetMsg({ ok: true, text: res.message });
      setResetName("");
      load();
    } catch (err) {
      setResetMsg({ ok: false, text: err.message });
    } finally {
      setResetting(false);
    }
  };

  if (loading) return <div className="spinner" />;
  if (error)   return <div className="result-banner error">{error}</div>;
  if (!stats)  return null;

  return (
    <div>
      {/* ── KPI row ── */}
      <div className="stats-bar">
        <StatCard icon="👥" value={stats.total_players}  label="Total Players" />
        <StatCard icon="⚔️"  value={stats.total_matches}  label="Matches (Season)" />
        <StatCard icon="🚩" value={stats.total_flagged}  label="Flagged (Season)" color="var(--danger)" />
        <StatCard icon="📅" value={stats.total_seasons}  label="Seasons" />
        <StatCard
          icon="🏆"
          value={stats.top_player_id ?? "—"}
          label={`Top Player · ${stats.top_player_score.toLocaleString()} pts`}
          color="var(--rank-gold)"
        />
      </div>

      {/* ── Active season + clean rate ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
          <div>
            <div className="section-title" style={{ marginBottom: 4 }}>Active Season</div>
            <SeasonBadge season={stats.active_season} />
          </div>
          <button className="btn btn-secondary btn-sm" onClick={load}>↺ Refresh</button>
        </div>
        <CleanRateBar pct={stats.clean_rate_pct} />
      </div>

      {/* ── Season reset ── */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="section-title">🔄 Season Reset</div>
        <p className="text-muted" style={{ fontSize: ".85rem", marginBottom: 16, lineHeight: 1.6 }}>
          Closing the current season preserves all its data. The new season starts with a clean leaderboard.
          Historical data remains queryable by season ID.
        </p>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input
            className="field input"
            style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 6, color: "var(--text)", padding: "8px 12px",
              fontSize: ".92rem", width: 220,
            }}
            placeholder={`Season ${(seasons.length ?? 0) + 1}`}
            value={resetName}
            onChange={(e) => setResetName(e.target.value)}
          />
          <button
            className="btn btn-danger"
            onClick={handleReset}
            disabled={resetting || !stats.active_season}
            title={!stats.active_season ? "No active season to reset" : ""}
          >
            {resetting ? "Resetting…" : "Reset Season"}
          </button>
        </div>
        {!stats.active_season && (
          <p className="text-muted" style={{ fontSize: ".78rem", marginTop: 8 }}>
            No active season. Submit a score first — Season 1 is created automatically.
          </p>
        )}
        {resetMsg && (
          <div className={`result-banner ${resetMsg.ok ? "success" : "error"}`} style={{ marginTop: 14 }}>
            {resetMsg.text}
          </div>
        )}
      </div>

      {/* ── Season history ── */}
      <div className="card">
        <div className="section-title">📅 Season History</div>
        {seasons.length === 0 ? (
          <div className="empty-state" style={{ padding: "24px 0" }}>
            <div className="empty-icon">📅</div>
            No seasons yet. Submit a score to auto-create Season 1.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[...seasons].reverse().map((s) => (
              <SeasonCard key={s.id} season={s} active={s.is_active} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
