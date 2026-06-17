"""
test_csv_ingest.py

Unit and integration tests for the CSV ingestion service.
Tests cover: valid upload, detection on CSV rows, missing columns,
empty file, and multi-player batch commits.
"""

import io

from services.csv_ingest import parse_csv


# ---------------------------------------------------------------------------
# Unit tests for parse_csv (no DB needed)
# ---------------------------------------------------------------------------


def _make_csv(*rows: str) -> bytes:
    """Helper — builds CSV bytes from a header + data rows."""
    header = "player_id,match_id,region,device,ping,score,kills,deaths,match_duration_seconds"
    lines  = "\n".join([header] + list(rows))
    return lines.encode("utf-8")


def test_parse_csv_valid_row():
    """A well-formed CSV row should parse correctly with integer casting."""
    data = _make_csv("P001,M001,India,Android,55,3200,18,4,420")
    rows = parse_csv(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["player_id"] == "P001"
    assert row["score"]  == 3200
    assert row["kills"]  == 18
    assert row["ping"]   == 55
    assert isinstance(row["deaths"], int)


def test_parse_csv_multiple_rows():
    """All data rows should be parsed and returned."""
    data = _make_csv(
        "P001,M001,India,Android,55,3200,18,4,420",
        "P002,M001,India,iOS,62,2800,14,6,390",
        "P003,M001,Europe,PC,28,4500,22,3,480",
    )
    rows = parse_csv(data)
    assert len(rows) == 3
    assert rows[2]["player_id"] == "P003"


def test_parse_csv_missing_column_raises():
    """A CSV missing a required column should raise ValueError."""
    bad_csv = b"player_id,match_id,region,device,ping,score,kills,deaths\nP001,M001,India,Android,55,3200,18,4"
    try:
        parse_csv(bad_csv)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "match_duration_seconds" in str(e)


def test_parse_csv_empty_file_raises():
    """An empty file (no header, no rows) should raise ValueError."""
    try:
        parse_csv(b"")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower() or "header" in str(e).lower()


def test_parse_csv_header_only_raises():
    """A header row with no data rows should raise ValueError."""
    header_only = b"player_id,match_id,region,device,ping,score,kills,deaths,match_duration_seconds\n"
    try:
        parse_csv(header_only)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "no data" in str(e).lower() or "rows" in str(e).lower()


def test_parse_csv_non_integer_field_raises():
    """A non-integer value in an integer field should raise ValueError."""
    data = _make_csv("P001,M001,India,Android,FAST,3200,18,4,420")
    try:
        parse_csv(data)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "ping" in str(e)


def test_parse_csv_handles_bom():
    """CSV files with a UTF-8 BOM marker should parse correctly."""
    bom_csv = b"\xef\xbb\xbfplayer_id,match_id,region,device,ping,score,kills,deaths,match_duration_seconds\nP001,M001,India,Android,55,3200,18,4,420"
    rows = parse_csv(bom_csv)
    assert len(rows) == 1
    assert rows[0]["player_id"] == "P001"


# ---------------------------------------------------------------------------
# Integration tests for POST /upload-csv (uses DB via client fixture)
# ---------------------------------------------------------------------------


def _csv_payload(*rows: str) -> bytes:
    """Build CSV bytes for upload."""
    return _make_csv(*rows)


def test_upload_csv_clean_batch(client):
    """
    Uploading a CSV with all clean players should return 0 flagged rows
    and insert all players into the database (visible on leaderboard).
    """
    csv_bytes = _csv_payload(
        "P001,M001,India,Android,55,3200,18,4,420",
        "P002,M001,India,iOS,62,2800,14,6,390",
    )
    res = client.post(
        "/upload-csv",
        files={"file": ("match.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"]    == 2
    assert data["flagged_count"] == 0
    assert data["clean_count"]   == 2

    # Both players should appear on the leaderboard
    lb = client.get("/leaderboard").json()
    player_ids = [e["player_id"] for e in lb["entries"]]
    assert "P001" in player_ids
    assert "P002" in player_ids


def test_upload_csv_detects_cheaters(client):
    """
    Suspicious rows in a CSV upload should be flagged and appear
    in /flagged-players, while clean rows remain clean.
    """
    csv_bytes = _csv_payload(
        "P001,M002,India,Android,55,3200,18,4,420",           # clean
        "P_CHEAT,M002,Europe,PC,10,99000,250,0,60",           # suspicious
    )
    res = client.post(
        "/upload-csv",
        files={"file": ("match.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["flagged_count"] == 1
    assert data["clean_count"]   == 1

    # Verify in flagged-players endpoint
    flagged = client.get("/flagged-players").json()
    pids = [p["player_id"] for p in flagged["players"]]
    assert "P_CHEAT" in pids
    assert "P001"    not in pids


def test_upload_csv_wrong_extension_rejected(client):
    """Uploading a non-CSV file should return 400."""
    res = client.post(
        "/upload-csv",
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert res.status_code == 400


def test_upload_csv_missing_column_returns_422(client):
    """A CSV missing a required column should return 422 with a clear message."""
    bad_csv = b"player_id,match_id,region,device,ping,score,kills,deaths\nP001,M001,India,Android,55,3200,18,4"
    res = client.post(
        "/upload-csv",
        files={"file": ("match.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    assert res.status_code == 422
    assert "match_duration_seconds" in res.json()["detail"]


def test_upload_csv_all_rows_committed_atomically(client):
    """
    All rows in a CSV should be committed together. After upload,
    the leaderboard count should match the number of unique players.
    """
    csv_bytes = _csv_payload(
        "PA,MATCH_X,SEA,PC,80,2500,12,5,300",
        "PB,MATCH_X,SEA,Android,90,2800,14,4,300",
        "PC,MATCH_X,SEA,iOS,85,3100,16,3,300",
    )
    res = client.post(
        "/upload-csv",
        files={"file": ("match.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["total_rows"] == 3

    lb = client.get("/leaderboard").json()
    assert lb["total_players"] == 3
