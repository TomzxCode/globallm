"""Persistent repository storage using PostgreSQL."""

from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json
from structlog import get_logger

from globallm.storage.db import get_connection

logger = get_logger(__name__)


class RepositoryStore:
    """Persistent storage for discovered and analyzed repositories using PostgreSQL."""

    def load_repositories(self) -> list[dict[str, Any]]:
        """Load all repositories from storage.

        Returns:
            List of repository dictionaries.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT data FROM repositories")
                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_load_repositories", error=str(e))
            return []

    def save_repositories(
        self, repos: list[dict[str, Any]], discovered_at: datetime | None = None
    ) -> None:
        """Save repositories to storage (replaces all existing).

        Args:
            repos: List of repository dictionaries to save.
            discovered_at: Timestamp when these repos were discovered.
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    timestamp = (discovered_at or datetime.now()).isoformat()

                    for repo in repos:
                        # Extract worth_working_on for indexed column
                        worth_working_on = repo.get("worth_working_on")
                        analyzed_at = repo.get("analyzed_at")

                        # Add metadata
                        repo.setdefault("_metadata", {})["discovered_at"] = timestamp

                        cur.execute(
                            """
                            INSERT INTO repositories (name, data, worth_working_on, analyzed_at)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (name)
                            DO UPDATE SET data = EXCLUDED.data,
                                          worth_working_on = EXCLUDED.worth_working_on,
                                          analyzed_at = EXCLUDED.analyzed_at,
                                          updated_at = NOW()
                        """,
                            (
                                repo.get("name"),
                                Json(repo),
                                worth_working_on,
                                datetime.fromisoformat(analyzed_at)
                                if analyzed_at
                                else None,
                            ),
                        )

                conn.commit()
                logger.info("saved_repositories", count=len(repos))
        except Exception as e:
            logger.error("failed_to_save_repositories", error=str(e))
            raise

    def get_repository(self, name: str) -> dict[str, Any] | None:
        """Get a repository by name.

        Args:
            name: Repository name (owner/repo).

        Returns:
            Repository dictionary, or None if not found.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM repositories
                        WHERE name = %s
                    """,
                        (name,),
                    )

                    result = cur.fetchone()
                    return result["data"] if result else None
        except Exception as e:
            logger.error("failed_to_get_repository", name=name, error=str(e))
            return None

    def update_repository(self, name: str, **kwargs: Any) -> None:
        """Update fields of a repository.

        Args:
            name: Repository name (owner/repo).
            **kwargs: Fields to update (e.g., worth_working_on=True).
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # First fetch existing data
                    cur.execute(
                        """
                        SELECT data, worth_working_on FROM repositories WHERE name = %s
                    """,
                        (name,),
                    )

                    result = cur.fetchone()
                    if result is None:
                        logger.warning("repository_not_found_for_update", name=name)
                        return

                    data, current_worth = result
                    data.update(kwargs)

                    # Update the worth_working_on column if provided
                    worth_working_on = kwargs.get("worth_working_on", current_worth)
                    analyzed_at = data.get("analyzed_at")

                    cur.execute(
                        """
                        UPDATE repositories
                        SET data = %s,
                            worth_working_on = %s,
                            analyzed_at = %s,
                            updated_at = NOW()
                        WHERE name = %s
                    """,
                        (
                            Json(data),
                            worth_working_on,
                            datetime.fromisoformat(analyzed_at)
                            if analyzed_at
                            else None,
                            name,
                        ),
                    )

                conn.commit()
                logger.info("updated_repository", name=name, fields=list(kwargs.keys()))
        except Exception as e:
            logger.error("failed_to_update_repository", name=name, error=str(e))
            raise

    def add_or_update(self, repo_dict: dict[str, Any]) -> None:
        """Add a new repository or update an existing one.

        Args:
            repo_dict: Repository dictionary to add or update.
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    worth_working_on = repo_dict.get("worth_working_on")
                    analyzed_at = repo_dict.get("analyzed_at")

                    cur.execute(
                        """
                        INSERT INTO repositories (name, data, worth_working_on, analyzed_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (name)
                        DO UPDATE SET data = EXCLUDED.data,
                                      worth_working_on = EXCLUDED.worth_working_on,
                                      analyzed_at = EXCLUDED.analyzed_at,
                                      updated_at = NOW()
                    """,
                        (
                            repo_dict.get("name"),
                            Json(repo_dict),
                            worth_working_on,
                            datetime.fromisoformat(analyzed_at)
                            if analyzed_at
                            else None,
                        ),
                    )

                conn.commit()
                logger.debug("added_or_updated_repository", name=repo_dict.get("name"))
        except Exception as e:
            logger.error(
                "failed_to_add_or_update_repository",
                name=repo_dict.get("name"),
                error=str(e),
            )
            raise

    def get_approved(self) -> list[dict[str, Any]]:
        """Get repositories marked as worth working on.

        Returns:
            List of repository dictionaries where worth_working_on is True.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM repositories
                        WHERE worth_working_on = TRUE
                    """
                    )
                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_get_approved", error=str(e))
            return []

    def get_rejected(self) -> list[dict[str, Any]]:
        """Get repositories marked as NOT worth working on.

        Returns:
            List of repository dictionaries where worth_working_on is False.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM repositories
                        WHERE worth_working_on = FALSE
                    """
                    )
                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_get_rejected", error=str(e))
            return []

    def get_unanalyzed(self) -> list[dict[str, Any]]:
        """Get repositories that haven't been analyzed yet.

        Returns:
            List of repository dictionaries where worth_working_on is NULL.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM repositories
                        WHERE worth_working_on IS NULL
                    """
                    )
                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_get_unanalyzed", error=str(e))
            return []
