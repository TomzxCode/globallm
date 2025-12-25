"""Budget management and enforcement."""

from dataclasses import dataclass

from globallm.budget.state import BudgetState
from globallm.budget.token_estimator import TokenEstimator, OperationEstimate
from globallm.logging_config import get_logger
from globallm.models.issue import Issue

logger = get_logger(__name__)


@dataclass
class BudgetLimits:
    """Configurable budget limits."""

    max_tokens_per_repo: int = 100_000
    max_time_per_repo: int = 3600  # seconds
    max_issues_per_language: int = 50
    max_issues_per_repo: int = 5
    weekly_token_budget: int = 5_000_000


@dataclass
class BudgetReport:
    """Report on current budget status."""

    weekly_budget: int
    weekly_used: int
    weekly_remaining: int
    weekly_percent: float

    per_repo: dict[str, dict[str, int]]
    per_language: dict[str, dict[str, int]]

    total_tokens: int
    total_issues: int
    total_prs: int

    def to_dict(self) -> dict:
        return {
            "weekly": {
                "budget": self.weekly_budget,
                "used": self.weekly_used,
                "remaining": self.weekly_remaining,
                "percent_used": round(self.weekly_percent, 1),
            },
            "per_repo": self.per_repo,
            "per_language": self.per_language,
            "totals": {
                "tokens": self.total_tokens,
                "issues": self.total_issues,
                "prs": self.total_prs,
            },
        }


