"""Priority scoring models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PriorityContext:
    """Context for priority calculation."""

    # Weights for each dimension (sum should ideally be 1.0)
    health_weight: float = 1.0
    impact_weight: float = 2.0
    solvability_weight: float = 1.5
    urgency_weight: float = 0.5

    # Budget constraints
    max_tokens_per_repo: int = 100_000
    max_time_per_repo: int = 3600  # seconds
    max_issues_per_language: int = 50
    max_issues_per_repo: int = 5
    weekly_token_budget: int = 5_000_000

    # Current usage tracking
    tokens_used_weekly: int = 0
    tokens_per_repo: dict[str, int] = field(default_factory=dict)
    issues_per_language: dict[str, int] = field(default_factory=dict)

    def can_process_repo(self, repo: str, estimated_tokens: int) -> bool:
        """Check if repository can be processed given budget."""
        # Check per-repo limit
        repo_used = self.tokens_per_repo.get(repo, 0)
        if repo_used + estimated_tokens > self.max_tokens_per_repo:
            return False

        # Check weekly limit
        if self.tokens_used_weekly + estimated_tokens > self.weekly_token_budget:
            return False

        return True

    def record_usage(self, repo: str, language: str, tokens: int) -> None:
        """Record token usage."""
        self.tokens_used_weekly += tokens
        self.tokens_per_repo[repo] = self.tokens_per_repo.get(repo, 0) + tokens
        self.issues_per_language[language] = (
            self.issues_per_language.get(language, 0) + 1
        )

    def can_process_issue(self, repo: str, language: str) -> bool:
        """Check if issue can be processed given budget."""
        # Check per-repo issue limit
        repo_issues = sum(1 for r in self.tokens_per_repo if r == repo)  # Approximation
        if repo_issues >= self.max_issues_per_repo:
            return False

        # Check per-language issue limit
        lang_issues = self.issues_per_language.get(language, 0)
        if lang_issues >= self.max_issues_per_language:
            return False

        return True


@dataclass
class PriorityScore:
    """Priority score for an issue or repository."""

    overall: float
    health_score: float
    impact_score: float
    solvability_score: float
    urgency_score: float
    redundancy_penalty: float = 0.0

    # Breakdown for debugging/transparency
    health_components: dict[str, float] = field(default_factory=dict)
    impact_components: dict[str, float] = field(default_factory=dict)
    solvability_components: dict[str, float] = field(default_factory=dict)
    urgency_components: dict[str, float] = field(default_factory=dict)

    # Metadata
    calculated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall": self.overall,
            "health_score": self.health_score,
            "impact_score": self.impact_score,
            "solvability_score": self.solvability_score,
            "urgency_score": self.urgency_score,
            "redundancy_penalty": self.redundancy_penalty,
            "health_components": self.health_components,
            "impact_components": self.impact_components,
            "solvability_components": self.solvability_components,
            "urgency_components": self.urgency_components,
        }

    @classmethod
    def calculate(
        cls,
        health: float,
        impact: float,
        solvability: float,
        urgency: float,
        context: PriorityContext,
        redundancy_penalty: float = 0.0,
    ) -> "PriorityScore":
        """Calculate priority score from components."""
        overall = (
            context.health_weight * health
            + context.impact_weight * impact
            + context.solvability_weight * solvability
            + context.urgency_weight * urgency
            - redundancy_penalty
        )

        return cls(
            overall=overall,
            health_score=health,
            impact_score=impact,
            solvability_score=solvability,
            urgency_score=urgency,
            redundancy_penalty=redundancy_penalty,
        )
