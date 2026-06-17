"""
locustfile.py

Load testing plan for the Game Ops API using Locust.

Usage:
    pip install locust
    locust -f locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 and set:
    - Number of users:  e.g. 100
    - Spawn rate:       e.g. 10 users/second

Or run headless:
    locust -f locustfile.py --host=http://localhost:8000 \\
           --users 100 --spawn-rate 10 --run-time 60s --headless

---
Test Scenarios
--------------
1. SubmitScoreUser   — Heavy write load (POST /submit-score)
   Simulates concurrent players submitting match results.
   Mix of clean and suspicious payloads to exercise detection.
   Weight: 60% of virtual users (most traffic is writes).

2. LeaderboardUser   — Read-heavy leaderboard polling
   Simulates spectators/dashboards polling the leaderboard.
   Includes region-filtered requests.
   Weight: 25% of virtual users.

3. OpsUser           — Ops admin activity
   Polls /flagged-players, /matchmaking, /dashboard, /seasons.
   Lower volume; exercises all read endpoints.
   Weight: 15% of virtual users.

---
Performance Targets (suggested baselines for a single-node instance)
----------------------------------------------------------------------
| Endpoint          | p50   | p95    | p99    | Error rate |
|-------------------|-------|--------|--------|------------|
| POST /submit-score| <80ms | <200ms | <400ms | <0.1%      |
| GET /leaderboard  | <50ms | <150ms | <300ms | <0.1%      |
| GET /flagged-players|<40ms| <120ms | <250ms | <0.1%      |
| GET /matchmaking  | <60ms | <180ms | <350ms | <0.1%      |
| GET /dashboard    | <40ms | <100ms | <200ms | <0.1%      |
"""

import random
import uuid

from locust import HttpUser, between, task


# ── Shared helpers ─────────────────────────────────────────────────────────

REGIONS  = ["India", "Europe", "NA", "SEA", "LATAM"]
DEVICES  = ["Android", "iOS", "PC", "Console"]


def _clean_payload() -> dict:
    """Generates a realistic clean match submission."""
    return {
        "player_id": f"P{random.randint(1, 500):04d}",
        "match_id":  str(uuid.uuid4())[:8],
        "region":    random.choice(REGIONS),
        "device":    random.choice(DEVICES),
        "ping":      random.randint(20, 120),
        "score":     random.randint(800, 6000),
        "kills":     random.randint(4, 25),
        "deaths":    random.randint(1, 10),
        "match_duration_seconds": random.randint(180, 600),
    }


def _suspicious_payload() -> dict:
    """Generates a suspicious match submission that will trigger detection."""
    return {
        "player_id": f"P{random.randint(501, 600):04d}",
        "match_id":  str(uuid.uuid4())[:8],
        "region":    random.choice(REGIONS),
        "device":    random.choice(DEVICES),
        "ping":      random.randint(5, 30),
        "score":     random.randint(80000, 120000),
        "kills":     random.randint(200, 300),
        "deaths":    0,
        "match_duration_seconds": random.randint(30, 90),
    }


# ── Scenario 1: High-volume score submission ────────────────────────────────

class SubmitScoreUser(HttpUser):
    """
    Simulates concurrent players posting match results.

    - 80% of submissions are clean players.
    - 20% are suspicious, exercising the full detection pipeline.
    - Wait time: 0.5–2s between requests (rapid submission scenario).
    """

    weight    = 60
    wait_time = between(0.5, 2)

    @task(4)
    def submit_clean(self):
        """POST /submit-score with valid, clean match data."""
        self.client.post(
            "/submit-score",
            json=_clean_payload(),
            name="POST /submit-score [clean]",
        )

    @task(1)
    def submit_suspicious(self):
        """POST /submit-score with suspicious data (triggers detection rules)."""
        self.client.post(
            "/submit-score",
            json=_suspicious_payload(),
            name="POST /submit-score [suspicious]",
        )


# ── Scenario 2: Leaderboard polling ────────────────────────────────────────

class LeaderboardUser(HttpUser):
    """
    Simulates spectators or dashboards polling the leaderboard.

    - Mix of global and region-filtered requests.
    - Wait time: 1–5s (polling cadence).
    """

    weight    = 25
    wait_time = between(1, 5)

    @task(3)
    def get_leaderboard_global(self):
        """GET /leaderboard — no filter."""
        self.client.get("/leaderboard", name="GET /leaderboard [global]")

    @task(2)
    def get_leaderboard_by_region(self):
        """GET /leaderboard?region=X — region-filtered."""
        region = random.choice(REGIONS)
        self.client.get(
            f"/leaderboard?region={region}",
            name="GET /leaderboard [region]",
        )

    @task(1)
    def get_leaderboard_by_season(self):
        """GET /leaderboard?season_id=1 — first season."""
        self.client.get(
            "/leaderboard?season_id=1",
            name="GET /leaderboard [season]",
        )


# ── Scenario 3: Ops admin read traffic ─────────────────────────────────────

class OpsUser(HttpUser):
    """
    Simulates ops/admin tooling hitting read endpoints.

    Lower frequency, but exercises every endpoint.
    Wait time: 2–8s (manual/dashboard polling cadence).
    """

    weight    = 15
    wait_time = between(2, 8)

    @task(3)
    def get_flagged_players(self):
        """GET /flagged-players."""
        self.client.get("/flagged-players", name="GET /flagged-players")

    @task(2)
    def get_matchmaking(self):
        """GET /matchmaking."""
        self.client.get("/matchmaking", name="GET /matchmaking")

    @task(3)
    def get_dashboard(self):
        """GET /dashboard."""
        self.client.get("/dashboard", name="GET /dashboard")

    @task(1)
    def list_seasons(self):
        """GET /seasons."""
        self.client.get("/seasons", name="GET /seasons")

    @task(1)
    def get_active_season(self):
        """GET /seasons/active."""
        self.client.get("/seasons/active", name="GET /seasons/active")
