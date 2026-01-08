"""CLI dashboard for GlobaLLM monitoring."""

from collections import defaultdict

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from globallm.logging_config import get_logger
from globallm.monitoring.metrics import MetricsCollector

logger = get_logger(__name__)


class Dashboard:
    """CLI dashboard for GlobaLLM status."""

    def __init__(
        self, console: Console | None = None, collector: MetricsCollector | None = None
    ) -> None:
        """Initialize dashboard.

        Args:
            console: Rich console instance
            collector: Metrics collector
        """
        self.console = console or Console()
        self.collector = collector or MetricsCollector()
        self._running = False

    def show_status(self) -> None:
        """Show current status dashboard."""
        layout = self._build_layout()
        self.console.print(layout)

    def _build_layout(self) -> Panel:
        """Build the dashboard layout."""
        summary = self.collector.get_summary()

        # Build budget section
        budget_text = self._format_budget_section(summary)

        # Build repositories section
        repos_text = self._format_repos_section(summary)

        # Build issues section
        issues_text = self._format_issues_section(summary)

        # Build solutions section
        solutions_text = self._format_solutions_section(summary)

        # Combine all sections
        content = f"""[bold cyan]GlobaLLM Status Dashboard[/bold cyan]
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{budget_text}

{repos_text}

{issues_text}

{solutions_text}
"""

        return Panel(content, title="GlobaLLM", border_style="cyan")

    def _format_budget_section(self, summary: dict[str, float]) -> str:
        """Format budget section."""
        used = summary.get("globallm_tokens_used", 0)
        remaining = summary.get("globallm_tokens_remaining", 5_000_000)

        # Calculate percentage
        total = remaining + used
        if total > 0:
            percent = (used / total) * 100
        else:
            percent = 0

        return f"""[bold]Budget[/bold]
  Tokens Used: {used:,} / {total:,} ({percent:.1f}%)
  [{"█" * int(percent / 5) * 2}{"░" * (40 - int(percent / 5) * 2)}]"""

    def _format_repos_section(self, summary: dict[str, float]) -> str:
        """Format repositories section."""
        discovered = int(summary.get("globallm_repositories_discovered", 0))
        filtered = int(summary.get("globallm_repositories_filtered", 0))
        active = int(summary.get("globallm_repositories_active", 0))

        return f"""[bold]Repositories[/bold]
  Discovered: {discovered:,}
  Filtered: {filtered:,}
  Active: {active:,}"""

    def _format_issues_section(self, summary: dict[str, float]) -> str:
        """Format issues section."""
        fetched = int(summary.get("globallm_issues_fetched", 0))
        analyzed = int(summary.get("globallm_issues_analyzed", 0))
        prioritized = int(summary.get("globallm_issues_prioritized", 0))

        return f"""[bold]Issues[/bold]
  Fetched: {fetched:,}
  Analyzed: {analyzed:,}
  Prioritized: {prioritized:,}"""

    def _format_solutions_section(self, summary: dict[str, float]) -> str:
        """Format solutions section."""
        generated = int(summary.get("globallm_solutions_generated", 0))
        submitted = int(summary.get("globallm_solutions_submitted", 0))
        merged = int(summary.get("globallm_solutions_merged", 0))

        # Calculate success rate
        if submitted > 0:
            success_rate = (merged / submitted) * 100
        else:
            success_rate = 0

        return f"""[bold]Solutions[/bold]
  Generated: {generated:,}
  Submitted: {submitted:,}
  Merged: {merged:,} ({success_rate:.1f}% success rate)"""


class RepositoryTable:
    """Table for displaying repository status."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize repository table.

        Args:
            console: Rich console instance
        """
        self.console = console or Console()

    def show(
        self,
        repos: list[dict[str, any]],
        sort_by: str = "impact",
        limit: int = 20,
    ) -> None:
        """Show repository table.

        Args:
            repos: List of repository dicts
            sort_by: Field to sort by
            limit: Max rows to display
        """
        table = Table(
            title="Repositories", show_header=True, header_style="bold magenta"
        )

        table.add_column("Repository", style="cyan", width=40)
        table.add_column("Stars", justify="right", style="yellow")
        table.add_column("Issues", justify="right", style="green")
        table.add_column("PRs", justify="right", style="green")
        table.add_column("Merged", justify="right", style="green")
        table.add_column("Impact", justify="right", style="blue")
        table.add_column("Health", justify="right", style="magenta")

        # Sort and limit
        if sort_by:
            repos = sorted(
                repos,
                key=lambda r: r.get(sort_by, 0),
                reverse=True,
            )

        for repo in repos[:limit]:
            table.add_row(
                repo.get("name", "unknown"),
                f"{repo.get('stars', 0):,}",
                str(repo.get("issues", 0)),
                str(repo.get("prs", 0)),
                str(repo.get("merged", 0)),
                f"{repo.get('impact', 0):.1f}",
                f"{repo.get('health', 0):.1f}",
            )

        self.console.print(table)


