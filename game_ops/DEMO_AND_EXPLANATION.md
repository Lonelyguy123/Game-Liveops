# Game Ops System — Complete Guide
### Everything you need to understand, run, and demo the project

---

## PART 1 — What This Project Is (Plain English)

Imagine you run a multiplayer mobile game. After every match, your servers
collect data — who played, what their score was, how many kills, how long
the match lasted, where they are, what device they used.

This system is the **backend brain** that handles all of that data. It does
four things automatically:

1. **Stores** every match result in a database
2. **Ranks** players on a leaderboard (season-scoped, region-filterable)
3. **Detects cheaters** by running rule-based checks on every match
4. **Suggests fair matches** by grouping players with similar skill and ping

It also has a **React web dashboard** so you can see everything live.

---

## PART 2 — Project Structure (What Every File Does)

```
game_ops/
│
├── main.py              ← The API server. Defines all 10 REST endpoints.
│                          No business logic here — just routes and responses.
│
├── database.py          ← Database connection setup. Reads DATABASE_URL
│                          from .env, creates the SQLAlchemy engine and
│                          session factory. get_db() is the dependency
│                          injected into every route.
│
├── models.py            ← The 4 database tables as Python classes:
│                          Season, Player, Match, FlaggedPlayer
│
├── schemas.py           ← Pydantic models for request/response validation.
│                          FastAPI auto-generates API docs from these.
│
├── constants.py         ← ALL detection thresholds live here.
│                          Never hardcoded anywhere else. Change a number
│                          here and every rule updates automatically.
│
├── .env                 ← Database connection string (not committed to git)
│
├── locustfile.py        ← Load testing scenarios (3 user types)
│
├── TECHNICAL_DOCUMENT.md  ← Formal 2-page submission document
├── MONITORING.md           ← Monitoring and alerting plan
│
├── services/
│   ├── detection.py     ← Cheater detection. Pure functions, no database.
│   │                      Takes match data, returns list of violation reasons.
│   │
│   ├── leaderboard.py   ← Leaderboard aggregation. Queries DB, aggregates
│   │                      per player, sorts, assigns ranks.
│   │
│   ├── matchmaking.py   ← Groups clean players by region+tier+ping.
│   │
│   ├── season.py        ← Season create/reset/dashboard stats.
│   │
│   └── csv_ingest.py    ← Parses CSV bytes, validates columns, bulk-inserts
│                          all rows in one DB transaction.
│
├── tests/
│   ├── conftest.py         ← Pytest fixtures. Auto-creates test DB.
│   │                          Each test gets a fresh schema, torn down after.
│   ├── test_detection.py   ← 5 pure unit tests (no DB needed)
│   ├── test_leaderboard.py ← 4 integration tests
│   ├── test_matchmaking.py ← 4 integration tests
│   ├── test_seasons.py     ← 6 integration tests
│   └── test_csv_ingest.py  ← 12 tests (7 unit + 5 integration)
│
└── sample_data/
    ├── match_clean_5v5.csv       ← 10 clean players, India vs Europe
    ├── match_with_cheaters.csv   ← 10 players, 3 obvious cheaters
    └── match_multiregion.csv     ← 10 clean players, SEA vs LATAM

game_ops_ui/src/
├── App.jsx              ← Tab shell (6 tabs)
├── api.js               ← All fetch calls to the backend
└── components/
    ├── Dashboard.jsx    ← KPI stats + season history + reset button
    ├── SubmitScore.jsx  ← Manual form + 5 sample player quick-load buttons
    ├── CsvUpload.jsx    ← Drag-drop CSV uploader with preview + results table
    ├── Leaderboard.jsx  ← Ranked table with season + region filters
    ├── FlaggedPlayers.jsx ← Cards showing flagged players + violation tags
    └── Matchmaking.jsx  ← Group cards with tier badge + player list
```

---

## PART 3 — The Database (4 Tables Explained)

### Why 4 tables?

```
seasons ──────────┐
                  │ one season has many matches
players ──────────┤
        │         │ one player has many matches
        │         ▼
        └──── matches ──── (every match row = one player's stats in one game)
        │
        └──── flagged_players ─── (created when detection finds a violation)
```

