const BASE = "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  // ── Match submission ──────────────────────────────────────
  submitScore: (payload) =>
    request("/submit-score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // ── Leaderboard (season-scoped by default) ────────────────
  getLeaderboard: (region = "", seasonId = null) => {
    const params = new URLSearchParams();
    if (region)   params.set("region", region);
    if (seasonId) params.set("season_id", seasonId);
    const qs = params.toString() ? `?${params}` : "";
    return request(`/leaderboard${qs}`);
  },

  // ── Flagged players (season-scoped by default) ────────────
  getFlagged: (seasonId = null) => {
    const qs = seasonId ? `?season_id=${seasonId}` : "";
    return request(`/flagged-players${qs}`);
  },

  // ── Matchmaking ───────────────────────────────────────────
  getMatchmaking: () => request("/matchmaking"),

  // ── Seasons ───────────────────────────────────────────────
  listSeasons:     ()           => request("/seasons"),
  getActiveSeason: ()           => request("/seasons/active"),
  createSeason:    (name)       => request("/seasons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }),
  resetSeason: (newName) => request("/seasons/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: newName }),
  }),

  // ── CSV upload ────────────────────────────────────────────
  uploadCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/upload-csv", { method: "POST", body: form });
  },

  // ── Dashboard ─────────────────────────────────────────────
  getDashboard: () => request("/dashboard"),
};
