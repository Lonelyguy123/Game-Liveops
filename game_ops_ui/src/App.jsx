import { useState } from "react";
import Dashboard from "./components/Dashboard";
import SubmitScore from "./components/SubmitScore";
import CsvUpload from "./components/CsvUpload";
import Leaderboard from "./components/Leaderboard";
import FlaggedPlayers from "./components/FlaggedPlayers";
import Matchmaking from "./components/Matchmaking";
import "./App.css";

const TABS = [
  { id: "dashboard",   label: "📊  Dashboard"       },
  { id: "submit",      label: "⚔️   Submit Score"    },
  { id: "csv",         label: "📂  Upload CSV"       },
  { id: "leaderboard", label: "🏆  Leaderboard"      },
  { id: "flagged",     label: "🚩  Flagged Players"  },
  { id: "matchmaking", label: "🎮  Matchmaking"      },
];

export default function App() {
  const [tab, setTab] = useState("dashboard");

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">🕹</span>
          <span className="logo-text">Game<span className="logo-accent">Ops</span></span>
        </div>
        <p className="logo-sub">Live Operations Dashboard</p>
      </header>

      <nav className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab-btn${tab === t.id ? " active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="content">
        {tab === "dashboard"   && <Dashboard />}
        {tab === "submit"      && <SubmitScore />}
        {tab === "csv"         && <CsvUpload />}
        {tab === "leaderboard" && <Leaderboard />}
        {tab === "flagged"     && <FlaggedPlayers />}
        {tab === "matchmaking" && <Matchmaking />}
      </main>
    </div>
  );
}