### Table: seasons
Tracks competitive seasons. Only one can be `is_active = TRUE` at a time.
When you reset, the old season gets `ended_at` stamped and `is_active = FALSE`.
The new season starts fresh. All old data is preserved — just not in the
active leaderboard.

### Table: players
One row per unique `player_id`. Stores region and device. These get
**updated** (upserted) on every submission — so if a player switches from
Android to PC, the record stays current.

### Table: matches
One row per **player per match**. In a 5v5 game with 10 players, all 10
rows share the same `match_id` but have different `player_id` values.
Every row is stamped with `season_id` so the leaderboard knows which
season to aggregate from.

### Table: flagged_players
Created whenever detection finds a violation. Stores the comma-joined
reasons string (e.g. `"Kill rate 250.0/min exceeds max 15/min,Suspicious K/D: 250 kills with 0 deaths"`).
Also stamped with `season_id` for season-scoped flagged lists.

---

## PART 4 — How Each Feature Works

### A. Score Submission (`POST /submit-score`)

```
Request arrives
    ↓
Get or auto-create active season
    ↓
Upsert player (create if new, update region/device if existing)
    ↓
Insert match row with season_id
    ↓
Run detection.check_suspicious(match_data)
    ↓
If violations found → insert FlaggedPlayer row
    ↓
Commit everything in one transaction
    ↓
Return: { flagged: true/false, flag_reasons: [...] }
```

### B. CSV Upload (`POST /upload-csv`)

Same flow as above but for an entire file at once. The whole batch
(e.g. 10 players from a 5v5) commits in a **single transaction** —
either all rows land or none do. This prevents partial data from
a corrupted or interrupted upload.

### C. Leaderboard (`GET /leaderboard`)

```
Load all players from DB
    ↓
For each player:
  - Filter their matches to the active season (or requested season_id)
  - Sum: total_score, total_kills, total_deaths
  - Count: matches_played
  - Find primary_region (most common region in their matches)
  - Check: is_flagged (any row in flagged_players for this player?)
    ↓
Apply optional region filter (case-insensitive string match)
    ↓
Sort: total_score DESC → total_deaths ASC → total_kills DESC
    ↓
Assign rank 1, 2, 3... sequentially
    ↓
Return list
```

**Key point:** Flagged players are NOT removed from the leaderboard.
Ops can see them — they just show a 🚩 badge. This is intentional
so you can identify the scope of cheating without hiding it.

### D. Cheater Detection (`services/detection.py`)

Four independent rules, all run on every submission:

| Rule | What it checks | Why it catches cheaters |
|------|---------------|-------------------------|
| Kill rate | kills ÷ (duration ÷ 60) > 15/min | A human can't reliably kill 15 players per minute — aimbots do |
| Score rate | score ÷ duration > 100/sec | Impossible to score 100 points every second legitimately |
| Match duration | duration < 120 seconds | Matches shorter than 2 minutes indicate exploit abuse or fake submissions |
| K/D ratio | deaths == 0 AND kills ≥ 20 | Going 20-0 is extremely unlikely; 250-0 is impossible |

Multiple rules can trigger on the same submission. Each adds a separate
human-readable reason string.

**This is a pure function.** It takes a dict, returns a list. No database
involved. That's why it's so fast and easy to test.

### E. Matchmaking (`GET /matchmaking`)

```
Load all players who are NOT in flagged_players
    ↓
For each clean player:
  - avg_score across all matches → skill tier (LOW / MID / HIGH)
      LOW  = avg_score < 2,000
      MID  = avg_score < 4,000
      HIGH = avg_score ≥ 4,000
  - avg_ping across all matches
  - primary_region (most common)
    ↓
Group by (region, skill_tier)
    ↓
Within each group, sort by avg_ping ascending
Apply sliding window:
  - If next player's ping - first player in current group's ping > 80ms
  → start a new subgroup
    ↓
Assign sequential group_id, compute group avg_ping
    ↓
Return list of groups
```

