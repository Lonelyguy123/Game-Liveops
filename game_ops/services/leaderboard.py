"""
leaderboard.py

Database-backed leaderboard service for the Game Ops system.
Aggregates match data per player and returns a ranked leaderboard.
Supports optional region and season filters.
"""

from collections import Counter

from sqlalchemy.orm import Session

from models import FlaggedPlayer, Match, Player


def get_leaderboard(
    db: Session,
    region: str | None = None,
    season_id: int | None = None,
) -> list[dict]:
    """
    Builds a ranked leaderboard by aggregating each player's match history.

    Aggregation per player:
        - total_score:    sum of all match scores
        - total_kills:    sum of all kills
        - total_deaths:   sum of all deaths
        - matches_played: count of match rows
        - primary_region: most common region across their matches

    Filtering:
        - If `region` is provided, only players whose primary_region matches
          (case-insensitive) are included.
        - If `season_id` is provided, only matches belonging to that season
          are aggregated (season-scoped leaderboard).

    Flagging:
        Any player with at least one row in flagged_players is marked
        is_flagged=True. Flagged players are NOT excluded from the board.

    Sorting:
        1. total_score  DESC
        2. total_deaths ASC  (fewer deaths wins tiebreak)
        3. total_kills  DESC

    Args:
        db:        Active SQLAlchemy session.
        region:    Optional region filter string (case-insensitive).
        season_id: Optional season ID to scope leaderboard to one season.

    Returns:
        A list of dicts matching the LeaderboardEntry schema fields,
        with sequential rank starting from 1.
    """
    players = db.query(Player).all()

    # Build a set of all-time flagged player_ids for O(1) lookup
    flagged_ids: set[str] = {
        row.player_id for row in db.query(FlaggedPlayer).all()
    }

    entries: list[dict] = []

    for player in players:
        # Scope matches to the requested season, or use all matches
        if season_id is not None:
            matches: list[Match] = [
                m for m in player.matches if m.season_id == season_id
            ]
        else:
            matches = list(player.matches)

        if not matches:
            continue

        total_score   = sum(m.score  for m in matches)
        total_kills   = sum(m.kills  for m in matches)
        total_deaths  = sum(m.deaths for m in matches)
        matches_played = len(matches)

        region_counts: Counter = Counter(m.region for m in matches)
        primary_region: str = region_counts.most_common(1)[0][0]

        # Apply optional region filter (case-insensitive)
        if region is not None and primary_region.lower() != region.lower():
            continue

        entries.append({
            "player_id":     player.player_id,
            "region":        primary_region,
            "total_score":   total_score,
            "total_kills":   total_kills,
            "total_deaths":  total_deaths,
            "matches_played": matches_played,
            "is_flagged":    player.player_id in flagged_ids,
        })

    # Sort: total_score DESC → total_deaths ASC → total_kills DESC
    entries.sort(
        key=lambda e: (-e["total_score"], e["total_deaths"], -e["total_kills"])
    )

    # Assign sequential rank starting at 1
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank

    return entries
