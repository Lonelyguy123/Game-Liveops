"""
detection.py

Pure detection functions for identifying suspicious player behaviour.
No database access — all functions operate on plain Python values.
"""

from constants import (
    MAX_KD_RATIO_WITH_ZERO_DEATHS,
    MAX_KILLS_PER_MINUTE,
    MAX_SCORE_PER_SECOND,
    MIN_MATCH_DURATION_SECONDS,
)


# ---------------------------------------------------------------------------
# Private rule helpers
# ---------------------------------------------------------------------------


def _check_kill_rate(kills: int, match_duration_seconds: int) -> str | None:
    """
    Checks whether the player's kill rate exceeds the allowed maximum.

    Args:
        kills: Number of kills recorded in the match.
        match_duration_seconds: Duration of the match in seconds.

    Returns:
        A reason string if the rule is triggered, otherwise None.
    """
    kills_per_minute = kills / (match_duration_seconds / 60)
    if kills_per_minute > MAX_KILLS_PER_MINUTE:
        return (
            f"Kill rate {kills_per_minute:.1f}/min exceeds max "
            f"{MAX_KILLS_PER_MINUTE}/min"
        )
    return None


def _check_score_rate(score: int, match_duration_seconds: int) -> str | None:
    """
    Checks whether the player's score rate exceeds the allowed maximum.

    Args:
        score: Total score achieved in the match.
        match_duration_seconds: Duration of the match in seconds.

    Returns:
        A reason string if the rule is triggered, otherwise None.
    """
    score_per_second = score / match_duration_seconds
    if score_per_second > MAX_SCORE_PER_SECOND:
        return (
            f"Score rate {score_per_second:.1f}/sec exceeds max "
            f"{MAX_SCORE_PER_SECOND}/sec"
        )
    return None


def _check_match_duration(match_duration_seconds: int) -> str | None:
    """
    Checks whether the match duration is suspiciously short.

    Args:
        match_duration_seconds: Duration of the match in seconds.

    Returns:
        A reason string if the rule is triggered, otherwise None.
    """
    if match_duration_seconds < MIN_MATCH_DURATION_SECONDS:
        return (
            f"Match duration {match_duration_seconds}s is below minimum "
            f"{MIN_MATCH_DURATION_SECONDS}s"
        )
    return None


def _check_kd_ratio(kills: int, deaths: int) -> str | None:
    """
    Checks whether the player has a suspicious kill/death ratio
    (many kills with zero deaths).

    Args:
        kills: Number of kills in the match.
        deaths: Number of deaths in the match.

    Returns:
        A reason string if the rule is triggered, otherwise None.
    """
    if deaths == 0 and kills >= MAX_KD_RATIO_WITH_ZERO_DEATHS:
        return f"Suspicious K/D: {kills} kills with 0 deaths"
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def check_suspicious(match_data: dict) -> list[str]:
    """
    Runs all detection rules against a single match submission.

    Args:
        match_data: A dict containing at minimum the keys:
            kills, deaths, score, match_duration_seconds.

    Returns:
        A list of reason strings for each triggered rule.
        An empty list means the player is clean.
    """
    kills = match_data["kills"]
    deaths = match_data["deaths"]
    score = match_data["score"]
    duration = match_data["match_duration_seconds"]

    checks = [
        _check_kill_rate(kills, duration),
        _check_score_rate(score, duration),
        _check_match_duration(duration),
        _check_kd_ratio(kills, deaths),
    ]

    return [reason for reason in checks if reason is not None]
