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

    def get_top_issues(
        self, limit: int = 20, skip_assigned: bool = True
    ) -> list[dict[str, Any]]:
        """Get top prioritized issues.

        Args:
            limit: Maximum number of issues to return.
            skip_assigned: If True, skip issues that are assigned with active heartbeat.

        Returns:
            List of issue dictionaries sorted by priority (descending).
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    if skip_assigned:
                        cur.execute(
                            """
                            SELECT data FROM issues
                            WHERE assignment_status IN ('available', 'completed', 'failed')
                               OR (assignment_status = 'assigned'
                                   AND last_heartbeat_at < NOW() - INTERVAL '30 minutes')
                            ORDER BY (data->>'priority')::numeric DESC NULLS LAST
                            LIMIT %s
                        """,
                            (limit,),
                        )
                    else:
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

    def assign_issue(self, repository: str, number: int, agent_id: str) -> bool:
        """Atomically assign an issue to an agent if available.

        Uses SELECT FOR UPDATE to prevent race conditions.

        Args:
            repository: Repository name
            number: Issue number
            agent_id: Agent ID to assign to

        Returns:
            True if assignment succeeded, False if issue not available
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Start transaction
                    cur.execute("BEGIN")

                    # Lock the row and check current status
                    cur.execute(
                        """
                        SELECT assignment_status, assigned_to, last_heartbeat_at
                        FROM issues
                        WHERE repository = %s AND number = %s
                        FOR UPDATE
                    """,
                        (repository, number),
                    )

                    result = cur.fetchone()
                    if not result:
                        conn.rollback()
                        return False

                    status, assigned_to, last_heartbeat = result

                    # Check if issue is available, failed, or assignment is stale
                    if status in ("available", "failed") or self._is_assignment_stale(last_heartbeat):
                        # Assign the issue
                        now = datetime.now()
                        cur.execute(
                            """
                            UPDATE issues
                            SET assignment_status = 'assigned',
                                assigned_to = %s,
                                assigned_at = %s,
                                last_heartbeat_at = %s,
                                updated_at = NOW()
                            WHERE repository = %s AND number = %s
                        """,
                            (agent_id, now, now, repository, number),
                        )
                        conn.commit()
                        logger.info(
                            "issue_assigned",
                            repository=repository,
                            number=number,
                            agent_id=agent_id,
                        )
                        return True

                    conn.rollback()
                    return False

        except Exception as e:
            logger.error("failed_to_assign_issue", error=str(e))
            raise

    def release_issue(
        self, repository: str, number: int, agent_id: str, status: str = "available"
    ) -> None:
        """Release an issue assignment.

        Args:
            repository: Repository name
            number: Issue number
            agent_id: Agent ID releasing the issue
            status: New status ('available', 'completed', 'failed')
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE issues
                        SET assignment_status = %s,
                            assigned_to = NULL,
                            assigned_at = NULL,
                            last_heartbeat_at = NULL,
                            updated_at = NOW()
                        WHERE repository = %s AND number = %s AND assigned_to = %s
                    """,
                        (status, repository, number, agent_id),
                    )
                    conn.commit()
                    logger.info(
                        "issue_released",
                        repository=repository,
                        number=number,
                        agent_id=agent_id,
                        status=status,
                    )
        except Exception as e:
            logger.error("failed_to_release_issue", error=str(e))
            raise

    def send_heartbeat(self, repository: str, number: int, agent_id: str) -> bool:
        """Update heartbeat timestamp for assigned issue.

        Args:
            repository: Repository name
            number: Issue number
            agent_id: Agent ID sending heartbeat

        Returns:
            True if heartbeat updated, False if issue not assigned to this agent
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE issues
                        SET last_heartbeat_at = NOW()
                        WHERE repository = %s AND number = %s
                          AND assigned_to = %s
                          AND assignment_status = 'assigned'
                    """,
                        (repository, number, agent_id),
                    )
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error("failed_to_send_heartbeat", error=str(e))
            return False

    def get_assigned_issue(self, agent_id: str) -> dict[str, Any] | None:
        """Get the issue currently assigned to an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Issue dict or None
        """
        try:
            with get_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT data FROM issues
                        WHERE assigned_to = %s AND assignment_status = 'assigned'
                    """,
                        (agent_id,),
                    )
                    result = cur.fetchone()
                    return result["data"] if result else None
        except Exception as e:
            logger.error("failed_to_get_assigned_issue", error=str(e))
            return None

    def claim_next_available_issue(
        self, agent_id: str, limit: int = 1
    ) -> dict[str, Any] | None:
        """Claim the next highest-priority available issue.

        Args:
            agent_id: Agent ID to assign to
            limit: Max issues to return (typically 1)

        Returns:
            Issue dict or None if no available issues
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Start transaction for atomic claim
                    cur.execute("BEGIN")

                    # Find highest priority available issue
                    cur.execute(
                        """
                        SELECT repository, number
                        FROM issues
                        WHERE assignment_status = 'available'
                        ORDER BY (data->>'priority')::numeric DESC NULLS LAST
                        LIMIT %s
                        FOR UPDATE
                    """,
                        (limit,),
                    )

                    candidates = cur.fetchall()
                    if not candidates:
                        conn.rollback()
                        return None

                    repository, number = candidates[0]

                    # Assign it
                    now = datetime.now()
                    cur.execute(
                        """
                        UPDATE issues
                        SET assignment_status = 'assigned',
                            assigned_to = %s,
                            assigned_at = %s,
                            last_heartbeat_at = %s,
                            updated_at = NOW()
                        WHERE repository = %s AND number = %s
                    """,
                        (agent_id, now, now, repository, number),
                    )

                    conn.commit()

                    # Fetch and return the full issue data
                    return self.get_issue(repository, number)

        except Exception as e:
            logger.error("failed_to_claim_next_issue", error=str(e))
            raise

    def release_stale_assignments(self, timeout_seconds: int = 1800) -> int:
        """Release assignments with stale heartbeats.

        Args:
            timeout_seconds: Seconds without heartbeat before considered stale

        Returns:
            Number of issues released
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE issues
                        SET assignment_status = 'available',
                            assigned_to = NULL,
                            assigned_at = NULL,
                            last_heartbeat_at = NULL,
                            updated_at = NOW()
                        WHERE assignment_status = 'assigned'
                          AND last_heartbeat_at < NOW() - INTERVAL '%s seconds'
                    """,
                        (timeout_seconds,),
                    )
                    conn.commit()
                    count = cur.rowcount
                    if count > 0:
                        logger.info("released_stale_assignments", count=count)
                    return count
        except Exception as e:
            logger.error("failed_to_release_stale_assignments", error=str(e))
            return 0

    def _is_assignment_stale(
        self, last_heartbeat: datetime | None, timeout_seconds: int = 1800
    ) -> bool:
        """Check if an assignment is stale.

        Args:
            last_heartbeat: Last heartbeat timestamp
            timeout_seconds: Seconds before considering stale

        Returns:
            True if stale
        """
        if last_heartbeat is None:
            return True
        age = (datetime.now() - last_heartbeat).total_seconds()
        return age > timeout_seconds
