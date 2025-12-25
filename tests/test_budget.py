"""Tests for budget management - green path tests."""

from datetime import datetime


from globallm.budget.budget_manager import BudgetManager, BudgetLimits
from globallm.budget.state import BudgetState, PerRepoBudget
from globallm.budget.token_estimator import TokenEstimator
from globallm.models.issue import Issue, IssueCategory


class TestTokenEstimator:
    """Test token estimator."""

    def test_estimate_text_tokens(self) -> None:
        """Test estimating tokens from text."""
        estimator = TokenEstimator()
        tokens = estimator.estimate_text_tokens("test" * 100)  # 400 chars
        assert tokens == 100  # 400 / 4

    def test_estimate_test_generation(self) -> None:
        """Test estimating test generation."""
        estimator = TokenEstimator()
        estimate = estimator.estimate_test_generation(files_count=3)
        assert estimate.operation == "test_generation"
        assert estimate.estimated_tokens == 800 * 3  # 2400


class TestBudgetState:
    """Test budget state."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = BudgetState()
        assert state.weekly_budget == 5_000_000
        assert state.weekly_used == 0

    def test_to_dict(self) -> None:
        """Test converting to dict."""
        state = BudgetState()
        state.weekly_used = 1000
        d = state.to_dict()
        assert d["weekly_used"] == 1000

    def test_weekly_remaining(self) -> None:
        """Test weekly remaining calculation."""
        state = BudgetState()
        state.weekly_used = 1000
        assert state.weekly_remaining == 4_999_000


class TestPerRepoBudget:
    """Test per-repo budget tracking."""

    def test_default_values(self) -> None:
        """Test default values."""
        budget = PerRepoBudget(repo="test/repo")
        assert budget.repo == "test/repo"
        assert budget.tokens_used == 0

    def test_to_dict(self) -> None:
        """Test converting to dict."""
        budget = PerRepoBudget(repo="test/repo", tokens_used=1000)
        d = budget.to_dict()
        assert d["tokens_used"] == 1000


class TestBudgetManager:
    """Test budget manager - green path tests."""

    def test_initialization(self) -> None:
        """Test manager initializes."""
        manager = BudgetManager()
        assert manager.state is not None
        assert manager.limits is not None
        assert manager.estimator is not None

    def test_custom_limits(self) -> None:
        """Test manager with custom limits."""
        limits = BudgetLimits(weekly_token_budget=100_000)
        manager = BudgetManager(limits=limits)
        assert manager.limits.weekly_token_budget == 100_000

    def test_can_process_repo(self) -> None:
        """Test can_process_repo check."""
        manager = BudgetManager(limits=BudgetLimits(max_tokens_per_repo=1000))
        # Use unique repo name to avoid conflicts with saved state
        unique_repo = "unique/test/repo"
        assert manager.can_process_repo(unique_repo, 500)

    def test_get_report(self) -> None:
        """Test getting budget report."""
        manager = BudgetManager()
        report = manager.get_report()
        assert report.weekly_budget >= 0
        assert report.weekly_used >= 0


class TestIssueModel:
    """Test Issue model."""

    def test_url_property(self) -> None:
        """Test URL generation."""
        issue = Issue(
            number=1,
            title="Test",
            body=None,
            author="test",
            repository="owner/repo",
            state="open",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            labels=[],
            assignees=[],
            comments_count=0,
            reactions={},
        )
        assert issue.url == "https://github.com/owner/repo/issues/1"

    def test_is_assigned_property(self) -> None:
        """Test is_assigned check."""
        issue = Issue(
            number=1,
            title="Test",
            body=None,
            author="test",
            repository="owner/repo",
            state="open",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            labels=[],
            assignees=["user1"],
            comments_count=0,
            reactions={},
        )
        assert issue.is_assigned is True

    def test_category_from_labels_bug(self) -> None:
        """Test category from bug label."""
        category = IssueCategory.from_labels(["bug"])
        assert category == IssueCategory.BUG

    def test_category_from_labels_feature(self) -> None:
        """Test category from feature label."""
        category = IssueCategory.from_labels(["feature"])
        assert category == IssueCategory.FEATURE

    def test_category_from_labels_security(self) -> None:
        """Test category from security label."""
        category = IssueCategory.from_labels(["security", "vulnerability"])
        assert category == IssueCategory.CRITICAL_SECURITY

    def test_category_from_labels_unknown(self) -> None:
        """Test category from unknown label."""
        category = IssueCategory.from_labels(["help wanted"])
        assert category == IssueCategory.UNKNOWN

    def test_category_multiplier(self) -> None:
        """Test category multiplier."""
        assert IssueCategory.CRITICAL_SECURITY.multiplier == 10.0
        assert IssueCategory.BUG.multiplier == 3.0
        assert IssueCategory.FEATURE.multiplier == 2.0
