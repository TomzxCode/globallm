"""Token usage estimation for operations."""

from dataclasses import dataclass

from globallm.models.issue import Issue
from globallm.models.solution import Solution

# Token costs for various operations (approximate)
CATEGORIZATION_TOKENS = 500
COMPLEXITY_ESTIMATION_TOKENS = 300
CODE_GENERATION_BASE_TOKENS = 1000
CODE_GENERATION_PER_COMPLEXITY_TOKENS = 500
TEST_GENERATION_TOKENS = 800
CODE_REVIEW_TOKENS = 400
PR_CREATION_TOKENS = 200

# Character to token ratio (rough approximation: ~4 chars per token)
CHARS_PER_TOKEN = 4


@dataclass
class OperationEstimate:
    """Token usage estimate for an operation."""

    operation: str
    estimated_tokens: int
    estimated_time_seconds: int = 0

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "estimated_tokens": self.estimated_tokens,
            "estimated_time_seconds": self.estimated_time_seconds,
        }


class TokenEstimator:
    """Estimate token usage for various operations."""

    def __init__(self, tokens_per_second: int = 50) -> None:
        """Initialize estimator.

        Args:
            tokens_per_second: Processing speed for time estimation
        """
        self.tokens_per_second = tokens_per_second

    def estimate_text_tokens(self, text: str) -> int:
        """Estimate tokens for a piece of text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // CHARS_PER_TOKEN

    def estimate_categorization(self, issue: Issue) -> OperationEstimate:
        """Estimate tokens for issue categorization.

        Args:
            issue: Issue to categorize

        Returns:
            OperationEstimate with token estimate
        """
        # Base cost + content length
        content_tokens = self.estimate_text_tokens(issue.title)
        if issue.body:
            content_tokens += self.estimate_text_tokens(issue.body)

        total = CATEGORIZATION_TOKENS + content_tokens
        return OperationEstimate(
            operation="categorization",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_complexity(self, issue: Issue) -> OperationEstimate:
        """Estimate tokens for complexity estimation.

        Args:
            issue: Issue to analyze

        Returns:
            OperationEstimate with token estimate
        """
        content_tokens = self.estimate_text_tokens(issue.title)
        if issue.body:
            content_tokens += self.estimate_text_tokens(issue.body)

        total = COMPLEXITY_ESTIMATION_TOKENS + content_tokens
        return OperationEstimate(
            operation="complexity_estimation",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_code_generation(
        self, issue: Issue, complexity: int = 5
    ) -> OperationEstimate:
        """Estimate tokens for code generation.

        Args:
            issue: Issue to generate code for
            complexity: Estimated complexity (1-10)

        Returns:
            OperationEstimate with token estimate
        """
        # Base cost + complexity scaling
        complexity_cost = complexity * CODE_GENERATION_PER_COMPLEXITY_TOKENS

        # Add issue context
        context_tokens = self.estimate_text_tokens(issue.title)
        if issue.body:
            context_tokens += self.estimate_text_tokens(issue.body)

        total = CODE_GENERATION_BASE_TOKENS + complexity_cost + context_tokens

        return OperationEstimate(
            operation="code_generation",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_test_generation(self, files_count: int = 1) -> OperationEstimate:
        """Estimate tokens for test generation.

        Args:
            files_count: Number of test files to generate

        Returns:
            OperationEstimate with token estimate
        """
        total = TEST_GENERATION_TOKENS * files_count
        return OperationEstimate(
            operation="test_generation",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_code_review(self, solution: Solution) -> OperationEstimate:
        """Estimate tokens for code review/validation.

        Args:
            solution: Solution to review

        Returns:
            OperationEstimate with token estimate
        """
        # Count lines changed
        lines_changed = solution.total_lines_changed

        # Rough estimate: 1 token per 4 lines of code
        code_tokens = lines_changed // 4

        total = CODE_REVIEW_TOKENS + code_tokens
        return OperationEstimate(
            operation="code_review",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_full_solution(
        self, issue: Issue, complexity: int = 5
    ) -> OperationEstimate:
        """Estimate tokens for complete solution generation.

        Includes categorization, code generation, test generation, and review.

        Args:
            issue: Issue to solve
            complexity: Estimated complexity

        Returns:
            OperationEstimate with total token estimate
        """
        categorization = self.estimate_categorization(issue)
        code_gen = self.estimate_code_generation(issue, complexity)
        test_gen = self.estimate_test_generation()
        review = self.estimate_code_review(
            Solution(
                issue_url=issue.url,
                repository=issue.repository,
                issue_number=issue.number,
                issue_title=issue.title,
                description="",
                patches=[],
                complexity=complexity,
            )
        )

        total = (
            categorization.estimated_tokens
            + code_gen.estimated_tokens
            + test_gen.estimated_tokens
            + review.estimated_tokens
            + PR_CREATION_TOKENS
        )

        return OperationEstimate(
            operation="full_solution",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def estimate_batch(
        self, issues: list[Issue], complexities: dict[int, int] | None = None
    ) -> OperationEstimate:
        """Estimate tokens for processing multiple issues.

        Args:
            issues: List of issues to process
            complexities: Optional dict mapping issue index to complexity

        Returns:
            OperationEstimate with total estimate
        """
        if complexities is None:
            complexities = {}

        total = 0
        for i, issue in enumerate(issues):
            complexity = complexities.get(i, 5)
            estimate = self.estimate_full_solution(issue, complexity)
            total += estimate.estimated_tokens

        return OperationEstimate(
            operation="batch_solution",
            estimated_tokens=total,
            estimated_time_seconds=self._estimate_time(total),
        )

    def _estimate_time(self, tokens: int) -> int:
        """Estimate processing time in seconds.

        Args:
            tokens: Number of tokens to process

        Returns:
            Estimated seconds
        """
        return max(1, tokens // self.tokens_per_second)
