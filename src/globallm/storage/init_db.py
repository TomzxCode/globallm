"""Database schema initialization and migrations."""

from typing import Any

from psycopg.rows import dict_row
from structlog import get_logger

from globallm.storage.db import get_connection

logger = get_logger(__name__)

# Schema version for future migrations
SCHEMA_VERSION = 2

# Migration definitions
# Each migration is a (from_version, to_version, description, sql_function) tuple
MIGRATIONS: list[tuple[int, int, str, Any]] = []

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
    -- Assignment tracking
    assigned_to VARCHAR(255) NULL,
    assigned_at TIMESTAMP WITH TIME ZONE NULL,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE NULL,
    assignment_status VARCHAR(50) DEFAULT 'available',
    UNIQUE(repository, number)
);

-- Indexes for issues
CREATE INDEX IF NOT EXISTS idx_issues_repository ON issues(repository);
CREATE INDEX IF NOT EXISTS idx_issues_repository_number ON issues(repository, number);
CREATE INDEX IF NOT EXISTS idx_issues_data ON issues USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_issues_assignment_status ON issues(assignment_status);
CREATE INDEX IF NOT EXISTS idx_issues_assigned_to ON issues(assigned_to);
CREATE INDEX IF NOT EXISTS idx_issues_last_heartbeat ON issues(last_heartbeat_at);

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
                row = cur.fetchone()
                status["issues_count"] = row[0] if row else 0

                cur.execute("SELECT COUNT(*) FROM repositories")
                row = cur.fetchone()
                status["repositories_count"] = row[0] if row else 0
    except Exception as e:
        status["error"] = str(e)

    return status


def migrate_1_to_2() -> None:
    """Migration from schema version 1 to 2.

    Adds assignment tracking columns to the issues table.
    """
    sql = """
    -- Add assignment tracking columns
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255) NULL;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP WITH TIME ZONE NULL;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP WITH TIME ZONE NULL;
    ALTER TABLE issues ADD COLUMN IF NOT EXISTS assignment_status VARCHAR(50) DEFAULT 'available';

    -- Create indexes for assignment queries
    CREATE INDEX IF NOT EXISTS idx_issues_assignment_status ON issues(assignment_status);
    CREATE INDEX IF NOT EXISTS idx_issues_assigned_to ON issues(assigned_to);
    CREATE INDEX IF NOT EXISTS idx_issues_last_heartbeat ON issues(last_heartbeat_at);

    -- Set default status for existing issues
    UPDATE issues SET assignment_status = 'available' WHERE assignment_status IS NULL;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    logger.info("migration_1_to_2_completed")


# Register migrations
MIGRATIONS.append((1, 2, "Add issue assignment tracking", migrate_1_to_2))


def get_pending_migrations() -> list[tuple[int, int, str, Any]]:
    """Get list of pending migrations based on current schema version.

    Returns:
        List of migrations that need to be applied.
    """
    current_version = get_schema_version()
    if current_version is None:
        return []

    pending = [
        (from_v, to_v, desc, fn)
        for from_v, to_v, desc, fn in MIGRATIONS
        if from_v >= current_version and to_v > current_version
    ]

    # Sort by version number
    pending.sort(key=lambda x: x[0])
    return pending


def migrate() -> None:
    """Run pending database migrations.

    Raises:
        Exception: If migration fails.
    """
    pending = get_pending_migrations()

    if not pending:
        logger.info("no_pending_migrations", current_version=get_schema_version())
        return

    logger.info(
        "pending_migrations_found",
        count=len(pending),
        current_version=get_schema_version(),
    )

    for from_version, to_version, description, migration_fn in pending:
        logger.info(
            "running_migration",
            from_version=from_version,
            to_version=to_version,
            description=description,
        )

        try:
            migration_fn()
        except Exception as e:
            logger.error(
                "migration_failed",
                from_version=from_version,
                to_version=to_version,
                error=str(e),
            )
            raise

        # Record the new schema version
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (%s)
                    ON CONFLICT (version) DO NOTHING
                """,
                    (to_version,),
                )
            conn.commit()

        logger.info("migration_applied", to_version=to_version)

    logger.info(
        "all_migrations_completed",
        final_version=pending[-1][1] if pending else get_schema_version(),
    )