class BudgetManager:
    """Manage and enforce budget constraints."""

    def __init__(
        self,
        limits: BudgetLimits | None = None,
        state: BudgetState | None = None,
        estimator: TokenEstimator | None = None,
    ) -> None:
        """Initialize budget manager.

        Args:
            limits: Budget limits configuration
            state: Pre-loaded budget state (loads from disk if None)
            estimator: Token estimator (creates default if None)
        """
        self.limits = limits or BudgetLimits()
        self.state = state or BudgetState.load()
        self.estimator = estimator or TokenEstimator()

        # Sync limits with state
        if self.state.weekly_budget != self.limits.weekly_token_budget:
            self.state.weekly_budget = self.limits.weekly_token_budget
            self.state.save()

    def can_process_repo(self, repo: str, estimated_tokens: int = 0) -> bool:
        """Check if repository can be processed given budget.

        Args:
            repo: Repository name
            estimated_tokens: Estimated tokens for the operation

        Returns:
            True if within budget
        """
        # Check per-repo token limit
        repo_tokens = self.state.get_repo_tokens(repo)
        if repo_tokens + estimated_tokens > self.limits.max_tokens_per_repo:
            logger.info(
                "repo_token_limit_exceeded",
                repo=repo,
                current=repo_tokens,
                estimated=estimated_tokens,
                limit=self.limits.max_tokens_per_repo,
            )
            return False

        # Check per-repo issue limit
        repo_issues = self.state.get_repo_issues(repo)
        if repo_issues >= self.limits.max_issues_per_repo:
            logger.info(
                "repo_issue_limit_exceeded",
                repo=repo,
                current=repo_issues,
                limit=self.limits.max_issues_per_repo,
            )
            return False

        # Check weekly budget
        if not self._check_weekly_budget(estimated_tokens):
            return False

        return True

    def can_process_issue(
        self, repo: str, language: str, estimated_tokens: int = 0
    ) -> bool:
        """Check if issue can be processed given budget.

        Args:
            repo: Repository name
            language: Programming language
            estimated_tokens: Estimated tokens for the operation

        Returns:
            True if within budget
        """
        # Check per-language issue limit
        lang_issues = self.state.get_language_issues(language)
        if lang_issues >= self.limits.max_issues_per_language:
            logger.info(
                "language_issue_limit_exceeded",
                language=language,
                current=lang_issues,
                limit=self.limits.max_issues_per_language,
            )
            return False

        # Check repo limits
        return self.can_process_repo(repo, estimated_tokens)

    def can_process_batch(self, issues: list[Issue], language: str) -> tuple[bool, int]:
        """Check if a batch of issues can be processed.

        Args:
            issues: List of issues to process
            language: Programming language

        Returns:
            (can_process, count) tuple with result and how many can be done
        """
        count = 0

        for issue in issues:
            estimate = self.estimator.estimate_full_solution(issue)
            if not self.can_process_issue(
                issue.repository, language, estimate.estimated_tokens
            ):
                break
            count += 1

        return (count > 0, count)

    def record_usage(
        self,
        repo: str,
        language: str,
        tokens: int,
        operation: str = "unknown",
    ) -> None:
        """Record token usage.

        Args:
            repo: Repository name
            language: Programming language
            tokens: Tokens used
            operation: Operation type for logging
        """
        self.state.record_repo_tokens(repo, tokens)
        self.state.record_language_tokens(language, tokens)

        logger.debug(
            "tokens_recorded",
            repo=repo,
            language=language,
            tokens=tokens,
            operation=operation,
        )

        # Save state
        self.state.save()

    def record_issue_processed(self, repo: str, language: str) -> None:
        """Record that an issue was processed.

        Args:
            repo: Repository name
            language: Programming language
        """
        self.state.record_issue_processed(repo, language)
        self.state.save()

    def record_pr_created(self) -> None:
        """Record that a PR was created."""
        self.state.record_pr_created()
        self.state.save()

    def _check_weekly_budget(self, estimated_tokens: int) -> bool:
        """Check if weekly budget allows operation.

        Args:
            estimated_tokens: Tokens to be used

        Returns:
            True if within weekly budget
        """
        self.state.check_and_reset_week()

        if self.state.weekly_used + estimated_tokens > self.limits.weekly_token_budget:
            logger.info(
                "weekly_budget_exceeded",
                current=self.state.weekly_used,
                estimated=estimated_tokens,
                limit=self.limits.weekly_token_budget,
            )
            return False

        return True

    def get_report(self) -> BudgetReport:
        """Generate budget status report.

        Returns:
            BudgetReport with current status
        """
        self.state.check_and_reset_week()

        per_repo = {}
        for repo, budget in self.state.per_repo.items():
            per_repo[repo] = {
                "tokens": budget.tokens_used,
                "issues": budget.issues_processed,
            }

        per_language = {}
        for lang, budget in self.state.per_language.items():
            per_language[lang] = {
                "tokens": budget.tokens_used,
                "issues": budget.issues_processed,
            }

        return BudgetReport(
            weekly_budget=self.state.weekly_budget,
            weekly_used=self.state.weekly_used,
            weekly_remaining=self.state.weekly_remaining,
            weekly_percent=self.state.weekly_used_percent,
            per_repo=per_repo,
            per_language=per_language,
            total_tokens=self.state.total_tokens_used,
            total_issues=self.state.total_issues_processed,
            total_prs=self.state.total_prs_created,
        )

    def reset_weekly(self) -> None:
        """Reset weekly budget tracking."""
        logger.info("resetting_weekly_budget")
        self.state.weekly_used = 0
        year, week = self.state.current_week
        self.state.year = year
        self.state.week_number = week
        self.state.save()

    def reset_repo(self, repo: str) -> None:
        """Reset tracking for a specific repository.

        Args:
            repo: Repository name to reset
        """
        if repo in self.state.per_repo:
            del self.state.per_repo[repo]
            self.state.save()
            logger.info("reset_repo_budget", repo=repo)

    def reset_language(self, language: str) -> None:
        """Reset tracking for a specific language.

        Args:
            language: Language to reset
        """
        if language in self.state.per_language:
            del self.state.per_language[language]
            self.state.save()
            logger.info("reset_language_budget", language=language)

    def get_remaining_for_repo(self, repo: str) -> int:
        """Get remaining token budget for a repository.

        Args:
            repo: Repository name

        Returns:
            Remaining tokens
        """
        used = self.state.get_repo_tokens(repo)
        return max(0, self.limits.max_tokens_per_repo - used)

    def get_remaining_for_language(self, language: str) -> int:
        """Get remaining issue budget for a language.

        Args:
            language: Programming language

        Returns:
            Remaining issues that can be processed
        """
        used = self.state.get_language_issues(language)
        return max(0, self.limits.max_issues_per_language - used)

    def estimate_cost(self, issue: Issue, complexity: int = 5) -> OperationEstimate:
        """Estimate cost to process an issue.

        Args:
            issue: Issue to process
            complexity: Estimated complexity (1-10)

        Returns:
            OperationEstimate with cost details
        """
        return self.estimator.estimate_full_solution(issue, complexity)
