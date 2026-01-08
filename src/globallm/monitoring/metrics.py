"""Metrics collection for GlobaLLM operations."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Callable

from globallm.logging_config import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Type of metric."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """A single metric."""

    name: str
    type: MetricType = MetricType.GAUGE
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    help_text: str = ""

    def __str__(self) -> str:
        """Format metric for display."""
        label_str = ""
        if self.labels:
            label_pairs = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ", ".join(label_pairs) + "}"
        return f"{self.name}{label_str} {self.value}"


@dataclass
class HistogramBucket:
    """A histogram bucket."""

    upper_bound: float
    count: int = 0


@dataclass
class Histogram(Metric):
    """A histogram metric with buckets."""

    buckets: list[HistogramBucket] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0

    def observe(self, value: float) -> None:
        """Observe a value."""
        self.count += 1
        self.sum += value

        # Find appropriate bucket
        for bucket in self.buckets:
            if value <= bucket.upper_bound:
                bucket.count += 1

    def __post_init__(self) -> None:
        """Initialize histogram type."""
        self.type = MetricType.HISTOGRAM


class MetricsRegistry:
    """Registry for metrics."""

    _instance = None
    _lock = Lock()

    def __new__(cls) -> "MetricsRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._metrics: dict[str, Metric] = {}
                    cls._instance._histograms: dict[str, Histogram] = {}
        return cls._instance

    def register(self, metric: Metric) -> None:
        """Register a metric."""
        key = self._make_key(metric.name, metric.labels)
        self._metrics[key] = metric

        if isinstance(metric, Histogram):
            self._histograms[key] = metric

    def get(self, name: str, labels: dict[str, str] | None = None) -> Metric | None:
        """Get a metric."""
        key = self._make_key(name, labels or {})
        return self._metrics.get(key)

    def increment(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, labels or {})
        metric = self._metrics.get(key)

        if metric is None:
            metric = Metric(
                name=name,
                type=MetricType.COUNTER,
                value=value,
                labels=labels or {},
            )
            self.register(metric)
        else:
            metric.value += value
            metric.timestamp = datetime.now()

    def set(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Set a gauge metric."""
        key = self._make_key(name, labels or {})
        metric = self._metrics.get(key)

        if metric is None:
            metric = Metric(
                name=name,
                type=MetricType.GAUGE,
                value=value,
                labels=labels or {},
            )
            self.register(metric)
        else:
            metric.value = value
            metric.timestamp = datetime.now()

    def observe(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Observe a value for a histogram."""
        key = self._make_key(name, labels or {})
        histogram = self._histograms.get(key)

        if histogram is None:
            histogram = Histogram(
                name=name,
                type=MetricType.HISTOGRAM,
                value=0.0,
                labels=labels or {},
                buckets=[
                    HistogramBucket(0.5),
                    HistogramBucket(1.0),
                    HistogramBucket(2.5),
                    HistogramBucket(5.0),
                    HistogramBucket(10.0),
                    HistogramBucket(float("inf")),
                ],
            )
            self.register(histogram)
        else:
            histogram.observe(value)

        histogram.timestamp = datetime.now()

    def get_all(self) -> list[Metric]:
        """Get all registered metrics."""
        return list(self._metrics.values())

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._histograms.clear()

    def _make_key(self, name: str, labels: dict[str, str]) -> str:
        """Make a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global registry
registry = MetricsRegistry()


class MetricsCollector:
    """Collect metrics for GlobaLLM operations."""

    def __init__(self, registry: MetricsRegistry = registry) -> None:
        """Initialize metrics collector.

        Args:
            registry: Metrics registry to use
        """
        self.registry = registry
        self._setup_default_metrics()

    def _setup_default_metrics(self) -> None:
        """Set up default metrics."""
        # Repository metrics
        self.registry.register(
            Metric(
                name="globallm_repositories_discovered",
                type=MetricType.COUNTER,
                help_text="Total repositories discovered",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_repositories_filtered",
                type=MetricType.COUNTER,
                help_text="Repositories filtered out",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_repositories_active",
                type=MetricType.GAUGE,
                help_text="Currently active repositories",
            )
        )

        # Issue metrics
        self.registry.register(
            Metric(
                name="globallm_issues_fetched",
                type=MetricType.COUNTER,
                help_text="Total issues fetched",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_issues_analyzed",
                type=MetricType.COUNTER,
                help_text="Total issues analyzed",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_issues_prioritized",
                type=MetricType.COUNTER,
                help_text="Issues prioritized for action",
            )
        )

        # Solution metrics
        self.registry.register(
            Metric(
                name="globallm_solutions_generated",
                type=MetricType.COUNTER,
                help_text="Solutions generated",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_solutions_submitted",
                type=MetricType.COUNTER,
                help_text="Solutions submitted as PRs",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_solutions_merged",
                type=MetricType.COUNTER,
                help_text="Solutions merged",
            )
        )

        # Budget metrics
        self.registry.register(
            Metric(
                name="globallm_tokens_used",
                type=MetricType.COUNTER,
                help_text="Total tokens used",
            )
        )
        self.registry.register(
            Metric(
                name="globallm_tokens_remaining",
                type=MetricType.GAUGE,
                help_text="Tokens remaining in budget",
            )
        )

        # Timing histograms
        self.registry.register(
            Histogram(
                name="globallm_issue_analysis_duration_seconds",
                help_text="Time spent analyzing issues",
            )
        )
        self.registry.register(
            Histogram(
                name="globallm_solution_generation_duration_seconds",
                help_text="Time spent generating solutions",
            )
        )

    # Repository metrics
    def increment_repositories_discovered(
        self, value: int = 1, language: str | None = None
    ) -> None:
        """Increment repositories discovered counter."""
        labels = {"language": language} if language else None
        self.registry.increment("globallm_repositories_discovered", value, labels)

    def increment_repositories_filtered(
        self, value: int = 1, reason: str | None = None
    ) -> None:
        """Increment repositories filtered counter."""
        labels = {"reason": reason} if reason else None
        self.registry.increment("globallm_repositories_filtered", value, labels)

    def set_active_repositories(self, count: int, language: str | None = None) -> None:
        """Set active repositories gauge."""
        labels = {"language": language} if language else None
        self.registry.set("globallm_repositories_active", count, labels)

    # Issue metrics
    def increment_issues_fetched(
        self, value: int = 1, repository: str | None = None
    ) -> None:
        """Increment issues fetched counter."""
        labels = {"repository": repository} if repository else None
        self.registry.increment("globallm_issues_fetched", value, labels)

    def increment_issues_analyzed(
        self, value: int = 1, category: str | None = None
    ) -> None:
        """Increment issues analyzed counter."""
        labels = {"category": category} if category else None
        self.registry.increment("globallm_issues_analyzed", value, labels)

    def increment_issues_prioritized(self, value: int = 1) -> None:
        """Increment issues prioritized counter."""
        self.registry.increment("globallm_issues_prioritized", value)

    # Solution metrics
    def increment_solutions_generated(
        self, value: int = 1, language: str | None = None
    ) -> None:
        """Increment solutions generated counter."""
        labels = {"language": language} if language else None
        self.registry.increment("globallm_solutions_generated", value, labels)

    def increment_solutions_submitted(self, value: int = 1) -> None:
        """Increment solutions submitted counter."""
        self.registry.increment("globallm_solutions_submitted", value)

    def increment_solutions_merged(self, value: int = 1) -> None:
        """Increment solutions merged counter."""
        self.registry.increment("globallm_solutions_merged", value)

    # Budget metrics
    def increment_tokens_used(self, value: int, operation: str | None = None) -> None:
        """Increment tokens used counter."""
        labels = {"operation": operation} if operation else None
        self.registry.increment("globallm_tokens_used", value, labels)

    def set_tokens_remaining(self, count: int) -> None:
        """Set tokens remaining gauge."""
        self.registry.set("globallm_tokens_remaining", count)

    # Timing metrics
    def observe_issue_analysis_duration(self, duration_seconds: float) -> None:
        """Observe issue analysis duration."""
        self.registry.observe(
            "globallm_issue_analysis_duration_seconds", duration_seconds
        )

    def observe_solution_generation_duration(self, duration_seconds: float) -> None:
        """Observe solution generation duration."""
        self.registry.observe(
            "globallm_solution_generation_duration_seconds", duration_seconds
        )

    # Utility methods
    def get_summary(self) -> dict[str, float]:
        """Get summary of all metrics."""
        summary = {}
        for metric in self.registry.get_all():
            if metric.name in summary:
                summary[metric.name] += metric.value
            else:
                summary[metric.name] = metric.value
        return summary

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        for metric in self.registry.get_all():
            # Add HELP if present
            if metric.help_text:
                lines.append(f"# HELP {metric.name} {metric.help_text}")
            lines.append(f"# TYPE {metric.name} {metric.type.value}")
            lines.append(str(metric))
        return "\n".join(lines)


def timed(collector: MetricsCollector | None = None, name: str | None = None):
    """Decorator to time a function and record to histogram.

    Args:
        collector: MetricsCollector to use
        name: Metric name (defaults to function_name_duration_seconds)

    Returns:
        Decorator function
    """
    import time
    import functools

    if collector is None:
        collector = MetricsCollector()

    def decorator(func: Callable) -> Callable:
        """Inner decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper that times the function."""
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                metric_name = name or f"{func.__name__}_duration_seconds"

                # Find the appropriate histogram metric
                if "analysis" in metric_name:
                    collector.observe_issue_analysis_duration(duration)
                elif "generation" in metric_name or "solution" in metric_name:
                    collector.observe_solution_generation_duration(duration)
                else:
                    # Generic timing
                    collector.registry.observe(metric_name, duration)

        return wrapper

    return decorator
