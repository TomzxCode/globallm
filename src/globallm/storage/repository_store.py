"""Persistent repository storage."""

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from structlog import get_logger


logger = get_logger(__name__)

# Storage directory (XDG Data Home)
STATE_DIR = Path.home() / ".local" / "share" / "globallm"
STATE_FILE = STATE_DIR / "repositories.yaml"


class RepositoryStore:
    """Persistent storage for discovered and analyzed repositories."""

    def __init__(self, state_file: Path | None = None) -> None:
        """Initialize the repository store.

        Args:
            state_file: Path to the state file. Defaults to ~/.local/share/globallm/repositories.yaml
        """
        self._state_file = state_file or STATE_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the state directory exists."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def load_repositories(self) -> list[dict[str, Any]]:
        """Load all repositories from storage.

        Returns:
            List of repository dictionaries, or empty list if file doesn't exist.
        """
        if not self._state_file.exists():
            logger.debug("no_repository_file", path=str(self._state_file))
            return []

        try:
            with self._state_file.open("r") as f:
                data = yaml.safe_load(f) or {}
            return data.get("repositories", [])
        except Exception as e:
            logger.error("failed_to_load_repositories", error=str(e))
            return []

    def save_repositories(
        self, repos: list[dict[str, Any]], discovered_at: datetime | None = None
    ) -> None:
        """Save repositories to storage.

        Args:
            repos: List of repository dictionaries to save.
            discovered_at: Timestamp when these repos were discovered.
        """
        data: dict[str, Any] = {
            "repositories": repos,
            "discovered_at": (discovered_at or datetime.now()).isoformat(),
        }

        self._ensure_dir()
        with self._state_file.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info("saved_repositories", count=len(repos), path=str(self._state_file))

    def get_repository(self, name: str) -> dict[str, Any] | None:
        """Get a repository by name.

        Args:
            name: Repository name (owner/repo).

        Returns:
            Repository dictionary, or None if not found.
        """
        repos = self.load_repositories()
        for repo in repos:
            if repo.get("name") == name:
                return repo
        return None

    def update_repository(self, name: str, **kwargs: Any) -> None:
        """Update fields of a repository.

        Args:
            name: Repository name (owner/repo).
            **kwargs: Fields to update (e.g., worth_working_on=True).
        """
        repos = self.load_repositories()
        updated = False

        for repo in repos:
            if repo.get("name") == name:
                repo.update(kwargs)
                updated = True
                break

        if updated:
            self.save_repositories(repos)
            logger.info("updated_repository", name=name, fields=list(kwargs.keys()))

    def add_or_update(self, repo_dict: dict[str, Any]) -> None:
        """Add a new repository or update an existing one.

        Args:
            repo_dict: Repository dictionary to add or update.
        """
        repos = self.load_repositories()
        name = repo_dict.get("name")

        # Remove existing repo with same name
        repos = [r for r in repos if r.get("name") != name]

        # Add the repo
        repos.append(repo_dict)
        self.save_repositories(repos)

        logger.debug("added_or_updated_repository", name=name)

    def get_approved(self) -> list[dict[str, Any]]:
        """Get repositories marked as worth working on.

        Returns:
            List of repository dictionaries where worth_working_on is True.
        """
        repos = self.load_repositories()
        return [r for r in repos if r.get("worth_working_on") is True]

    def get_rejected(self) -> list[dict[str, Any]]:
        """Get repositories marked as NOT worth working on.

        Returns:
            List of repository dictionaries where worth_working_on is False.
        """
        repos = self.load_repositories()
        return [r for r in repos if r.get("worth_working_on") is False]

    def get_unanalyzed(self) -> list[dict[str, Any]]:
        """Get repositories that haven't been analyzed yet.

        Returns:
            List of repository dictionaries where worth_working_on is None/null.
        """
        repos = self.load_repositories()
        return [r for r in repos if r.get("worth_working_on") is None]
