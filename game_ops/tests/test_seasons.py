"""
test_seasons.py

Integration tests for season management and season-scoped leaderboard.
Verifies: season creation, reset isolation, cross-season data integrity.
"""

DEFAULT_PAYLOAD = {
    "player_id": "P001",
    "match_id": "M001",
    "region": "India",
    "device": "Android",
    "ping": 55,
    "score": 3200,
    "kills": 18,
    "deaths": 4,
    "match_duration_seconds": 420,
}


def submit(client, overrides=None):
    """Submit a match score using the default payload merged with overrides."""
    payload = {**DEFAULT_PAYLOAD, **(overrides or {})}
    return client.post("/submit-score", json=payload)


# ---------------------------------------------------------------------------
# Season creation
# ---------------------------------------------------------------------------


def test_first_submit_auto_creates_season(client):
    """
    Submitting a score when no season exists should automatically
    create Season 1 and return 200.
    """
    res = submit(client, {"player_id": "P001", "match_id": "M001"})
    assert res.status_code == 200

    active = client.get("/seasons/active")
    assert active.status_code == 200
    data = active.json()
    assert data["is_active"] is True
    assert data["name"] == "Season 1"


def test_create_season_endpoint(client):
    """
    POST /seasons should create a new active season and deactivate the old one.
    """
    # Submit to auto-create Season 1
    submit(client)

    # Manually create Season 2
    res = client.post("/seasons", json={"name": "Season 2"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Season 2"
    assert data["is_active"] is True

    # Season 1 should now be closed
    all_seasons = client.get("/seasons").json()
    season1 = next(s for s in all_seasons if s["name"] == "Season 1")
    assert season1["is_active"] is False


# ---------------------------------------------------------------------------
# Season reset
# ---------------------------------------------------------------------------


def test_season_reset_isolates_leaderboard(client):
    """
    After a season reset, the new season's leaderboard should be empty
    until new matches are submitted. Old season data is preserved.
    """
    # Submit in Season 1
    submit(client, {"player_id": "P001", "match_id": "M001", "score": 5000})

    s1 = client.get("/seasons/active").json()
    s1_id = s1["id"]

    # Leaderboard in Season 1 has P001
    lb_s1 = client.get(f"/leaderboard?season_id={s1_id}").json()
    assert lb_s1["total_players"] == 1

    # Reset to Season 2
    reset = client.post("/seasons/reset", json={"name": "Season 2"})
    assert reset.status_code == 200
    reset_data = reset.json()
    assert "Season 2" in reset_data["message"]

    # New active season leaderboard is empty
    lb_new = client.get("/leaderboard").json()
    assert lb_new["total_players"] == 0

    # Old season leaderboard still intact
    lb_old = client.get(f"/leaderboard?season_id={s1_id}").json()
    assert lb_old["total_players"] == 1
    assert lb_old["entries"][0]["player_id"] == "P001"


def test_reset_without_active_season_returns_400(client):
    """
    POST /seasons/reset when no active season exists should return 400.
    """
    # No submits — no active season
    res = client.post("/seasons/reset", json={"name": "Season X"})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Season-scoped flagged players
# ---------------------------------------------------------------------------


def test_flagged_players_scoped_to_season(client):
    """
    Flagged player from Season 1 should not appear in Season 2's
    flagged list, but should be visible when querying Season 1.
    """
    submit(client, {
        "player_id": "P_CHEAT",
        "match_id": "M_CHEAT",
        "kills": 250, "score": 99000,
        "match_duration_seconds": 60, "deaths": 0,
    })

    s1 = client.get("/seasons/active").json()
    s1_id = s1["id"]

    # Season 1 has the flagged player
    flagged_s1 = client.get(f"/flagged-players?season_id={s1_id}").json()
    assert flagged_s1["total_flagged"] == 1

    # Reset to Season 2
    client.post("/seasons/reset", json={"name": "Season 2"})

    # Season 2 flagged list is empty
    flagged_s2 = client.get("/flagged-players").json()
    assert flagged_s2["total_flagged"] == 0


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_returns_correct_stats(client):
    """
    GET /dashboard should return accurate counts for the active season.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "score": 4000})
    submit(client, {"player_id": "P002", "match_id": "M002", "score": 3000})
    submit(client, {
        "player_id": "P003", "match_id": "M003",
        "kills": 250, "score": 99000,
        "match_duration_seconds": 60, "deaths": 0,
    })

    res = client.get("/dashboard")
    assert res.status_code == 200
    data = res.json()

    assert data["total_players"] == 3
    assert data["total_matches"] == 3
    assert data["total_flagged"] == 1
    assert data["top_player_id"] == "P003"   # highest score in season
    assert data["active_season"] is not None
    assert data["clean_rate_pct"] < 100.0
