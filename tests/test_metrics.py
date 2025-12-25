"""Tests for metrics collection."""

from globallm.monitoring.metrics import (
    Metric,
    MetricType,
    MetricsCollector,
    MetricsRegistry,
)


class TestMetric:
    """Test Metric dataclass."""

    def test_metric_creation(self) -> None:
        """Test creating a metric."""
        metric = Metric(
            name="test_metric",
            type=MetricType.COUNTER,
            value=10.0,
            help_text="Test metric",
        )
        assert metric.name == "test_metric"
        assert metric.type == MetricType.COUNTER
        assert metric.value == 10.0


class TestMetricsRegistry:
    """Test metrics registry."""

    def test_singleton(self) -> None:
        """Test registry is singleton."""
        registry1 = MetricsRegistry()
        registry2 = MetricsRegistry()
        assert registry1 is registry2

    def test_register_metric(self) -> None:
        """Test registering a metric."""
        registry = MetricsRegistry()
        metric = Metric(name="test", type=MetricType.COUNTER, value=1.0)
        registry.register(metric)
        assert registry.get("test") == metric

    def test_increment(self) -> None:
        """Test incrementing a counter."""
        registry = MetricsRegistry()
        registry.increment("test_counter", 2.0)
        metric = registry.get("test_counter")
        assert metric is not None
        assert metric.value == 2.0

    def test_set_gauge(self) -> None:
        """Test setting a gauge."""
        registry = MetricsRegistry()
        registry.set("test_gauge", 42.0)
        metric = registry.get("test_gauge")
        assert metric is not None
        assert metric.value == 42.0

    def test_get_all(self) -> None:
        """Test getting all metrics."""
        registry = MetricsRegistry()
        registry.increment("metric1", 1.0)
        registry.set("metric2", 2.0)

        all_metrics = registry.get_all()
        # Note: metrics from previous runs may exist
        assert len(all_metrics) >= 2


class TestMetricsCollector:
    """Test metrics collector."""

    def test_initialization(self) -> None:
        """Test collector initialization."""
        collector = MetricsCollector()
        assert collector.registry is not None

    def test_repository_metrics(self) -> None:
        """Test repository-related metrics."""
        collector = MetricsCollector()

        collector.increment_repositories_discovered(5, language="python")
        collector.set_active_repositories(3, language="python")

        summary = collector.get_summary()
        assert summary.get("globallm_repositories_discovered") >= 5
        assert summary.get("globallm_repositories_active") >= 3

    def test_issue_metrics(self) -> None:
        """Test issue-related metrics."""
        collector = MetricsCollector()

        collector.increment_issues_fetched(10)
        collector.increment_issues_analyzed(5, category="bug")
        collector.increment_issues_prioritized(2)

        summary = collector.get_summary()
        assert summary.get("globallm_issues_fetched") >= 10
        assert summary.get("globallm_issues_analyzed") >= 5
        assert summary.get("globallm_issues_prioritized") >= 2

    def test_solution_metrics(self) -> None:
        """Test solution-related metrics."""
        collector = MetricsCollector()

        collector.increment_solutions_generated(3, language="python")
        collector.increment_solutions_submitted(2)
        collector.increment_solutions_merged(1)

        summary = collector.get_summary()
        assert summary.get("globallm_solutions_generated") >= 3
        assert summary.get("globallm_solutions_submitted") >= 2
        assert summary.get("globallm_solutions_merged") >= 1

    def test_budget_metrics(self) -> None:
        """Test budget-related metrics."""
        collector = MetricsCollector()

        collector.increment_tokens_used(1000, operation="analysis")
        collector.set_tokens_remaining(9000)

        summary = collector.get_summary()
        assert summary.get("globallm_tokens_used") >= 1000
        assert summary.get("globallm_tokens_remaining") >= 9000

    def test_get_summary(self) -> None:
        """Test getting summary."""
        collector = MetricsCollector()
        collector.increment_repositories_discovered(5)

        summary = collector.get_summary()
        assert "globallm_repositories_discovered" in summary
        assert summary["globallm_repositories_discovered"] >= 5
