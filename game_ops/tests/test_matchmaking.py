"""
test_matchmaking.py

Integration tests for the matchmaking endpoint.
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


def test_different_regions_not_grouped(client):
    """
    Players from different regions must never appear in the same
    matchmaking group.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "region": "India", "ping": 50, "score": 3200})
    submit(client, {"player_id": "P002", "match_id": "M002", "region": "Europe", "ping": 55, "score": 3100})

    response = client.get("/matchmaking")
    assert response.status_code == 200
    data = response.json()

    for group in data["groups"]:
        player_ids = group["player_ids"]
        assert not (
            "P001" in player_ids and "P002" in player_ids
        ), "P001 (India) and P002 (Europe) must not share a group"


def test_same_region_same_tier_grouped(client):
    """
    Two players in the same region with similar scores (both MID tier)
    and close ping values should be placed in the same matchmaking group.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "region": "India", "ping": 50, "score": 3200})
    submit(client, {"player_id": "P002", "match_id": "M002", "region": "India", "ping": 55, "score": 3100})

    response = client.get("/matchmaking")
    assert response.status_code == 200
    data = response.json()

    found_together = any(
        "P001" in group["player_ids"] and "P002" in group["player_ids"]
        for group in data["groups"]
    )
    assert found_together, "P001 and P002 should be in the same matchmaking group"


def test_flagged_player_excluded_from_matchmaking(client):
    """
    A player flagged for suspicious activity must not appear in
    any matchmaking group.
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

    response = client.get("/matchmaking")
    assert response.status_code == 200
    data = response.json()

    all_player_ids = [
        pid
        for group in data["groups"]
        for pid in group["player_ids"]
    ]
    assert "P003" not in all_player_ids, "Flagged player P003 must not appear in matchmaking"


def test_ping_split_within_region(client):
    """
    Two players in the same region and tier but with a ping difference
    greater than PING_DIFFERENCE_THRESHOLD_MS (80ms) should be placed
    in separate groups.
    """
    submit(client, {"player_id": "P001", "match_id": "M001", "region": "India", "ping": 30, "score": 3000})
    submit(client, {"player_id": "P002", "match_id": "M002", "region": "India", "ping": 150, "score": 3100})

    response = client.get("/matchmaking")
    assert response.status_code == 200
    data = response.json()

    # Find groups containing each player
    p001_group = next(
        (g for g in data["groups"] if "P001" in g["player_ids"]), None
    )
    p002_group = next(
        (g for g in data["groups"] if "P002" in g["player_ids"]), None
    )

    assert p001_group is not None, "P001 should be in a group"
    assert p002_group is not None, "P002 should be in a group"
    assert p001_group["group_id"] != p002_group["group_id"], (
        "P001 (ping=30) and P002 (ping=150) should be in different groups"
    )
