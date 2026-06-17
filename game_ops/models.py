"""
models.py

SQLAlchemy ORM models for the Game Ops system.
Defines three tables: players, matches, and flagged_players.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Season(Base):
    """
    Represents a competitive season in the Game Ops system.

    Attributes:
        id: Auto-incremented primary key.
        name: Human-readable season name (e.g. "Season 1").
        is_active: True for the currently active season (only one at a time).
        started_at: When this season was created.
        ended_at: When this season was reset/closed (nullable).
        matches: All match records that belong to this season.
        flags: All flag records that belong to this season.
    """

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    matches: Mapped[list["Match"]] = relationship("Match", back_populates="season")
    flags: Mapped[list["FlaggedPlayer"]] = relationship("FlaggedPlayer", back_populates="season")


class Player(Base):
    """
    Represents a registered player in the system.

    Attributes:
        player_id: Unique identifier for the player (primary key).
        region: The player's current region.
        device: The device the player uses.
        matches: All match records associated with this player.
        flags: All flagged entries associated with this player.
    """

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[str] = mapped_column(String, nullable=False)
    device: Mapped[str] = mapped_column(String, nullable=False)

    matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="player"
    )
    flags: Mapped[list["FlaggedPlayer"]] = relationship(
        "FlaggedPlayer", back_populates="player"
    )


class Match(Base):
    """
    Represents a single match result submitted by a player.

    Attributes:
        id: Auto-incremented primary key.
        match_id: Identifier for the match session.
        player_id: Foreign key referencing the player.
        region: Region where the match was played.
        device: Device used during the match.
        ping: Player's ping in milliseconds.
        score: Score achieved in the match.
        kills: Number of kills in the match.
        deaths: Number of deaths in the match.
        match_duration_seconds: Duration of the match in seconds.
        submitted_at: Timestamp when the match was submitted.
        player: Relationship back to the Player record.
    """

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String, nullable=False)
    player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.player_id"), nullable=False
    )
    season_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("seasons.id"), nullable=True
    )
    region: Mapped[str] = mapped_column(String, nullable=False)
    device: Mapped[str] = mapped_column(String, nullable=False)
    ping: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    kills: Mapped[int] = mapped_column(Integer, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    match_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    player: Mapped["Player"] = relationship("Player", back_populates="matches")
    season: Mapped["Season | None"] = relationship("Season", back_populates="matches")


class FlaggedPlayer(Base):
    """
    Represents a suspicious player flagged for a specific match.

    Attributes:
        id: Auto-incremented primary key.
        player_id: Foreign key referencing the flagged player.
        match_id: The match in which suspicious activity was detected.
        reasons: Comma-separated list of flag reasons.
        flagged_at: Timestamp when the flag was created.
        player: Relationship back to the Player record.
    """

    __tablename__ = "flagged_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String, ForeignKey("players.player_id"), nullable=False
    )
    match_id: Mapped[str] = mapped_column(String, nullable=False)
    season_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("seasons.id"), nullable=True
    )
    reasons: Mapped[str] = mapped_column(String, nullable=False)
    flagged_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    player: Mapped["Player"] = relationship("Player", back_populates="flags")
    season: Mapped["Season | None"] = relationship("Season", back_populates="flags")
