"""Database connection management for GlobalLM.

Provides a singleton connection pool that can be safely used across
multiple processes with proper connection lifecycle management.
"""

import os
from typing import Any, ContextManager

import psycopg
from psycopg_pool import ConnectionPool
from structlog import get_logger

logger = get_logger(__name__)


class Database:
    """Database connection pool manager.

    Implements singleton pattern with lazy initialization.
    The connection pool is created on first access and reused across
    all instances in the process.
    """

    _pool: ConnectionPool[Any] | None = None

    @classmethod
    def get_pool(cls) -> ConnectionPool[Any]:
        """Get or create the connection pool.

        Returns:
            Connection pool instance.
        """
        if cls._pool is None:
            cls._pool = ConnectionPool(
                cls._get_dsn(),
                min_size=2,  # Minimum connections
                max_size=10,  # Maximum connections per process
                timeout=5,  # Connection timeout in seconds
                max_idle=300,  # Close idle connections after 5 minutes
                reconnect_timeout=5,
            )
            logger.info("created_connection_pool", dsn=cls._get_dsn(minimized=True))
        return cls._pool

    @classmethod
    def _get_dsn(cls, minimized: bool = False) -> str:
        """Get the database connection string.

        Args:
            minimized: If True, return DSN without password for logging.

        Returns:
            PostgreSQL DSN string.
        """
        # Check for environment variable override
        dsn = os.getenv("GLOBALLM_DATABASE_URL")
        if dsn:
            if minimized:
                # Hide password in logs
                parts = dsn.split("://")
                if len(parts) == 2:
                    auth_host = parts[1].split("@")
                    if len(auth_host) == 2:
                        return f"{parts[0].split('@')[0]}://***@{auth_host[1]}"
            return dsn

        # Default: docker-compose PostgreSQL
        default = "postgresql://globallm:globallm@localhost:5432/globallm"
        if minimized:
            return "postgresql://***:***@localhost:5432/globallm"
        return default

    @classmethod
    def close(cls) -> None:
        """Close the connection pool.

        Should be called when shutting down the application.
        """
        if cls._pool is not None:
            cls._pool.close()
            cls._pool = None
            logger.info("closed_connection_pool")


def get_connection() -> ContextManager[psycopg.Connection[Any]]:
    """Get a connection from the pool.

    Usage:
        with get_connection() as conn:
            # Use connection
            pass

    Returns:
        Connection context manager that yields a Connection object.
    """
    pool = Database.get_pool()
    return pool.connection()
