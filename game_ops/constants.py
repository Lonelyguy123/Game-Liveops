"""
constants.py

All detection thresholds and configuration constants for the Game Ops system.
Import from here — never hardcode these values elsewhere in the codebase.
"""

# Maximum kills per minute before a player is flagged for suspicious kill rate
MAX_KILLS_PER_MINUTE: int = 15

# Maximum score per second before a player is flagged for suspicious scoring
MAX_SCORE_PER_SECOND: int = 100

# Minimum acceptable match duration in seconds
MIN_MATCH_DURATION_SECONDS: int = 120

# If a player has zero deaths, this is the maximum kills allowed before flagging
MAX_KD_RATIO_WITH_ZERO_DEATHS: int = 20

# Maximum multiplier vs average score before flagging (reserved for future use)
MAX_SCORE_MULTIPLIER_VS_AVG: float = 5.0

# Maximum ping difference (ms) allowed within a matchmaking subgroup
PING_DIFFERENCE_THRESHOLD_MS: int = 80

# Skill tier score boundaries:
#   avg_score < 2000  → LOW
#   avg_score < 4000  → MID
#   avg_score >= 4000 → HIGH
SKILL_TIER_BOUNDARIES: dict[str, int] = {
    "LOW": 2000,
    "MID": 4000,
}
