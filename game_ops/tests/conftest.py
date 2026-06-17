"""
conftest.py

Pytest fixtures for the Game Ops test suite.

- create_test_database: session-scoped autouse fixture that creates the
  test PostgreSQL database if it does not already exist.
- client: function-scoped fixture that sets up a fresh test database schema,
  yields a TestClient, and tears down all tables after each test.
"""

import os

import psycopg2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db

# Resolve URLs
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/game_ops_db")

# Derive test URL by replacing the database name at the end of the URL
_base, _db_name = DATABASE_URL.rsplit("/", 1)
TEST_DATABASE_URL = f"{_base}/game_ops_db_test"


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """
    Session-scoped fixture that creates the test PostgreSQL database
    (game_ops_db_test) if it does not already exist.

    Connects to the 'postgres' maintenance database with AUTOCOMMIT
    isolation level so that CREATE DATABASE can execute outside a transaction.

    Yields:
        None — runs once before all tests in the session.
    """
    # Connect to the postgres maintenance DB to issue CREATE DATABASE
    conn = psycopg2.connect(
        host=_extract_host(DATABASE_URL),
        port=_extract_port(DATABASE_URL),
        user=_extract_user(DATABASE_URL),
        password=_extract_password(DATABASE_URL),
        dbname="postgres",
    )
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Check if the test database already exists before creating it
    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = 'game_ops_db_test'"
    )
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE game_ops_db_test")

    cursor.close()
    conn.close()
    yield


@pytest.fixture(scope="function")
def client():
    """
    Function-scoped fixture that provides a TestClient backed by a fresh
    test database schema.

    Setup:
        - Creates a new engine and session factory bound to game_ops_db_test.
        - Runs create_all to build all tables.
        - Overrides the FastAPI get_db dependency to use the test session.

    Teardown:
        - Drops all tables after each test so tests are fully isolated.

    Yields:
        TestClient: A configured test HTTP client for the FastAPI app.
    """
    from main import app  # Import here to avoid circular import at module level

    test_engine = create_engine(TEST_DATABASE_URL)
    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        """Yields a test database session."""
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Teardown: drop all tables for a clean slate on the next test
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()
    test_engine.dispose()


# ---------------------------------------------------------------------------
# URL parsing helpers
# ---------------------------------------------------------------------------


def _extract_host(url: str) -> str:
    """Extracts the host from a PostgreSQL connection URL."""
    # Format: postgresql://user:password@host:port/dbname
    after_at = url.split("@")[1]
    host_port = after_at.split("/")[0]
    return host_port.split(":")[0]


def _extract_port(url: str) -> int:
    """Extracts the port from a PostgreSQL connection URL."""
    after_at = url.split("@")[1]
    host_port = after_at.split("/")[0]
    parts = host_port.split(":")
    return int(parts[1]) if len(parts) > 1 else 5432


def _extract_user(url: str) -> str:
    """Extracts the username from a PostgreSQL connection URL."""
    # Format: postgresql://user:password@...
    credentials = url.split("://")[1].split("@")[0]
    return credentials.split(":")[0]


def _extract_password(url: str) -> str:
    """Extracts the password from a PostgreSQL connection URL."""
    credentials = url.split("://")[1].split("@")[0]
    parts = credentials.split(":")
    return parts[1] if len(parts) > 1 else ""
