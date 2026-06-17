"""
test_leaderboard.py

Integration tests for the leaderboard endpoint.
Uses the client fixture which sets up a fresh test database per test.
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


def submit(client, overrides: dict | None = None):
    """
    Helper that posts a match submission using the default payload,
    merged with any provided overrides.

    Args:
        client: TestClient instance.
        overrides: Dict of fields to override in the default payload.

    Returns:
        Response object from POST /submit-score.
    """
    payload = {**DEFAULT_PAYLOAD, **(overrides or {})}
    return client.post("/submit-score", json=payload)


def test_leaderboard_ranking_by_score(client):
    """
    Three players with different scores should be ranked in descending
    score order, with ranks [1, 2, 3].
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "score": 3200})
    submit(client, {"player_id": "P002", "match_id": "M002", "score": 2800})
    submit(client, {"player_id": "P003", "match_id": "M003", "score": 3500})

    response = client.get("/leaderboard")
    assert response.status_code == 200
    data = response.json()

    entries = data["entries"]
    assert len(entries) == 3

    # Top entry should have the highest score (3500)
    assert entries[0]["total_score"] == 3500

    ranks = [e["rank"] for e in entries]
    assert ranks == [1, 2, 3]


def test_leaderboard_tiebreak_by_deaths(client):
    """
    Two players with the same total score should be ranked by deaths ascending
    — the player with fewer deaths gets the higher rank.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "score": 3200, "deaths": 4})
    submit(client, {"player_id": "P002", "match_id": "M002", "score": 3200, "deaths": 6})

    response = client.get("/leaderboard")
    assert response.status_code == 200
    data = response.json()

    entries = data["entries"]
    rank1_entry = next(e for e in entries if e["rank"] == 1)
    assert rank1_entry["player_id"] == "P001"


def test_leaderboard_flagged_player_visible(client):
    """
    A player who was flagged for suspicious behaviour should still appear
    in the leaderboard with is_flagged == True.
    """
    submit(
        client,
        {
            "player_id": "P003",
            "match_id": "M003",
            "kills": 250,
            "score": 99000,
            "match_duration_seconds": 60,
            "deaths": 0,
        },
    )

    response = client.get("/leaderboard")
    assert response.status_code == 200
    data = response.json()

    entries = data["entries"]
    p003 = next((e for e in entries if e["player_id"] == "P003"), None)
    assert p003 is not None, "P003 should appear in leaderboard"
    assert p003["is_flagged"] is True


def test_leaderboard_region_filter(client):
    """
    When filtering by region, only players whose primary region matches
    the filter should be returned.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "region": "India"})
    submit(client, {"player_id": "P002", "match_id": "M002", "region": "Europe"})

    response = client.get("/leaderboard?region=India")
    assert response.status_code == 200
    data = response.json()

    entries = data["entries"]
    assert len(entries) == 1
    assert entries[0]["player_id"] == "P001"