class ProgressTracker:
    """Track progress of operations."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize progress tracker.

        Args:
            console: Rich console instance
        """
        self.console = console or Console()
        self.progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console,
        )

    def __enter__(self) -> "ProgressTracker":
        """Enter context manager."""
        self.progress.__enter__()
        return self

    def __exit__(self, *args) -> None:
        """Exit context manager."""
        self.progress.__exit__(*args)

    def add_task(self, description: str, total: int = 100, completed: int = 0) -> int:
        """Add a task to track.

        Args:
            description: Task description
            total: Total work
            completed: Completed work

        Returns:
            Task ID
        """
        return self.progress.add_task(description, total=total, completed=completed)

    def update(self, task_id: int, advance: int | None = None, **kwargs) -> None:
        """Update task progress.

        Args:
            task_id: Task ID
            advance: Amount to advance
            **kwargs: Additional arguments to pass to Progress.update
        """
        if advance is not None:
            kwargs["advance"] = advance
        self.progress.update(task_id, **kwargs)


class ReportGenerator:
    """Generate reports from metrics."""

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        """Initialize report generator.

        Args:
            collector: Metrics collector
        """
        self.collector = collector or MetricsCollector()

    def generate_daily_report(self) -> str:
        """Generate daily report.

        Returns:
            Report text
        """
        summary = self.collector.get_summary()

        lines = [
            "# GlobaLLM Daily Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
        ]

        # Budget
        used = summary.get("globallm_tokens_used", 0)
        lines.append(f"- **Tokens Used**: {used:,}")

        # Repositories
        discovered = summary.get("globallm_repositories_discovered", 0)
        active = summary.get("globallm_repositories_active", 0)
        lines.append(f"- **Repositories Discovered**: {int(discovered):,}")
        lines.append(f"- **Active Repositories**: {int(active):,}")

        # Issues
        fetched = summary.get("globallm_issues_fetched", 0)
        analyzed = summary.get("globallm_issues_analyzed", 0)
        prioritized = summary.get("globallm_issues_prioritized", 0)
        lines.append(f"- **Issues Fetched**: {int(fetched):,}")
        lines.append(f"- **Issues Analyzed**: {int(analyzed):,}")
        lines.append(f"- **Issues Prioritized**: {int(prioritized):,}")

        # Solutions
        generated = summary.get("globallm_solutions_generated", 0)
        submitted = summary.get("globallm_solutions_submitted", 0)
        merged = summary.get("globallm_solutions_merged", 0)
        lines.append(f"- **Solutions Generated**: {int(generated):,}")
        lines.append(f"- **Solutions Submitted**: {int(submitted):,}")
        lines.append(f"- **Solutions Merged**: {int(merged):,}")

        if submitted > 0:
            success_rate = (merged / submitted) * 100
            lines.append(f"- **Success Rate**: {success_rate:.1f}%")

        return "\n".join(lines)

    def generate_language_report(self) -> str:
        """Generate per-language report.

        Returns:
            Report text
        """
        lines = [
            "# GlobaLLM Language Breakdown",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## By Language",
            "",
        ]

        # Group by language
        language_stats = defaultdict(lambda: defaultdict(float))

        for metric in self.collector.registry.get_all():
            if "language" in metric.labels:
                lang = metric.labels["language"]
                language_stats[lang][metric.name] += metric.value

        # Sort by total activity
        sorted_languages = sorted(
            language_stats.items(),
            key=lambda x: sum(v for v in x[1].values()),
            reverse=True,
        )

        for lang, stats in sorted_languages:
            active = int(stats.get("globallm_repositories_active", 0))
            solutions = int(stats.get("globallm_solutions_generated", 0))

            lines.append(f"### {lang.upper()}")
            lines.append(f"- Active Repos: {active:,}")
            lines.append(f"- Solutions: {solutions:,}")
            lines.append("")

        return "\n".join(lines)

    def export_metrics_json(self) -> str:
        """Export metrics as JSON.

        Returns:
            JSON string
        """
        import json

        metrics_data = []
        for metric in self.collector.registry.get_all():
            metrics_data.append(
                {
                    "name": metric.name,
                    "type": metric.type.value,
                    "value": metric.value,
                    "labels": metric.labels,
                    "timestamp": metric.timestamp.isoformat(),
                }
            )

        return json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "metrics": metrics_data,
            },
            indent=2,
        )
