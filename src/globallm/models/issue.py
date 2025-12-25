"""Issue-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IssueCategory(Enum):
    """Categories for issue classification."""

    CRITICAL_SECURITY = "critical_security"
    BUG_CRITICAL = "bug_critical"
    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    DOCUMENTATION = "documentation"
    STYLE = "style"
    REFACTOR = "refactor"
    PERFORMANCE = "performance"
    TESTS = "tests"
    UNKNOWN = "unknown"

    @property
    def multiplier(self) -> float:
        """Priority multiplier for this category."""
        multipliers: dict[IssueCategory, float] = {
            IssueCategory.CRITICAL_SECURITY: 10.0,
            IssueCategory.BUG_CRITICAL: 5.0,
            IssueCategory.BUG: 3.0,
            IssueCategory.PERFORMANCE: 2.5,
            IssueCategory.FEATURE: 2.0,
            IssueCategory.ENHANCEMENT: 1.5,
            IssueCategory.TESTS: 1.2,
            IssueCategory.DOCUMENTATION: 1.0,
            IssueCategory.REFACTOR: 0.5,
            IssueCategory.STYLE: 0.1,
            IssueCategory.UNKNOWN: 0.5,
        }
        return multipliers.get(self, 0.5)

    @classmethod
    def from_labels(cls, labels: list[str]) -> "IssueCategory":
        """Determine category from GitHub issue labels."""
        label_set = {label.lower() for label in labels}

        # Priority order matters - check most specific first
        label_mappings = [
            ({"security", "vulnerability", "cve"}, cls.CRITICAL_SECURITY),
            ({"bug", "crash", "error"}, cls.BUG),
            ({"critical", "urgent", "blocker"}, cls.BUG_CRITICAL),
            ({"performance", "slow", "optimization"}, cls.PERFORMANCE),
            ({"feature", "enhancement"}, cls.FEATURE),
            ({"docs", "documentation"}, cls.DOCUMENTATION),
            ({"style", "lint", "formatting"}, cls.STYLE),
            ({"refactor", "cleanup"}, cls.REFACTOR),
            ({"test", "testing", "tests"}, cls.TESTS),
        ]

        for label_group, category in label_mappings:
            if label_group & label_set:
                return category

        return cls.UNKNOWN

    @classmethod
    def from_string(cls, value: str) -> "IssueCategory":
        """Parse category from string."""
        value_lower = value.lower().replace("-", "_")
        try:
            return cls[value_lower]
        except KeyError:
            return cls.UNKNOWN


class IssueSeverity(Enum):
    """Severity levels for issues."""

    TRIVIAL = "trivial"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    BLOCKER = "blocker"

    @property
    def numeric_value(self) -> int:
        """Numeric value for severity comparison."""
        return {
            IssueSeverity.TRIVIAL: 1,
            IssueSeverity.MINOR: 2,
            IssueSeverity.MAJOR: 3,
            IssueSeverity.CRITICAL: 4,
            IssueSeverity.BLOCKER: 5,
        }[self]


@dataclass
class IssueRequirements:
    """Extracted requirements from an issue."""

    description: str  # What needs to be done
    affected_files: list[str] = field(default_factory=list)  # Files that need changes
    complexity: int = 5  # 1-10 estimated complexity
    breaking_change: bool = False
    test_required: bool = True
    api_change: bool = False

    # Additional context
    dependencies: list[str] = field(default_factory=list)  # Required packages/libraries
    related_issues: list[str] = field(default_factory=list)  # Related issue URLs


@dataclass
class Issue:
    """GitHub issue with enhanced metadata."""

    number: int
    title: str
    body: str | None
    author: str
    repository: str  # "owner/repo"
    state: str  # "open", "closed"
    created_at: datetime
    updated_at: datetime
    labels: list[str]
    assignees: list[str]
    comments_count: int
    reactions: dict[str, int]  # {"+1": 10, "-1": 0, ...}

    # Analysis fields
    category: IssueCategory = IssueCategory.UNKNOWN
    severity: IssueSeverity = IssueSeverity.MINOR
    complexity: int = 5  # 1-10
    solvability: float = 0.5  # 0-1, probability of successful automated fix
    requirements: IssueRequirements | None = None

    # Computed metrics
    priority_score: float = 0.0

    @property
    def url(self) -> str:
        """GitHub URL for this issue."""
        return f"https://github.com/{self.repository}/issues/{self.number}"

    @property
    def is_assigned(self) -> bool:
        """Check if issue has any assignees."""
        return len(self.assignees) > 0

    @property
    def engagement_score(self) -> float:
        """Calculate engagement based on comments and reactions."""
        total_reactions = sum(self.reactions.values())
        return self.comments_count * 1.0 + total_reactions * 0.5

    @property
    def age_days(self) -> int:
        """Age of issue in days."""
        return (datetime.now(tz=self.updated_at.tzinfo) - self.created_at).days

    @classmethod
    def from_github_issue(cls, issue: Any, repo_name: str) -> "Issue":
        """Create Issue from PyGithub Issue object."""
        from github.Issue import Issue as GithubIssue

        if not isinstance(issue, GithubIssue):
            raise TypeError(f"Expected GithubIssue, got {type(issue)}")

        return cls(
            number=issue.number,
            title=issue.title,
            body=issue.body,
            author=issue.user.login if issue.user else "unknown",
            repository=repo_name,
            state=issue.state,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            labels=[label.name for label in issue.labels],
            assignees=[a.login for a in issue.assignees],
            comments_count=issue.comments,
            reactions={
                reaction.content: reaction.count for reaction in issue.get_reactions()
            }
            if hasattr(issue, "get_reactions")
            else {},
            category=IssueCategory.from_labels([label.name for label in issue.labels]),
        )
