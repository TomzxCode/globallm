"""Repository-related data models."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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

    # Analysis fields
    worth_working_on: bool | None = None  # Set after analysis
    analyzed_at: datetime | None = None  # When analysis was performed
    analysis_reason: str | None = None  # Explanation of the decision

    @property
    def impact_score(self) -> float:
        """Calculate dependency-graph-based impact score."""
        return (
            self.stars * 1.0
            + self.forks * 2.0
            + self.subscribers * 5.0
            + self.dependents * 10.0  # Dependents weighted highest
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        d = asdict(self)
        # Convert HealthScore to dict
        if isinstance(d.get("health_score"), dict):
            # Already converted by asdict
            pass
        elif self.health_score is not None:
            d["health_score"] = asdict(self.health_score)
        # Convert Language enum to string
        if self.language is not None:
            d["language"] = self.language.value
        # Convert datetime to ISO format
        if self.last_commit_at is not None:
            d["last_commit_at"] = self.last_commit_at.isoformat()
        if self.analyzed_at is not None:
            d["analyzed_at"] = self.analyzed_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Repository":
        """Create from dictionary for YAML deserialization."""
        # Handle health_score dict conversion
        health_score_data = data.pop("health_score", None)
        if isinstance(health_score_data, dict):
            health_score = HealthScore(**health_score_data)
        else:
            health_score = health_score_data

        # Handle Language string to enum conversion
        language_str = data.pop("language", None)
        if language_str is not None:
            language = Language.from_string(language_str)
        else:
            language = None

        # Handle datetime parsing
        last_commit_at_str = data.pop("last_commit_at", None)
        if last_commit_at_str:
            last_commit_at = datetime.fromisoformat(last_commit_at_str)
        else:
            last_commit_at = None

        analyzed_at_str = data.pop("analyzed_at", None)
        if analyzed_at_str:
            analyzed_at = datetime.fromisoformat(analyzed_at_str)
        else:
            analyzed_at = None

        return cls(
            health_score=health_score,
            language=language,
            last_commit_at=last_commit_at,
            analyzed_at=analyzed_at,
            **data,
        )


@dataclass
class MaintenanceVerdict:
    """Verdict on whether a repository is worth maintaining."""

    worthy: bool
    reason: str