**Why exclude flagged players?** You don't want confirmed cheaters
to ruin fair matchmaking for legitimate players.

**Why the 80ms ping window?** A 80ms ping difference is noticeable as
lag in real gameplay. Players within 80ms of each other will have
a smooth experience.

### F. Season Reset (`POST /seasons/reset`)

```
Request: { "name": "Season 3" }
    ↓
Find active season → set is_active=FALSE, ended_at=now()
    ↓
Create new season → set is_active=TRUE
    ↓
Return both season objects
```

After reset:
- `GET /leaderboard` → empty (no matches in new season yet)
- `GET /leaderboard?season_id=1` → old season data still there
- All match/flag history preserved forever

### G. Dashboard (`GET /dashboard`)

Single endpoint that computes and returns:
- Total players ever registered
- Matches in the **active season** only
- Flags in the **active season** only
- Total seasons count
- Active season details
- Top player (highest total score in active season)
- Clean rate % (players with zero flags ÷ total players × 100)

---

## PART 5 — REST API Reference

All endpoints are at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

```
POST   /submit-score
  Body: { player_id, match_id, region, device, ping, score,
          kills, deaths, match_duration_seconds }
  Returns: { message, player_id, match_id, flagged, flag_reasons }

POST   /upload-csv
  Body: multipart/form-data, field name "file", .csv only
  Returns: { total_rows, flagged_count, clean_count, results: [...] }

GET    /leaderboard
  Query: ?region=India  (optional)
         &season_id=1   (optional, defaults to active season)
  Returns: { total_players, entries: [{rank, player_id, region,
             total_score, total_kills, total_deaths, matches_played,
             is_flagged}] }

GET    /flagged-players
  Query: ?season_id=1   (optional, defaults to active season)
  Returns: { total_flagged, players: [{player_id, match_id,
             reasons, flagged_at}] }

GET    /matchmaking
  Returns: { total_groups, groups: [{group_id, region, skill_tier,
             player_ids, avg_ping}] }

GET    /dashboard
  Returns: { total_players, total_matches, total_flagged,
             total_seasons, active_season, top_player_id,
             top_player_score, clean_rate_pct }

GET    /seasons
  Returns: list of all seasons

GET    /seasons/active
  Returns: current active season (404 if none)

POST   /seasons
  Body: { "name": "Season 2" }
  Returns: new season info (201 Created)

POST   /seasons/reset
  Body: { "name": "Season 2" }
  Returns: { message, closed_season, new_season }
```

---

## PART 6 — HOW TO RUN EVERYTHING (Step by Step)

### Prerequisites
- PostgreSQL 18 running on localhost:5432
- Python 3.14 venv already set up at `..\venv`
- Node.js 24 installed

---

### Step 1 — Check your .env file

Open `game_ops/.env` and confirm your PostgreSQL password:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/game_ops_db
```
Replace `YOUR_PASSWORD` with the password you set when you installed PostgreSQL.

---

### Step 2 — Create the database (only needed once)

Open a new PowerShell window and run:
```powershell
$env:PGPASSWORD = "YOUR_PASSWORD"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE game_ops_db;"
```

You should see: `CREATE DATABASE`

---

### Step 3 — Start the backend API server

```powershell
cd "c:\Users\ADMIN\Downloads\game liveops architecture\game_ops"
..\venv\Scripts\uvicorn.exe main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Leave this terminal open. The `--reload` flag means the server
automatically restarts when you save any Python file.

---

### Step 4 — Start the React frontend

Open a **second** PowerShell window:
```powershell
cd "c:\Users\ADMIN\Downloads\game liveops architecture\game_ops_ui"
npm run dev
```

Expected output:
```
VITE v8.x  ready in 200ms
➜  Local: http://localhost:5173/
```

(It may say 5174 if 5173 is busy — both are fine.)

Open your browser: **http://localhost:5173** (or 5174)

---

### Step 5 — Run the automated test suite

Open a **third** PowerShell window:
```powershell
cd "c:\Users\ADMIN\Downloads\game liveops architecture\game_ops"
..\venv\Scripts\pytest.exe tests/ -v
```

Expected: **31 passed** in ~2 seconds.

