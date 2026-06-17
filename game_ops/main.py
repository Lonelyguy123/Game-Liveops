"""
main.py

FastAPI application entry point for the Game Ops system.
Defines all API routes and wires them to the service layer.
No business logic lives here — route handlers delegate entirely
to service functions.
"""

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import FlaggedPlayer, Match, Player
from schemas import (
    CsvRowResult,
    CsvUploadResponse,
    DashboardStats,
    FlaggedPlayerEntry,
    FlaggedPlayersResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    MatchmakingResponse,
    MatchResponse,
    MatchSubmission,
    SeasonCreate,
    SeasonInfo,
    SeasonResetResponse,
)
from services import detection, leaderboard, matchmaking, season as season_svc
from services.csv_ingest import ingest_csv

# Create all tables on startup if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Game Ops API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# POST /submit-score
# ---------------------------------------------------------------------------


@app.post("/submit-score", response_model=MatchResponse)
def submit_score(payload: MatchSubmission, db: Session = Depends(get_db)):
    """
    Accepts a player match result, persists it, and runs fraud detection.

    Automatically stamps the match with the active season's ID.
    If no season exists, one is created automatically.

    Args:
        payload: Validated MatchSubmission request body.
        db: Injected database session.

    Returns:
        MatchResponse with flagged status and reasons.
    """
    # Resolve active season (auto-create Season 1 if needed)
    active_season = season_svc.get_or_create_active_season(db)

    # Upsert player
    existing_player = db.query(Player).filter(
        Player.player_id == payload.player_id
    ).first()

    if existing_player:
        existing_player.region = payload.region
        existing_player.device = payload.device
    else:
        new_player = Player(
            player_id=payload.player_id,
            region=payload.region,
            device=payload.device,
        )
        db.add(new_player)
        db.flush()

    # Insert match record with season_id
    match_row = Match(
        match_id=payload.match_id,
        player_id=payload.player_id,
        season_id=active_season.id,
        region=payload.region,
        device=payload.device,
        ping=payload.ping,
        score=payload.score,
        kills=payload.kills,
        deaths=payload.deaths,
        match_duration_seconds=payload.match_duration_seconds,
    )
    db.add(match_row)

    # Run detection
    reasons = detection.check_suspicious(payload.model_dump())

    # Flag if suspicious — also scoped to the active season
    if reasons:
        flag_row = FlaggedPlayer(
            player_id=payload.player_id,
            match_id=payload.match_id,
            season_id=active_season.id,
            reasons=",".join(reasons),
        )
        db.add(flag_row)

    db.commit()

    return MatchResponse(
        message="Score submitted successfully",
        player_id=payload.player_id,
        match_id=payload.match_id,
        flagged=bool(reasons),
        flag_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# GET /leaderboard
# ---------------------------------------------------------------------------


@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    region: str | None = None,
    season_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Returns a ranked leaderboard of all players.

    Query params:
        region:    Optional case-insensitive region filter.
        season_id: Optional season ID to scope results. Defaults to active season.

    Args:
        region: Optional region string.
        season_id: Optional season ID. If omitted, the active season is used.
        db: Injected database session.

    Returns:
        LeaderboardResponse with total_players and ranked entries.
    """
    # Default to active season if no season_id supplied
    if season_id is None:
        active = season_svc.get_active_season(db)
        if active:
            season_id = active.id

    entries = leaderboard.get_leaderboard(db, region=region, season_id=season_id)
    return LeaderboardResponse(
        total_players=len(entries),
        entries=[LeaderboardEntry(**e) for e in entries],
    )


# ---------------------------------------------------------------------------
# GET /flagged-players
# ---------------------------------------------------------------------------


@app.get("/flagged-players", response_model=FlaggedPlayersResponse)
def get_flagged_players(
    season_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Returns all flagged players, optionally scoped to a season.

    Query params:
        season_id: Optional season ID filter. Defaults to active season.

    Args:
        season_id: Optional season ID.
        db: Injected database session.

    Returns:
        FlaggedPlayersResponse with total_flagged count and player list.
    """
    if season_id is None:
        active = season_svc.get_active_season(db)
        if active:
            season_id = active.id

    query = db.query(FlaggedPlayer)
    if season_id is not None:
        query = query.filter(FlaggedPlayer.season_id == season_id)
    rows = query.all()

    players = [
        FlaggedPlayerEntry(
            player_id=row.player_id,
            match_id=row.match_id,
            reasons=row.reasons.split(","),
            flagged_at=row.flagged_at,
        )
        for row in rows
    ]

    return FlaggedPlayersResponse(
        total_flagged=len(players),
        players=players,
    )


# ---------------------------------------------------------------------------
# GET /matchmaking
# ---------------------------------------------------------------------------


@app.get("/matchmaking", response_model=MatchmakingResponse)
def get_matchmaking(db: Session = Depends(get_db)):
    """
    Returns suggested matchmaking groups for all eligible (non-flagged) players.

    Args:
        db: Injected database session.

    Returns:
        MatchmakingResponse with total_groups and groups list.
    """
    groups = matchmaking.suggest_matchmaking(db)
    return MatchmakingResponse(
        total_groups=len(groups),
        groups=groups,
    )


# ---------------------------------------------------------------------------
# POST /upload-csv
# ---------------------------------------------------------------------------


@app.post("/upload-csv", response_model=CsvUploadResponse)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts a CSV file containing multiple players' match results from a
    single completed match (e.g. 10 players in a 5v5 game).

    Expected columns (header row required, order-independent):
        player_id, match_id, region, device, ping, score,
        kills, deaths, match_duration_seconds

    Each row is processed individually:
        - Player is upserted.
        - Match row is inserted stamped with the active season.
        - Fraud detection runs on every row.
        - Flagged rows get a FlaggedPlayer entry.

    All rows are committed together in a single transaction.

    Args:
        file: Uploaded CSV file (multipart/form-data).
        db:   Injected database session.

    Returns:
        CsvUploadResponse with per-row results and summary counts.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    file_bytes = await file.read()

    try:
        results = ingest_csv(db, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    flagged_count = sum(1 for r in results if r["flagged"])

    return CsvUploadResponse(
        total_rows=len(results),
        flagged_count=flagged_count,
        clean_count=len(results) - flagged_count,
        results=[CsvRowResult(**r) for r in results],
    )


# ---------------------------------------------------------------------------
# Season endpoints
# ---------------------------------------------------------------------------


@app.get("/seasons", response_model=list[SeasonInfo])
def list_seasons(db: Session = Depends(get_db)):
    """
    Returns all seasons ordered by creation date.

    Args:
        db: Injected database session.

    Returns:
        List of SeasonInfo objects.
    """
    return season_svc.get_all_seasons(db)


@app.get("/seasons/active", response_model=SeasonInfo)
def get_active_season(db: Session = Depends(get_db)):
    """
    Returns the currently active season.

    Args:
        db: Injected database session.

    Returns:
        SeasonInfo for the active season.

    Raises:
        404 if no active season exists.
    """
    s = season_svc.get_active_season(db)
    if s is None:
        raise HTTPException(status_code=404, detail="No active season")
    return s


@app.post("/seasons", response_model=SeasonInfo, status_code=201)
def create_season(payload: SeasonCreate, db: Session = Depends(get_db)):
    """
    Creates a new active season, closing any currently active one.

    Args:
        payload: SeasonCreate with the new season's name.
        db: Injected database session.

    Returns:
        SeasonInfo for the newly created season.
    """
    return season_svc.create_season(db, name=payload.name)


@app.post("/seasons/reset", response_model=SeasonResetResponse)
def reset_season(payload: SeasonCreate, db: Session = Depends(get_db)):
    """
    Resets the active season: closes it and opens a new one.

    All historical data from the closed season is preserved and
    queryable via season_id. The new season starts with a clean slate.

    Args:
        payload: SeasonCreate with the new season's name.
        db: Injected database session.

    Returns:
        SeasonResetResponse with details of both the closed and new season.

    Raises:
        400 if there is no active season to reset.
    """
    try:
        result = season_svc.reset_season(db, new_season_name=payload.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SeasonResetResponse(
        message=f"Season reset. '{result['closed_season'].name}' closed, '{result['new_season'].name}' is now active.",
        closed_season=result["closed_season"],
        new_season=result["new_season"],
    )


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------


@app.get("/dashboard", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db)):
    """
    Returns aggregated system-wide statistics for the ops dashboard.

    Includes total players, matches, flags, seasons, active season info,
    top player, and clean rate — all scoped to the active season where relevant.

    Args:
        db: Injected database session.

    Returns:
        DashboardStats object.
    """
    stats = season_svc.get_dashboard_stats(db)
    return DashboardStats(**stats)
