import { useState, useRef } from "react";
import { api } from "../api";

const SAMPLE_FILES = [
  { name: "match_clean_5v5.csv",      label: "Clean 5v5 (India vs Europe)",  color: "var(--accent2)" },
  { name: "match_with_cheaters.csv",  label: "With Cheaters (NA)",           color: "var(--danger)"  },
  { name: "match_multiregion.csv",    label: "Multi-region (SEA vs LATAM)",  color: "var(--warn)"    },
];

export default function CsvUpload() {
  const inputRef              = useRef(null);
  const [file, setFile]       = useState(null);
  const [preview, setPreview] = useState(null);   // parsed rows before submit
  const [result, setResult]   = useState(null);   // API response
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [dragging, setDragging] = useState(false);

  // ── Parse CSV in the browser for preview ─────────────────
  const parsePreview = (f) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const lines = e.target.result.split("\n").filter((l) => l.trim());
      if (lines.length < 2) { setPreview([]); return; }
      const headers = lines[0].split(",").map((h) => h.trim().toLowerCase());
      const rows = lines.slice(1).map((line) => {
        const vals = line.split(",").map((v) => v.trim());
        return Object.fromEntries(headers.map((h, i) => [h, vals[i] ?? ""]));
      });
      setPreview(rows);
    };
    reader.readAsText(f);
  };

  const handleFileChange = (f) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
    parsePreview(f);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileChange(f);
  };

  const handleSubmit = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.uploadCsv(file);
      setResult(data);
      setPreview(null); // replace preview with result
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div>
      {/* ── How it works ── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">📂 How CSV upload works</div>
        <p style={{ color: "var(--text-muted)", fontSize: ".88rem", lineHeight: 1.7 }}>
          After each match finishes, drop the match CSV here. Each row is one
          player's result. All rows sharing the same <code style={{ background: "var(--surface2)", padding: "1px 5px", borderRadius: 4 }}>match_id</code> belong to
          the same game (e.g. 10 players in a 5v5). Detection runs on every row
          and the whole batch is committed in one transaction.
        </p>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: ".78rem", color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".05em" }}>
            Required columns
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {["player_id","match_id","region","device","ping","score","kills","deaths","match_duration_seconds"].map((c) => (
              <code key={c} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 4, padding: "2px 7px", fontSize: ".78rem", color: "var(--accent2)" }}>
                {c}
              </code>
            ))}
          </div>
        </div>
      </div>

      {/* ── Sample files info ── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title">Sample CSV files</div>
        <p style={{ fontSize: ".82rem", color: "var(--text-muted)", marginBottom: 12 }}>
          Three sample files are in <code style={{ background: "var(--surface2)", padding: "1px 5px", borderRadius: 4 }}>game_ops/sample_data/</code> — download and upload them to test:
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {SAMPLE_FILES.map((s) => (
            <div key={s.name} style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 7, padding: "10px 14px",
              display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
            }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: ".88rem", color: "var(--text)" }}>{s.name}</div>
                <div style={{ fontSize: ".76rem", color: "var(--text-muted)", marginTop: 2 }}>{s.label}</div>
              </div>
              <span style={{ fontSize: ".72rem", fontWeight: 700, color: s.color, border: `1px solid ${s.color}`, borderRadius: 99, padding: "2px 8px" }}>
                {s.name.includes("cheater") ? "Has cheaters 🚩" : "Clean ✓"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Drop zone ── */}
      <div className="card">
        <div className="section-title">Upload Match CSV</div>

        {/* Drop target */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? "var(--accent)" : "var(--border)"}`,
            borderRadius: 10,
            padding: "36px 20px",
            textAlign: "center",
            cursor: "pointer",
            background: dragging ? "rgba(108,99,255,.07)" : "var(--surface2)",
            transition: "all .2s",
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: 8 }}>📁</div>
          {file ? (
            <div>
              <div style={{ fontWeight: 700, color: "var(--text)" }}>{file.name}</div>
              <div style={{ color: "var(--text-muted)", fontSize: ".8rem", marginTop: 4 }}>
                {preview ? `${preview.length} rows detected` : "Parsing…"}
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: ".9rem" }}>
              Drag & drop a <strong>.csv</strong> file here, or click to browse
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={(e) => handleFileChange(e.target.files[0])}
          />
        </div>

        {/* Actions */}
        {file && (
          <div className="form-actions" style={{ marginBottom: 20 }}>
            <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
              {loading ? "Processing…" : `Submit ${preview ? preview.length + " rows" : "CSV"}`}
            </button>
            <button className="btn btn-secondary" onClick={handleReset}>Clear</button>
          </div>
        )}

        {/* Error */}
        {error && <div className="result-banner error" style={{ marginBottom: 16 }}><strong>Error:</strong> {error}</div>}

        {/* Preview table (before submit) */}
        {preview && !result && preview.length > 0 && (
          <div>
            <div style={{ fontSize: ".8rem", color: "var(--text-muted)", marginBottom: 10, textTransform: "uppercase", letterSpacing: ".05em" }}>
              Preview — {preview.length} rows · not submitted yet
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Player</th><th>Match</th><th>Region</th><th>Device</th>
                    <th>Score</th><th>K</th><th>D</th><th>Ping</th><th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 700 }}>{r.player_id}</td>
                      <td className="text-muted">{r.match_id}</td>
                      <td>{r.region}</td>
                      <td>{r.device}</td>
                      <td style={{ fontWeight: 700 }}>{Number(r.score).toLocaleString()}</td>
                      <td>{r.kills}</td>
                      <td>{r.deaths}</td>
                      <td>{r.ping}</td>
                      <td>{r.match_duration_seconds}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Result table (after submit) */}
        {result && (
          <div>
            {/* Summary badges */}
            <div className="stats-bar" style={{ marginBottom: 16 }}>
              <div className="stat-box">
                <div className="stat-box-value">{result.total_rows}</div>
                <div className="stat-box-label">Total Rows</div>
              </div>
              <div className="stat-box">
                <div className="stat-box-value" style={{ color: "var(--accent2)" }}>{result.clean_count}</div>
                <div className="stat-box-label">Clean</div>
              </div>
              <div className="stat-box">
                <div className="stat-box-value" style={{ color: "var(--danger)" }}>{result.flagged_count}</div>
                <div className="stat-box-label">Flagged</div>
              </div>
            </div>

            <div style={{ fontSize: ".8rem", color: "var(--text-muted)", marginBottom: 10, textTransform: "uppercase", letterSpacing: ".05em" }}>
              Results — all rows committed to database
            </div>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Player</th><th>Match</th><th>Region</th><th>Score</th>
                    <th>K</th><th>D</th><th>Ping</th><th>Status</th><th>Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 700 }}>{r.player_id}</td>
                      <td className="text-muted">{r.match_id}</td>
                      <td>{r.region}</td>
                      <td style={{ fontWeight: 700 }}>{r.score.toLocaleString()}</td>
                      <td>{r.kills}</td>
                      <td>{r.deaths}</td>
                      <td>{r.ping}</td>
                      <td>
                        <span className={`flag-pill ${r.flagged ? "flagged" : "clean"}`}>
                          {r.flagged ? "🚩 Flagged" : "✓ Clean"}
                        </span>
                      </td>
                      <td style={{ fontSize: ".75rem", color: "var(--danger)", maxWidth: 260 }}>
                        {r.flag_reasons.join(" · ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