The tests use a separate database (`game_ops_db_test`) that is
created automatically and wiped after each test.

---

### Step 6 — Run the load test

In a **fourth** PowerShell window (keep the API server running):
```powershell
& "c:\Users\ADMIN\Downloads\game liveops architecture\venv\Scripts\locust.exe" -f "c:\Users\ADMIN\Downloads\game liveops architecture\game_ops\locustfile.py" --host=http://localhost:8000
```

Open **http://localhost:8089**

Set:
- Number of users: `50`
- Spawn rate: `5`
- Click **Start swarming**

Watch requests/sec and response times in real time.

---

## PART 7 — DEMO VIDEO SCRIPT (What to Show and Say)

### Scene 1 — Show the running servers (30 seconds)

Show terminal 1: uvicorn running
Show terminal 2: npm dev running
Open browser: `http://localhost:5174`

**Say:** "This is the Game Ops live operations dashboard. It's a full-stack
system — FastAPI backend with PostgreSQL, and a React frontend. Let me walk
you through each feature."

---

### Scene 2 — Dashboard tab (30 seconds)

Click **📊 Dashboard** tab.

It will show 0 everywhere since nothing is submitted yet.

**Say:** "The dashboard gives ops teams a live snapshot — total players,
matches this season, flagged players, the top-scoring player, and what
percentage of players are clean."

---

### Scene 3 — Submit individual scores (1 minute)

Click **⚔️ Submit Score** tab.

Click the **P001** button (quick-load sample). Click **Submit Score**.
Green banner: "✅ Score submitted — P001 / M001 — clean"

Click **P003** button. Click **Submit Score**.
Red banner: "🚩 Player flagged!" with 3 violation reasons.

**Say:** "Every time a match finishes, we submit the player's stats.
The system runs four detection rules instantly — kill rate, score rate,
match duration, and K/D ratio. P003 triggered all of them: 250 kills
in 60 seconds, 99,000 score in 60 seconds — obviously a cheater."

Submit P002, P004, P005 as well (click each button, submit).

---

### Scene 4 — Upload CSV (1 minute)

Click **📂 Upload CSV** tab.

**Say:** "In a real game, when a 5v5 match ends, we get a CSV with all
10 players at once. Let me show that."

Drag and drop `game_ops/sample_data/match_with_cheaters.csv` onto
the drop zone.

The preview table appears showing 10 rows.

**Say:** "The browser shows a preview of all rows before anything is submitted."

Click **Submit 10 rows**.

Results table appears: 7 clean (green), 3 flagged (red) with reason text.

**Say:** "Three cheaters detected automatically. All 10 rows committed to
the database in one transaction."

---

### Scene 5 — Leaderboard (45 seconds)

Click **🏆 Leaderboard** tab.

Shows all submitted players ranked. P003 has a 🚩 Flagged badge.

**Say:** "The leaderboard ranks players by total score. Flagged players
still appear — ops need to see them — but they're clearly marked.
The tiebreak is fewer deaths first, then more kills."

Type `India` in the region filter box. Click **Apply**.

Shows only India-region players.

**Say:** "You can filter by region — useful for regional tournaments
or region-specific leaderboards."

---

### Scene 6 — Flagged Players (30 seconds)

Click **🚩 Flagged Players** tab.

Cards show P003 and the 3 cheaters from the CSV with their violation tags.

**Say:** "Every flagged player has a card showing which match triggered it,
when it was flagged, and exactly which rules fired. Ops can use this to
review and take action."

---

### Scene 7 — Matchmaking (45 seconds)

Click **🎮 Matchmaking** tab.

Shows groups of clean players.

**Say:** "Matchmaking excludes all flagged players entirely. Clean players
are grouped first by region — you never mix India and Europe in one match.
Then by skill tier: LOW under 2000 avg score, MID up to 4000, HIGH above.
Then by ping — if two players in the same tier have more than 80ms ping
difference, they go into separate groups. This ensures fair, lag-free games."

---

### Scene 8 — Season Reset (1 minute)

Click **📊 Dashboard** tab.

