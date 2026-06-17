# Game Ops System

A backend system for managing multiplayer game events. Ingests player match data, generates a leaderboard, detects suspicious activity, and suggests matchmaking groups.

Built with **FastAPI + PostgreSQL + SQLAlchemy + Pytest**.

---

## Setup

```bash
# 1. Clone the repo and install dependencies
pip install -r requirements.txt

# 2. Create a PostgreSQL database
createdb game_ops_db

# 3. Set environment variable
cp .env.example .env
# Edit .env and set your DATABASE_URL

# 4. Run the server
uvicorn main:app --reload

# 5. Open API docs
# Visit http://localhost:8000/docs
```

---

## API Endpoints

| Method | Endpoint          | Description                          |
|--------|-------------------|--------------------------------------|
| POST   | /submit-score     | Submit a player match result         |
| GET    | /leaderboard      | Get ranked leaderboard (?region=)    |
| GET    | /flagged-players  | Get all flagged/suspicious players   |
| GET    | /matchmaking      | Get suggested matchmaking groups     |

---

## Sample Data (curl)

```bash
# Player 1 — clean player
curl -X POST http://localhost:8000/submit-score \
  -H "Content-Type: application/json" \
  -d '{"player_id":"P001","match_id":"M001","region":"India","device":"Android","ping":55,"score":3200,"kills":18,"deaths":4,"match_duration_seconds":420}'

# Player 2 — clean player
curl -X POST http://localhost:8000/submit-score \
  -H "Content-Type: application/json" \
  -d '{"player_id":"P002","match_id":"M002","region":"India","device":"iOS","ping":62,"score":2800,"kills":14,"deaths":6,"match_duration_seconds":390}'

# Player 3 — suspicious (high kill rate + K/D + score rate)
curl -X POST http://localhost:8000/submit-score \
  -H "Content-Type: application/json" \
  -d '{"player_id":"P003","match_id":"M003","region":"Europe","device":"PC","ping":20,"score":99000,"kills":250,"deaths":0,"match_duration_seconds":60}'

# Player 4 — clean player, different region
curl -X POST http://localhost:8000/submit-score \
  -H "Content-Type: application/json" \
  -d '{"player_id":"P004","match_id":"M004","region":"Europe","device":"Android","ping":75,"score":2500,"kills":12,"deaths":5,"match_duration_seconds":360}'

# Player 5 — clean player, high ping
curl -X POST http://localhost:8000/submit-score \
  -H "Content-Type: application/json" \
  -d '{"player_id":"P005","match_id":"M005","region":"India","device":"PC","ping":145,"score":3100,"kills":16,"deaths":3,"match_duration_seconds":410}'
```

---

## Detection Rules

| Rule           | Threshold                          |
|----------------|------------------------------------|
| Kill rate      | > 15 kills/minute                  |
| Score rate     | > 100 score/second                 |
| Match duration | < 120 seconds                      |
| K/D ratio      | 20+ kills with 0 deaths            |

---

## Running Tests

```bash
# Ensure PostgreSQL is running and DATABASE_URL is set in .env
pytest
```

Tests automatically create and tear down a `game_ops_db_test` database. No manual setup required beyond having PostgreSQL running.

---

## Scaling Notes

- **Read replicas** for leaderboard query load, plus **PgBouncer** connection pooling for high concurrency.
- **Redis sorted set** for real-time leaderboard caching — O(log N) updates per score submission.
- **Async score ingestion queue** (Celery + RabbitMQ or Kafka) to decouple submission spikes from DB writes.
- **Horizontal API scaling** behind a load balancer with stateless FastAPI workers.
