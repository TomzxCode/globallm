"""Persistent issue storage."""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from structlog import get_logger


logger = get_logger(__name__)

# Storage directory (XDG Data Home)
STATE_DIR = Path.home() / ".local" / "share" / "globallm"
STATE_FILE = STATE_DIR / "issues.yaml"


class IssueStore:
    """Persistent storage for prioritized issues."""

    def __init__(self, state_file: Path | None = None) -> None:
        """Initialize the issue store.

        Args:
            state_file: Path to the state file. Defaults to ~/.local/share/globallm/issues.yaml
        """
        self._state_file = state_file or STATE_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the state directory exists."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def load_issues(self) -> list[dict[str, Any]]:
        """Load all issues from storage.

        Returns:
            List of issue dictionaries, or empty list if file doesn't exist.
        """
        if not self._state_file.exists():
            logger.debug("no_issue_file", path=str(self._state_file))
            return []

        try:
            with self._state_file.open("r") as f:
                data = yaml.safe_load(f) or {}
            return data.get("issues", [])
        except Exception as e:
            logger.error("failed_to_load_issues", error=str(e))
            return []

    def save_issues(
        self, issues: list[dict[str, Any]], prioritized_at: datetime | None = None
    ) -> None:
        """Save issues to storage.

        Args:
            issues: List of issue dictionaries to save.
            prioritized_at: Timestamp when these issues were prioritized.
        """
        data: dict[str, Any] = {
            "issues": issues,
            "prioritized_at": (prioritized_at or datetime.now()).isoformat(),
        }

        self._ensure_dir()
        with self._state_file.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info("saved_issues", count=len(issues), path=str(self._state_file))

    def get_issue(self, repository: str, number: int) -> dict[str, Any] | None:
        """Get an issue by repository and number.

        Args:
            repository: Repository name (owner/repo).
            number: Issue number.

        Returns:
            Issue dictionary, or None if not found.
        """
        issues = self.load_issues()
        for issue in issues:
            if issue.get("repository") == repository and issue.get("number") == number:
                return issue
        return None

    def get_issues_by_repository(self, repository: str) -> list[dict[str, Any]]:
        """Get all issues for a repository.

        Args:
            repository: Repository name (owner/repo).

        Returns:
            List of issue dictionaries for the repository.
        """
        issues = self.load_issues()
        return [i for i in issues if i.get("repository") == repository]

    def get_top_issues(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get top prioritized issues.

        Args:
            limit: Maximum number of issues to return.

        Returns:
            List of issue dictionaries sorted by priority_score (descending).
        """
        issues = self.load_issues()
        issues.sort(key=lambda i: i.get("priority_score", 0), reverse=True)
        return issues[:limit]

    def add_or_update(self, issue_dict: dict[str, Any]) -> None:
        """Add a new issue or update an existing one.

        Args:
            issue_dict: Issue dictionary to add or update.
        """
        issues = self.load_issues()
        repository = issue_dict.get("repository")
        number = issue_dict.get("number")

        # Remove existing issue with same repository and number
        issues = [
            i
            for i in issues
            if not (i.get("repository") == repository and i.get("number") == number)
        ]

        # Add the issue
        issues.append(issue_dict)
        self.save_issues(issues)

        logger.debug("added_or_updated_issue", repository=repository, number=number)