**Say:** "Now let me show season management — one of the bonus features."

In the Season Reset card, type `Season 2`. Click **Reset Season**.

Success banner appears. Season history shows Season 1 closed, Season 2 active.

Click **🏆 Leaderboard** tab.

Shows 0 players — new season, clean slate.

**Say:** "After reset, the leaderboard is empty. The new season starts fresh.
But watch this."

Click the season dropdown. Select Season 1.

Old data appears — all previous players still ranked.

**Say:** "All historical data is fully preserved. You can always look back
at any previous season. The data is just scoped by season_id in the database."

---

### Scene 9 — Automated Tests (30 seconds)

Switch to terminal 3. Show pytest output.

**Say:** "31 automated tests — pure unit tests for detection logic,
integration tests for every endpoint, season isolation tests, CSV ingestion
tests. All passing in under 3 seconds."

Point out: "The test database is created and torn down automatically.
No manual setup."

---

### Scene 10 — Load Test (30 seconds)

Switch to browser tab with Locust at `http://localhost:8089`.

**Say:** "For load testing, I used Locust with three user scenarios —
60% are players submitting match results, 25% are spectators polling
the leaderboard, 15% are ops admins hitting the dashboard and flagged
player endpoints. You can see response times and requests per second
in real time."

---

## PART 8 — Explaining the Architecture (If Asked)

**"Why FastAPI?"**
FastAPI gives you automatic API documentation, built-in Pydantic
validation, and dependency injection — perfect for a data-intensive
backend. Every request body is validated before your code even runs.

**"Why PostgreSQL?"**
Relational data with foreign keys is the right fit here. Player → Match
is a one-to-many relationship. Season scoping via foreign keys is clean.
At scale, PostgreSQL read replicas and materialised views handle the
leaderboard query load.

**"Why is detection a pure function with no DB?"**
Speed and testability. A pure function takes data in, returns data out,
with no side effects. You can test all four detection rules without
a database connection at all — that's why test_detection.py runs in
milliseconds.

**"What would you change for 200,000 players?"**
Three things: (1) Move leaderboard aggregation from Python loops to a
PostgreSQL materialised view that refreshes every 30 seconds. (2) Cache
the leaderboard in Redis sorted sets — O(log N) updates on each submit.
(3) Decouple score ingestion from DB writes using a Kafka queue so
submission spikes don't hammer the database.

**"Why does the leaderboard show flagged players?"**
Intentional design. Ops need to know where cheaters rank — removing them
would hide the scale of the problem. They're visible but clearly marked.
Matchmaking is the place where they get excluded.

---

## PART 9 — Key Numbers to Remember

| Thing | Value |
|-------|-------|
| Kill rate threshold | 15 kills/minute |
| Score rate threshold | 100 points/second |
| Min match duration | 120 seconds (2 minutes) |
| K/D zero-deaths threshold | 20+ kills with 0 deaths |
| Matchmaking ping window | 80ms max difference in a group |
| Skill tier LOW | avg score < 2,000 |
| Skill tier MID | avg score 2,000–4,000 |
| Skill tier HIGH | avg score ≥ 4,000 |
| Total test cases | 31 (all passing) |
| Total API endpoints | 10 |
| Total DB tables | 4 |

---

## PART 10 — Troubleshooting Common Issues

| Problem | Fix |
|---------|-----|
| `uvicorn not recognized` | Run from inside `game_ops/` folder using `..\venv\Scripts\uvicorn.exe` |
| `DATABASE_URL not set` | Check `.env` file exists in `game_ops/` and has the correct password |
| `password authentication failed` | Update the password in `.env` to match your PostgreSQL password |
| `psycopg2 connection refused` | PostgreSQL service isn't running — start it from Windows Services |
| Frontend shows CORS error | Make sure the backend is running on port 8000, not another port |
| Leaderboard shows 0 after reset | Correct — new season is empty. Submit scores or use season dropdown to view old data |
| Port 5173 already in use | Vite automatically uses 5174 — check the terminal output for the actual URL |
| `locust not recognized` | Use the full path: `& "c:\...\venv\Scripts\locust.exe"` |
