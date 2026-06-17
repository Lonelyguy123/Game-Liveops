# Game Ops System — Technical Document

---

## 1. Problem Understanding

A multiplayer game generates match results continuously. After each match,
the system needs to:

- Ingest player stats (score, kills, deaths, ping, region, device)
- Maintain a ranked, filterable leaderboard scoped to seasons
- Automatically detect and flag suspicious behaviour (cheating/botting)
- Suggest fair matchmaking groups based on region, skill tier, and ping
- Support season resets where historical data is preserved but the active
  competition starts fresh

The system must handle growing player volume without becoming slow or
difficult to operate.

---

## 2. Assumptions

- A player can play multiple matches per season; the leaderboard aggregates
  all of them.
- Match data arrives either as individual API calls or as a CSV file
  representing one completed match (e.g. 10 players in a 5v5).
- Suspicious players remain on the leaderboard (visible to ops) but are
  excluded from matchmaking.
- Only one season is active at a time. Resetting a season preserves all
  historical data — it only changes what the active leaderboard shows.
- Detection thresholds are fixed constants that ops can adjust in
  `constants.py` without touching application logic.
- Region and device are player-level attributes updated on every submission
  (players may change devices/regions between seasons).

---

## 3. Database Design

### Tables

```
seasons
  id          SERIAL PK
  name        VARCHAR NOT NULL
  is_active   BOOLEAN NOT NULL DEFAULT TRUE
  started_at  TIMESTAMP NOT NULL
  ended_at    TIMESTAMP NULLABLE

players
  player_id   VARCHAR PK
  region      VARCHAR NOT NULL
  device      VARCHAR NOT NULL

matches
  id                      SERIAL PK
  match_id                VARCHAR NOT NULL
  player_id               VARCHAR FK → players.player_id
  season_id               INTEGER FK → seasons.id (nullable for legacy rows)
  region                  VARCHAR NOT NULL
  device                  VARCHAR NOT NULL
  ping                    INTEGER NOT NULL
  score                   INTEGER NOT NULL
  kills                   INTEGER NOT NULL
  deaths                  INTEGER NOT NULL
  match_duration_seconds  INTEGER NOT NULL
  submitted_at            TIMESTAMP NOT NULL DEFAULT NOW()

flagged_players
  id          SERIAL PK
  player_id   VARCHAR FK → players.player_id
  match_id    VARCHAR NOT NULL
  season_id   INTEGER FK → seasons.id (nullable for legacy rows)
  reasons     VARCHAR NOT NULL  ← comma-separated violation strings
  flagged_at  TIMESTAMP NOT NULL DEFAULT NOW()
```

### Key design decisions

- `match_id` is not unique — multiple players share the same match_id
  (all 10 players in a 5v5 game have the same match_id).
- `season_id` on both `matches` and `flagged_players` enables full
  season-scoped queries without duplicating data.
- `reasons` is stored as a comma-joined string for simplicity. In a
  production system this would be a separate `flag_reasons` table or a
  JSON column.
- Player upsert on every submission keeps `players.region` and
  `players.device` current without a separate update endpoint.

---

## 4. Leaderboard Logic

```
For each player in the active season:
  1. Filter their matches to the requested season_id
  2. Aggregate: total_score, total_kills, total_deaths, matches_played
  3. Derive primary_region (most frequent region across their matches)
  4. Mark is_flagged if any row exists in flagged_players (all-time)
  5. Apply optional region filter (case-insensitive)

Sort order:
  1. total_score  DESC  (primary ranking)
  2. total_deaths ASC   (tiebreak: fewer deaths wins)
  3. total_kills  DESC  (secondary tiebreak)

Assign sequential rank starting at 1.
```

Region-wise leaderboard: pass `?region=India` to `GET /leaderboard`.
Season-wise: pass `?season_id=1`. Both filters can be combined.

---

## 5. Suspicious Player Detection Logic

Detection runs synchronously on every match submission (individual or CSV).
It is a pure function — no database access, testable in isolation.

| Rule             | Threshold                              | Reason stored             |
|------------------|----------------------------------------|---------------------------|
| Kill rate        | > 15 kills/minute                      | "Kill rate X/min…"        |
| Score rate       | > 100 score/second                     | "Score rate X/sec…"       |
| Match duration   | < 120 seconds                          | "Match duration Xs…"      |
| K/D ratio        | ≥ 20 kills with 0 deaths               | "Suspicious K/D: X kills" |

All four rules run on every submission. A player can be flagged for
multiple reasons simultaneously. Flagged players:
- Remain visible on the leaderboard (`is_flagged = True`)
- Are excluded from matchmaking groups entirely

---

## 6. Matchmaking Logic

```
For each non-flagged player with at least one match:
  1. Compute avg_score, avg_ping, primary_region
  2. Assign skill_tier:
       avg_score < 2000 → LOW
       avg_score < 4000 → MID
       avg_score ≥ 4000 → HIGH

Group players by (primary_region, skill_tier)

Within each group, sort by avg_ping ascending, then apply
sliding-window split:
  - Start a new subgroup when:
      current_player.avg_ping - first_player_in_subgroup.avg_ping > 80ms

Output: list of groups with group_id, region, skill_tier,
        player_ids, avg_ping
```

This ensures players only face others of similar skill and connection
quality, and never cross-region in the same game.

---

## 7. Architecture

