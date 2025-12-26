"""Persistent issue storage using PostgreSQL."""

from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json
from structlog import get_logger

from globallm.storage.db import get_connection

logger = get_logger(__name__)


class IssueStore:
    """Persistent storage for prioritized issues using PostgreSQL."""

    def load_issues(self) -> list[dict[str, Any]]:
        """Load all issues from storage.

        Returns:
            List of issue dictionaries.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("""
                        SELECT data FROM issues
                        ORDER BY (data->>'priority')::numeric DESC NULLS LAST
                    """)
                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_load_issues", error=str(e))
            return []

    def save_issues(
        self, issues: list[dict[str, Any]], prioritized_at: datetime | None = None
    ) -> None:
        """Save issues to storage (replaces all existing issues).

        Args:
            issues: List of issue dictionaries to save.
            prioritized_at: Timestamp when these issues were prioritized.
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Delete all existing issues
                    cur.execute("DELETE FROM issues")

                    # Insert new issues in batch
                    if issues:
                        timestamp = (prioritized_at or datetime.now()).isoformat()
                        for issue in issues:
                            # Add metadata to the data field
                            issue.setdefault("_metadata", {})["prioritized_at"] = (
                                timestamp
                            )

                            cur.execute(
                                """
                                INSERT INTO issues (repository, number, data)
                                VALUES (%s, %s, %s)
                            """,
                                (
                                    issue.get("repository"),
                                    issue.get("number"),
                                    Json(issue),
                                ),
                            )

                conn.commit()
                logger.info("saved_issues", count=len(issues))
        except Exception as e:
            logger.error("failed_to_save_issues", error=str(e))
            raise

    def get_issue(self, repository: str, number: int) -> dict[str, Any] | None:
        """Get an issue by repository and number.

        Args:
            repository: Repository name (owner/repo).
            number: Issue number.

        Returns:
            Issue dictionary, or None if not found.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM issues
                        WHERE repository = %s AND number = %s
                    """,
                        (repository, number),
                    )

                    result = cur.fetchone()
                    return result["data"] if result else None
        except Exception as e:
            logger.error(
                "failed_to_get_issue",
                repository=repository,
                number=number,
                error=str(e),
            )
            return None

    def get_issues_by_repository(self, repository: str) -> list[dict[str, Any]]:
        """Get all issues for a repository.

        Args:
            repository: Repository name (owner/repo).

        Returns:
            List of issue dictionaries for the repository.
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM issues
                        WHERE repository = %s
                        ORDER BY (data->>'priority')::numeric DESC NULLS LAST
                    """,
                        (repository,),
                    )

                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error(
                "failed_to_get_issues_by_repository",
                repository=repository,
                error=str(e),
            )
            return []

    def get_top_issues(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get top prioritized issues.

        Args:
            limit: Maximum number of issues to return.

        Returns:
            List of issue dictionaries sorted by priority (descending).
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM issues
                        ORDER BY (data->>'priority')::numeric DESC NULLS LAST
                        LIMIT %s
                    """,
                        (limit,),
                    )

                    results = cur.fetchall()
                    return [row["data"] for row in results]
        except Exception as e:
            logger.error("failed_to_get_top_issues", error=str(e))
            return []

    def add_or_update(self, issue_dict: dict[str, Any]) -> None:
        """Add a new issue or update an existing one.

        Args:
            issue_dict: Issue dictionary to add or update.
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO issues (repository, number, data)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (repository, number)
                        DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                        (
                            issue_dict.get("repository"),
                            issue_dict.get("number"),
                            Json(issue_dict),
                        ),
                    )

                conn.commit()
                logger.debug(
                    "added_or_updated_issue",
                    repository=issue_dict.get("repository"),
                    number=issue_dict.get("number"),
                )
        except Exception as e:
            logger.error(
                "failed_to_add_or_update_issue",
                repository=issue_dict.get("repository"),
                number=issue_dict.get("number"),
                error=str(e),
            )
            raise
