"""
schemas.py

Pydantic v2 request/response models for the Game Ops API.
All ORM-backed models use model_config with from_attributes=True.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class MatchSubmission(BaseModel):
    """
    Request body for POST /submit-score.

    All fields are required. Represents a single match result submitted
    by a player.
    """

    player_id: str
    match_id: str
    region: str
    device: str
    ping: int
    score: int
    kills: int
    deaths: int
    match_duration_seconds: int


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MatchResponse(BaseModel):
    """
    Response for POST /submit-score.

    Includes whether the player was flagged and the reasons if any.
    """

    message: str
    player_id: str
    match_id: str
    flagged: bool
    flag_reasons: list[str]


class LeaderboardEntry(BaseModel):
    """
    A single entry in the leaderboard response.

    Includes aggregated stats for one player and their current rank.
    """

    model_config = ConfigDict(from_attributes=True)

    rank: int
    player_id: str
    region: str
    total_score: int
    total_kills: int
    total_deaths: int
    matches_played: int
    is_flagged: bool


class LeaderboardResponse(BaseModel):
    """
    Full leaderboard response containing all ranked player entries.
    """

    total_players: int
    entries: list[LeaderboardEntry]


class FlaggedPlayerEntry(BaseModel):
    """
    A single flagged player entry in the flagged players response.
    """

    player_id: str
    match_id: str
    reasons: list[str]
    flagged_at: datetime


class FlaggedPlayersResponse(BaseModel):
    """
    Response for GET /flagged-players.

    Contains all players who have been flagged for suspicious activity.
    """

    total_flagged: int
    players: list[FlaggedPlayerEntry]


class MatchmakingGroup(BaseModel):
    """
    A single suggested matchmaking group.

    Players in the group share the same region and skill tier,
    and have similar ping values.
    """

    group_id: int
    region: str
    skill_tier: str
    player_ids: list[str]
    avg_ping: float


class MatchmakingResponse(BaseModel):
    """
    Response for GET /matchmaking.

    Contains all suggested matchmaking groups.
    """

    total_groups: int
    groups: list[MatchmakingGroup]


# ---------------------------------------------------------------------------
# Season schemas
# ---------------------------------------------------------------------------


class SeasonCreate(BaseModel):
    """Request body for POST /seasons — creates a new season."""
    name: str


class SeasonInfo(BaseModel):
    """Details of a single season."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    started_at: datetime
    ended_at: datetime | None


class SeasonResetResponse(BaseModel):
    """Response after resetting (closing) the active season."""
    message: str
    closed_season: SeasonInfo
    new_season: SeasonInfo


class DashboardStats(BaseModel):
    """Aggregated system-wide stats for the dashboard."""
    total_players: int
    total_matches: int
    total_flagged: int
    total_seasons: int
    active_season: SeasonInfo | None
    top_player_id: str | None
    top_player_score: int
    clean_rate_pct: float  # percentage of players with no flags


# ---------------------------------------------------------------------------
# CSV ingestion schemas
# ---------------------------------------------------------------------------


class CsvRowResult(BaseModel):
    """Result for a single row processed from a CSV upload."""
    player_id: str
    match_id: str
    region: str
    device: str
    score: int
    kills: int
    deaths: int
    ping: int
    flagged: bool
    flag_reasons: list[str]


class CsvUploadResponse(BaseModel):
    """Response for POST /upload-csv."""
    total_rows: int
    flagged_count: int
    clean_count: int
    results: list[CsvRowResult]
