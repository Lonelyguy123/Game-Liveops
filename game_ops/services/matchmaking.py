"""
matchmaking.py

Database-backed matchmaking service for the Game Ops system.
Groups clean (non-flagged) players by region and skill tier,
then splits groups by ping proximity.
"""

from collections import Counter

from sqlalchemy.orm import Session

from constants import PING_DIFFERENCE_THRESHOLD_MS, SKILL_TIER_BOUNDARIES
from models import FlaggedPlayer, Match, Player


def get_skill_tier(avg_score: float) -> str:
    """
    Determines a player's skill tier based on their average score.

    Tiers:
        LOW  — avg_score < SKILL_TIER_BOUNDARIES["LOW"]
        MID  — avg_score < SKILL_TIER_BOUNDARIES["MID"]
        HIGH — avg_score >= SKILL_TIER_BOUNDARIES["MID"]

    Args:
        avg_score: The player's average score across all matches.

    Returns:
        A string: "LOW", "MID", or "HIGH".
    """
    if avg_score < SKILL_TIER_BOUNDARIES["LOW"]:
        return "LOW"
    if avg_score < SKILL_TIER_BOUNDARIES["MID"]:
        return "MID"
    return "HIGH"


def suggest_matchmaking(db: Session) -> list[dict]:
    """
    Suggests matchmaking groups for all clean (non-flagged) players.

    Steps:
        1. For each player, compute avg_score, avg_ping, primary_region,
           and skill_tier from their match history.
        2. Exclude players who appear in flagged_players.
        3. Group players by (primary_region, skill_tier).
        4. Within each group, sort by avg_ping ascending, then apply a
           sliding-window split: start a new subgroup whenever the next
           player's avg_ping differs from the first player in the current
           subgroup by more than PING_DIFFERENCE_THRESHOLD_MS.
        5. Assign sequential group_id (starting from 1) across all subgroups.
        6. Compute avg_ping for each final subgroup.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        A list of dicts matching the MatchmakingGroup schema fields.
    """
    players = db.query(Player).all()

    # Build set of flagged player_ids
    flagged_ids: set[str] = {
        row.player_id for row in db.query(FlaggedPlayer).all()
    }

    # Build player stats, skipping flagged players and those with no matches
    player_stats: list[dict] = []

    for player in players:
        if player.player_id in flagged_ids:
            continue

        matches: list[Match] = player.matches
        if not matches:
            continue

        avg_score = sum(m.score for m in matches) / len(matches)
        avg_ping = sum(m.ping for m in matches) / len(matches)

        region_counts: Counter = Counter(m.region for m in matches)
        primary_region: str = region_counts.most_common(1)[0][0]

        player_stats.append(
            {
                "player_id": player.player_id,
                "avg_score": avg_score,
                "avg_ping": avg_ping,
                "primary_region": primary_region,
                "skill_tier": get_skill_tier(avg_score),
            }
        )

    # Group players by (primary_region, skill_tier)
    bucket: dict[tuple[str, str], list[dict]] = {}
    for ps in player_stats:
        key = (ps["primary_region"], ps["skill_tier"])
        bucket.setdefault(key, []).append(ps)

    groups: list[dict] = []
    group_id = 1

    for (region, skill_tier), members in bucket.items():
        # Sort by avg_ping ascending within the bucket
        members.sort(key=lambda p: p["avg_ping"])

        # Sliding-window ping split
        subgroup: list[dict] = []
        subgroup_anchor_ping: float = 0.0

        for member in members:
            if not subgroup:
                subgroup.append(member)
                subgroup_anchor_ping = member["avg_ping"]
            elif member["avg_ping"] - subgroup_anchor_ping <= PING_DIFFERENCE_THRESHOLD_MS:
                subgroup.append(member)
            else:
                # Flush current subgroup and start a new one
                subgroup_avg_ping = sum(p["avg_ping"] for p in subgroup) / len(subgroup)
                groups.append(
                    {
                        "group_id": group_id,
                        "region": region,
                        "skill_tier": skill_tier,
                        "player_ids": [p["player_id"] for p in subgroup],
                        "avg_ping": round(subgroup_avg_ping, 2),
                    }
                )
                group_id += 1
                subgroup = [member]
                subgroup_anchor_ping = member["avg_ping"]

        # Flush the last subgroup
        if subgroup:
            subgroup_avg_ping = sum(p["avg_ping"] for p in subgroup) / len(subgroup)
            groups.append(
                {
                    "group_id": group_id,
                    "region": region,
                    "skill_tier": skill_tier,
                    "player_ids": [p["player_id"] for p in subgroup],
                    "avg_ping": round(subgroup_avg_ping, 2),
                }
            )
            group_id += 1

    return groups
