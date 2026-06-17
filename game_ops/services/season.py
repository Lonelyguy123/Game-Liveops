"""
season.py

Season management service for the Game Ops system.
Handles creating seasons, resetting (closing) the active season,
fetching the active season, and computing dashboard statistics.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from models import FlaggedPlayer, Match, Player, Season


def get_active_season(db: Session) -> Season | None:
    """
    Returns the currently active season, or None if none exists.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        The active Season ORM object, or None.
    """
    return db.query(Season).filter(Season.is_active == True).first()


def get_or_create_active_season(db: Session) -> Season:
    """
    Returns the active season. If none exists, creates 'Season 1' automatically.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        The active Season ORM object.
    """
    season = get_active_season(db)
    if season is None:
        season = Season(name="Season 1", is_active=True)
        db.add(season)
        db.commit()
        db.refresh(season)
    return season


def create_season(db: Session, name: str) -> Season:
    """
    Creates a new active season and deactivates all previous seasons.

    Args:
        db: Active SQLAlchemy session.
        name: The display name for the new season.

    Returns:
        The newly created Season ORM object.
    """
    # Deactivate any existing active season
    db.query(Season).filter(Season.is_active == True).update(
        {"is_active": False, "ended_at": datetime.utcnow()}
    )
    new_season = Season(name=name, is_active=True)
    db.add(new_season)
    db.commit()
    db.refresh(new_season)
    return new_season


def reset_season(db: Session, new_season_name: str) -> dict:
    """
    Closes the currently active season and opens a new one.

    The old season's data (matches, flags) is preserved in the database
    and remains queryable via season_id. The new season starts empty.

    Args:
        db: Active SQLAlchemy session.
        new_season_name: Display name for the replacement season.

    Returns:
        A dict with 'closed_season' and 'new_season' Season objects.

    Raises:
        ValueError: If there is no active season to reset.
    """
    active = get_active_season(db)
    if active is None:
        raise ValueError("No active season to reset.")

    # Close current season
    active.is_active = False
    active.ended_at = datetime.utcnow()

    # Open new season
    new_season = Season(name=new_season_name, is_active=True)
    db.add(new_season)
    db.commit()
    db.refresh(active)
    db.refresh(new_season)

    return {"closed_season": active, "new_season": new_season}


def get_all_seasons(db: Session) -> list[Season]:
    """
    Returns all seasons ordered by id ascending.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        List of Season ORM objects.
    """
    return db.query(Season).order_by(Season.id).all()


def get_dashboard_stats(db: Session) -> dict:
    """
    Computes aggregated system-wide statistics for the dashboard.

    Stats include:
        - total_players: all players ever registered
        - total_matches: all matches ever submitted
        - total_flagged: total flagged entries
        - total_seasons: number of seasons
        - active_season: the current active season (or None)
        - top_player_id: player with the highest total score in the active season
        - top_player_score: that player's total score
        - clean_rate_pct: % of players who have never been flagged

    Args:
        db: Active SQLAlchemy session.

    Returns:
        A dict matching the DashboardStats schema fields.
    """
    active = get_active_season(db)

    total_players = db.query(Player).count()
    total_seasons = db.query(Season).count()

    # Season-scoped match and flag counts
    if active:
        total_matches = db.query(Match).filter(Match.season_id == active.id).count()
        total_flagged = db.query(FlaggedPlayer).filter(
            FlaggedPlayer.season_id == active.id
        ).count()
        season_matches = db.query(Match).filter(Match.season_id == active.id).all()
    else:
        # No season yet — fall back to all-time counts
        total_matches = db.query(Match).count()
        total_flagged = db.query(FlaggedPlayer).count()
        season_matches = db.query(Match).all()

    # Compute top player by total score in active season
    top_player_id = None
    top_player_score = 0

    if season_matches:
        score_map: dict[str, int] = {}
        for m in season_matches:
            score_map[m.player_id] = score_map.get(m.player_id, 0) + m.score
        if score_map:
            top_player_id = max(score_map, key=lambda p: score_map[p])
            top_player_score = score_map[top_player_id]

    # Clean rate — players with zero flags (all-time, since flags are per-player)
    flagged_player_ids = {
        row.player_id for row in db.query(FlaggedPlayer.player_id).distinct()
    }
    clean_players = total_players - len(flagged_player_ids)
    clean_rate_pct = round((clean_players / total_players * 100), 1) if total_players > 0 else 100.0

    return {
        "total_players": total_players,
        "total_matches": total_matches,
        "total_flagged": total_flagged,
        "total_seasons": total_seasons,
        "active_season": active,
        "top_player_id": top_player_id,
        "top_player_score": top_player_score,
        "clean_rate_pct": clean_rate_pct,
    }
