"""
csv_ingest.py

CSV batch ingestion service for the Game Ops system.

Parses a match CSV file where each row represents one player's result
from a completed match. All rows sharing the same match_id are treated
as belonging to the same match (e.g. 10 players from a 5v5 game).

Expected CSV columns (order-independent, header row required):
    player_id, match_id, region, device, ping, score,
    kills, deaths, match_duration_seconds

Detection runs on every row. Results are bulk-committed in a single
transaction so either all rows land or none do.
"""

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from models import FlaggedPlayer, Match, Player
from services import detection
from services.season import get_or_create_active_season

# Required columns — exactly matching the Match schema
REQUIRED_COLUMNS = {
    "player_id", "match_id", "region", "device",
    "ping", "score", "kills", "deaths", "match_duration_seconds",
}

INTEGER_FIELDS = {"ping", "score", "kills", "deaths", "match_duration_seconds"}


def parse_csv(file_bytes: bytes) -> list[dict]:
    """
    Parses raw CSV bytes into a list of row dicts with correct types.

    Args:
        file_bytes: Raw bytes of the uploaded CSV file.

    Returns:
        List of dicts, one per data row, with integer fields cast.

    Raises:
        ValueError: If required columns are missing or a row has invalid data.
    """
    text = file_bytes.decode("utf-8-sig")  # handle optional BOM
    reader = csv.DictReader(io.StringIO(text))

    # Normalise header names (strip whitespace, lowercase)
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row.")

    normalised = [f.strip().lower() for f in reader.fieldnames]
    missing = REQUIRED_COLUMNS - set(normalised)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    rows: list[dict] = []
    for line_num, raw_row in enumerate(reader, start=2):
        # Re-key with normalised names
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}

        # Cast integer fields
        for field in INTEGER_FIELDS:
            raw = row.get(field, "")
            if not raw:
                raise ValueError(f"Row {line_num}: '{field}' is empty.")
            try:
                row[field] = int(raw)
            except ValueError:
                raise ValueError(
                    f"Row {line_num}: '{field}' must be an integer, got '{raw}'."
                )

        rows.append(row)

    if not rows:
        raise ValueError("CSV file has a header but no data rows.")

    return rows


def ingest_csv(db: Session, file_bytes: bytes) -> list[dict]:
    """
    Parses a CSV file and bulk-inserts all match rows into the database.

    For each row:
        1. Upserts the player record.
        2. Inserts the match row stamped with the active season.
        3. Runs fraud detection.
        4. Inserts a FlaggedPlayer row if suspicious.

    All inserts are committed together in a single transaction.

    Args:
        db:         Active SQLAlchemy session.
        file_bytes: Raw bytes of the uploaded CSV file.

    Returns:
        A list of result dicts, one per row, each containing:
            player_id, match_id, flagged (bool), flag_reasons (list[str])

    Raises:
        ValueError: If the CSV is malformed or missing required columns.
    """
    rows = parse_csv(file_bytes)
    active_season = get_or_create_active_season(db)

    results: list[dict] = []

    for row in rows:
        player_id = row["player_id"]
        match_id  = row["match_id"]

        # Upsert player
        player = db.query(Player).filter(Player.player_id == player_id).first()
        if player:
            player.region = row["region"]
            player.device = row["device"]
        else:
            player = Player(
                player_id=player_id,
                region=row["region"],
                device=row["device"],
            )
            db.add(player)
            db.flush()

        # Insert match
        match_row = Match(
            match_id=match_id,
            player_id=player_id,
            season_id=active_season.id,
            region=row["region"],
            device=row["device"],
            ping=row["ping"],
            score=row["score"],
            kills=row["kills"],
            deaths=row["deaths"],
            match_duration_seconds=row["match_duration_seconds"],
        )
        db.add(match_row)

        # Run detection
        reasons = detection.check_suspicious(row)

        if reasons:
            flag_row = FlaggedPlayer(
                player_id=player_id,
                match_id=match_id,
                season_id=active_season.id,
                reasons=",".join(reasons),
            )
            db.add(flag_row)

        results.append({
            "player_id":   player_id,
            "match_id":    match_id,
            "region":      row["region"],
            "device":      row["device"],
            "score":       row["score"],
            "kills":       row["kills"],
            "deaths":      row["deaths"],
            "ping":        row["ping"],
            "flagged":     bool(reasons),
            "flag_reasons": reasons,
        })

    db.commit()
    return results
