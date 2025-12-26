"""Database schema initialization and migrations."""

from typing import Any

from psycopg.rows import dict_row
from structlog import get_logger

from globallm.storage.db import get_connection

logger = get_logger(__name__)

# Schema version for future migrations
SCHEMA_VERSION = 1

# SQL schema definition
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Issues table
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    repository VARCHAR(255) NOT NULL,
    number INTEGER NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(repository, number)
);

-- Indexes for issues
CREATE INDEX IF NOT EXISTS idx_issues_repository ON issues(repository);
CREATE INDEX IF NOT EXISTS idx_issues_repository_number ON issues(repository, number);
CREATE INDEX IF NOT EXISTS idx_issues_data ON issues USING GIN (data);

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    worth_working_on BOOLEAN,
    analyzed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for repositories
CREATE INDEX IF NOT EXISTS idx_repos_name ON repositories(name);
CREATE INDEX IF NOT EXISTS idx_repos_worth_working_on ON repositories(worth_working_on);
CREATE INDEX IF NOT EXISTS idx_repos_data ON repositories USING GIN (data);
"""


def init_database(drop_existing: bool = False) -> None:
    """Initialize the database schema.

    Args:
        drop_existing: If True, drops existing tables before creating.
                       WARNING: This will delete all data!
    """
    try:
        with get_connection() as conn:
            if drop_existing:
                # Drop all tables
                with conn.cursor() as cur:
                    cur.execute("DROP TABLE IF EXISTS issues CASCADE")
                    cur.execute("DROP TABLE IF EXISTS repositories CASCADE")
                    cur.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")
                conn.commit()
                logger.warning("dropped_existing_tables")

            # Execute schema
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)

                # Record schema version
                cur.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (%s)
                    ON CONFLICT (version) DO NOTHING
                """,
                    (SCHEMA_VERSION,),
                )

            conn.commit()
            logger.info("initialized_schema", version=SCHEMA_VERSION)

    except Exception as e:
        logger.error("failed_to_initialize_schema", error=str(e))
        raise


def get_schema_version() -> int | None:
    """Get the current schema version.

    Returns:
        Schema version or None if not initialized.
    """
    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
                )
                result = cur.fetchone()
                return result["version"] if result else None
    except Exception:
        return None


def get_status() -> dict[str, Any]:
    """Get database status information.

    Returns:
        Dictionary with status information including schema version,
        connection pool info, and table row counts.
    """
    from globallm.storage.db import Database

    status: dict[str, Any] = {
        "schema_version": get_schema_version(),
        "pool": {
            "active": Database._pool is not None,
        },
    }

    if Database._pool:
        stats = Database._pool.get_stats()
        status["pool"]["stats"] = stats
        status["pool"]["min_size"] = Database._pool.min_size
        status["pool"]["max_size"] = Database._pool.max_size

    # Get row counts
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM issues")
                status["issues_count"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM repositories")
                status["repositories_count"] = cur.fetchone()[0]
    except Exception as e:
        status["error"] = str(e)

    return status
