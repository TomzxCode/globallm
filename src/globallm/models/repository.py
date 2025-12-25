"""Repository-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Language(Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"

    @classmethod
    def from_string(cls, value: str) -> "Language | None":
        """Parse language from string, case-insensitive."""
        for lang in cls:
            if lang.value.lower() == value.lower():
                return lang
        # Handle common aliases
        value_lower = value.lower()
        if value_lower in ("js", "node", "nodejs"):
            return cls.JAVASCRIPT
        if value_lower in ("ts",):
            return cls.TYPESCRIPT
        if value_lower in ("golang",):
            return cls.GO
        if value_lower in ("py",):
            return cls.PYTHON
        return None


@dataclass(frozen=True)
class HealthScore:
    """Repository health metrics."""

    commit_velocity: float  # 0-1, normalized commits in last 90 days
    issue_resolution_rate: float  # 0-1, closed / (closed + open)
    ci_status: float  # 0-1, CI pass rate or has_ci boolean
    contributor_diversity: float  # 0-1, unique contributors / max contributors
    documentation_quality: float  # 0-1, has docs + readme + examples

    @property
    def overall(self) -> float:
        """Calculate overall health score with weighted components."""
        return (
            self.commit_velocity * 0.30
            + self.issue_resolution_rate * 0.25
            + self.ci_status * 0.20
            + self.contributor_diversity * 0.15
            + self.documentation_quality * 0.10
        )


@dataclass
class RepoCandidate:
    """A repository candidate for analysis."""

    name: str  # "owner/repo"
    stars: int
    forks: int
    open_issues: int
    watchers: int
    subscribers: int
    language: Language | None
    description: str | None
    last_commit_at: datetime | None
    created_at: datetime | None
    dependents: int = 0  # Number of packages depending on this
    health_score: HealthScore | None = None

    # Package registry specific
    package_name: str | None = None  # e.g., "requests" for PyPI
    registry_url: str | None = None  # e.g., "https://pypi.org/p/requests"

    @property
    def is_worth_maintaining(self) -> bool:
        """Determine if repository is worth maintaining based on health."""
        if self.health_score is None:
            return True  # Unknown, assume yes
        # Abandoned if no commits in 6+ months
        if self.last_commit_at:
            days_since = (
                datetime.now(tz=self.last_commit_at.tzinfo) - self.last_commit_at
            ).days
            if days_since > 180 and self.health_score.overall < 0.3:
                return False
        return True


@dataclass
class Repository:
    """Full repository context for solution generation."""

    name: str
    owner: str
    description: str | None
    language: Language | None
    stars: int
    forks: int
    open_issues: int
    watchers: int
    subscribers: int
    dependents: int
    health_score: HealthScore
    last_commit_at: datetime | None
    has_ci: bool
    has_tests: bool
    test_coverage: float | None  # 0-1
    has_type_hints: bool
    has_docs: bool
    topics: list[str] = field(default_factory=list)
    license: str | None = None
    archived: bool = False
    default_branch: str = "main"

    @property
    def impact_score(self) -> float:
        """Calculate dependency-graph-based impact score."""
        return (
            self.stars * 1.0
            + self.forks * 2.0
            + self.subscribers * 5.0
            + self.dependents * 10.0  # Dependents weighted highest
        )


@dataclass
class MaintenanceVerdict:
    """Verdict on whether a repository is worth maintaining."""

    worthy: bool
    reason: str
