"""Budget state persistence."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from globallm.logging_config import get_logger

logger = get_logger(__name__)

STATE_DIR = Path.home() / ".local" / "share" / "globallm"
STATE_FILE = STATE_DIR / "budget_state.json"


@dataclass
class PerRepoBudget:
    """Budget tracking for a single repository."""

    repo: str
    tokens_used: int = 0
    time_used_seconds: int = 0
    issues_processed: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PerRepoBudget":
        return cls(**data)


@dataclass
class PerLanguageBudget:
    """Budget tracking for a single language."""

    language: str
    tokens_used: int = 0
    issues_processed: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PerLanguageBudget":
        return cls(**data)


@dataclass
class BudgetState:
    """Global budget state."""

    # Weekly budget tracking
    weekly_budget: int = 5_000_000
    weekly_used: int = 0
    week_number: int = 0
    year: int = 0

    # Per-repo tracking
    per_repo: dict[str, PerRepoBudget] = field(default_factory=dict)

    # Per-language tracking
    per_language: dict[str, PerLanguageBudget] = field(default_factory=dict)

    # Global stats
    total_tokens_used: int = 0
    total_issues_processed: int = 0
    total_prs_created: int = 0

    # Timestamps
    created_at: str = ""
    last_updated: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()

    @property
    def current_week(self) -> tuple[int, int]:
        """Get current (year, week_number)."""
        now = datetime.now()
        return now.isocalendar()[:2]

    @property
    def weekly_remaining(self) -> int:
        """Get remaining weekly budget."""
        return max(0, self.weekly_budget - self.weekly_used)

    @property
    def weekly_used_percent(self) -> float:
        """Get percentage of weekly budget used."""
        if self.weekly_budget == 0:
            return 0.0
        return (self.weekly_used / self.weekly_budget) * 100

    def check_and_reset_week(self) -> bool:
        """Check if week has changed and reset if needed.

        Returns:
            True if week was reset
        """
        current_year, current_week = self.current_week

        if self.year != current_year or self.week_number != current_week:
            logger.info(
                "weekly_budget_reset",
                old_year=self.year,
                old_week=self.week_number,
                new_year=current_year,
                new_week=current_week,
            )
            self.week_number = current_week
            self.year = current_year
            self.weekly_used = 0
            return True

        return False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "weekly_budget": self.weekly_budget,
            "weekly_used": self.weekly_used,
            "week_number": self.week_number,
            "year": self.year,
            "per_repo": {
                repo: budget.to_dict() for repo, budget in self.per_repo.items()
            },
            "per_language": {
                lang: budget.to_dict() for lang, budget in self.per_language.items()
            },
            "total_tokens_used": self.total_tokens_used,
            "total_issues_processed": self.total_issues_processed,
            "total_prs_created": self.total_prs_created,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BudgetState":
        """Create from dictionary."""
        per_repo = {
            repo: PerRepoBudget.from_dict(budget_data)
            for repo, budget_data in data.get("per_repo", {}).items()
        }
        per_language = {
            lang: PerLanguageBudget.from_dict(budget_data)
            for lang, budget_data in data.get("per_language", {}).items()
        }

        return cls(
            weekly_budget=data.get("weekly_budget", 5_000_000),
            weekly_used=data.get("weekly_used", 0),
            week_number=data.get("week_number", 0),
            year=data.get("year", 0),
            per_repo=per_repo,
            per_language=per_language,
            total_tokens_used=data.get("total_tokens_used", 0),
            total_issues_processed=data.get("total_issues_processed", 0),
            total_prs_created=data.get("total_prs_created", 0),
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
        )

    def save(self) -> None:
        """Save state to file."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        self.check_and_reset_week()
        self.last_updated = datetime.now().isoformat()

        try:
            with STATE_FILE.open("w") as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.debug("budget_state_saved", path=str(STATE_FILE))
        except Exception as e:
            logger.error("budget_state_save_failed", error=str(e))

    @classmethod
    def load(cls) -> "BudgetState":
        """Load state from file."""
        if not STATE_FILE.exists():
            logger.info("budget_state_not_found", creating_new=True)
            state = cls()
            # Initialize with current week
            year, week = state.current_week
            state.year = year
            state.week_number = week
            state.save()
            return state

        try:
            with STATE_FILE.open("r") as f:
                data = json.load(f)

            state = cls.from_dict(data)
            state.check_and_reset_week()
            logger.info("budget_state_loaded", path=str(STATE_FILE))
            return state

        except Exception as e:
            logger.error("budget_state_load_failed", error=str(e))
            # Return new state on error
            return cls()

    def record_repo_tokens(self, repo: str, tokens: int) -> None:
        """Record token usage for a repository."""
        if repo not in self.per_repo:
            self.per_repo[repo] = PerRepoBudget(repo=repo)

        self.per_repo[repo].tokens_used += tokens
        self.per_repo[repo].last_updated = datetime.now().isoformat()

        self.weekly_used += tokens
        self.total_tokens_used += tokens

    def record_language_tokens(self, language: str, tokens: int) -> None:
        """Record token usage for a language."""
        if language not in self.per_language:
            self.per_language[language] = PerLanguageBudget(language=language)

        self.per_language[language].tokens_used += tokens
        self.per_language[language].last_updated = datetime.now().isoformat()

    def record_issue_processed(self, repo: str, language: str) -> None:
        """Record that an issue was processed."""
        if repo not in self.per_repo:
            self.per_repo[repo] = PerRepoBudget(repo=repo)

        self.per_repo[repo].issues_processed += 1

        if language not in self.per_language:
            self.per_language[language] = PerLanguageBudget(language=language)

        self.per_language[language].issues_processed += 1
        self.total_issues_processed += 1

    def record_pr_created(self) -> None:
        """Record that a PR was created."""
        self.total_prs_created += 1

    def get_repo_tokens(self, repo: str) -> int:
        """Get tokens used for a repository."""
        return self.per_repo.get(repo, PerRepoBudget(repo=repo)).tokens_used

    def get_language_tokens(self, language: str) -> int:
        """Get tokens used for a language."""
        return self.per_language.get(
            language, PerLanguageBudget(language=language)
        ).tokens_used

    def get_repo_issues(self, repo: str) -> int:
        """Get issues processed for a repository."""
        return self.per_repo.get(repo, PerRepoBudget(repo=repo)).issues_processed

    def get_language_issues(self, language: str) -> int:
        """Get issues processed for a language."""
        return self.per_language.get(
            language, PerLanguageBudget(language=language)
        ).issues_processed