```
                        ┌─────────────────────────────────────┐
                        │           React Frontend             │
                        │  (Vite · Dashboard · Leaderboard    │
                        │   Flagged · Matchmaking · CSV Upload)│
                        └──────────────┬──────────────────────┘
                                       │ HTTP / JSON
                        ┌──────────────▼──────────────────────┐
                        │         FastAPI (Python 3.14)        │
                        │                                      │
                        │  POST /submit-score                  │
                        │  POST /upload-csv                    │
                        │  GET  /leaderboard[?region&season]   │
                        │  GET  /flagged-players               │
                        │  GET  /matchmaking                   │
                        │  GET  /dashboard                     │
                        │  POST /seasons/reset                 │
                        └──────┬──────────────┬───────────────┘
                               │              │
                ┌──────────────▼──┐    ┌──────▼──────────────┐
                │  Service Layer   │    │  Detection Service   │
                │  leaderboard.py  │    │  detection.py        │
                │  matchmaking.py  │    │  (pure functions,    │
                │  season.py       │    │   no DB access)      │
                │  csv_ingest.py   │    └─────────────────────┘
                └──────┬──────────┘
                       │ SQLAlchemy ORM
                ┌──────▼──────────────┐
                │   PostgreSQL         │
                │  seasons             │
                │  players             │
                │  matches             │
                │  flagged_players     │
                └─────────────────────┘
```

**Layering rules:**
- Route handlers contain zero business logic — they only call service
  functions and construct response schemas
- Detection is a pure stateless function — fully unit-testable without
  a database
- All constants live in `constants.py` — no magic numbers anywhere else

---

## 8. Scaling Plan

### Current state (2,000 players)
Single FastAPI process + single PostgreSQL instance. Handles this
comfortably with synchronous SQLAlchemy sessions.

### Growing to 200,000 players

**Database**
- Add indexes on `matches(player_id, season_id)` and
  `flagged_players(player_id, season_id)` — leaderboard queries go
  from O(n) Python aggregation to O(1) SQL GROUP BY
- Move leaderboard aggregation into a PostgreSQL view or materialised view
  that refreshes on a schedule (e.g. every 30 seconds) instead of computing
  on every request
- Connection pooling via **PgBouncer** to prevent connection exhaustion
  under high concurrency
- Read replica for leaderboard / dashboard reads so writes and reads
  don't compete on the same node

**API layer**
- Move to async FastAPI (`async def`) with an async ORM (SQLAlchemy async
  session) or switch the leaderboard path to raw SQL with asyncpg
- Run multiple uvicorn workers behind **Nginx** or a cloud load balancer
- Containerise with Docker and deploy on **Kubernetes** (HPA scales worker
  pods based on CPU/RPS)

**Leaderboard at scale**
- Cache the leaderboard in **Redis** (sorted set, `ZADD`/`ZRANGE`) —
  O(log N) updates on each score submission, O(1) rank lookups
- Invalidate or update the cache entry on every `POST /submit-score`
- Serve `/leaderboard` from Redis, fall back to PostgreSQL on cache miss

**Score ingestion**
- At very high match rates, decouple submission from DB writes with an
  async queue (**Kafka** or **RabbitMQ**)
- API writes to queue → worker pool consumes and batch-inserts into
  PostgreSQL → dramatically reduces DB write pressure

**Detection**
- Detection is already a pure, stateless function — it can be offloaded to
  a separate microservice or a serverless function (AWS Lambda) with zero
  DB dependency, then called asynchronously from the queue worker

### Growing beyond 200,000 players

- Partition the `matches` table by `season_id` — historical seasons become
  read-only archived partitions
- Shard by region if needed (India, Europe, NA on separate DB clusters)
- Use **CDN** (CloudFront, Cloudflare) to cache `/leaderboard` responses
  at the edge for spectators who only read

---

## 9. Limitations

| Limitation | Detail |
|------------|--------|
| In-process aggregation | Leaderboard aggregation iterates over all players in Python. Correct for small scale; needs SQL GROUP BY or Redis at 10k+ players |
| Synchronous ORM | SQLAlchemy synchronous sessions block threads. Fine for current load; needs async session or connection pool tuning for high concurrency |
| Single active season constraint | Enforced in application code, not database — a bug could leave two active rows. A DB partial unique index on `is_active = TRUE` would enforce this at the DB level |
| reasons as CSV string | `flagged_players.reasons` is a comma-joined string. Parsing is fragile if a reason text ever contains a comma. A proper solution uses a `flag_reasons` junction table |
| No auth/rate limiting | Endpoints are open — any caller can submit scores or trigger a season reset. Production needs authentication and per-IP rate limiting |
| UTC timestamps | `datetime.utcnow()` is deprecated in Python 3.12+. Should migrate to `datetime.now(UTC)` with timezone-aware columns |
| No pagination | `/leaderboard` returns all players in one response. At 10k+ players this becomes a large payload; needs `limit/offset` or cursor-based pagination |

---

## 10. API Summary

| Method | Endpoint            | Description                                 |
|--------|---------------------|---------------------------------------------|
| POST   | /submit-score       | Submit one player's match result            |
| POST   | /upload-csv         | Batch-ingest a full match CSV (N players)   |
| GET    | /leaderboard        | Ranked leaderboard (?region= ?season_id=)   |
| GET    | /flagged-players    | All suspicious players (?season_id=)        |
| GET    | /matchmaking        | Suggested matchmaking groups                |
| GET    | /dashboard          | Aggregated ops stats (season-scoped)        |
| GET    | /seasons            | List all seasons                            |
| GET    | /seasons/active     | Get the current active season               |
| POST   | /seasons            | Create a new season (closes current)        |
| POST   | /seasons/reset      | Reset: close active, open new season        |
