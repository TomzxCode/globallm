"""Status command."""

import typer
from rich import print as rprint

app = typer.Typer(help="Show system status and statistics")


@app.command()
def status(
    export: str = typer.Option(None, help="Export format (json)"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Show dashboard"),
) -> None:
    """Show system status and statistics."""
    from globallm.config.loader import load_config  # noqa: PLC0415

    config = load_config()

    if dashboard:
        _show_dashboard(config)
        return

    rprint("[bold cyan]GlobaLLM Status[/bold cyan]")
    rprint(f"  Log level: {config.log_level}")
    rprint(f"  LLM provider: {config.llm_provider}")
    rprint(f"  LLM model: {config.llm_model}")

    rprint("\n[bold]Filters[/bold]")
    rprint(f"  Min stars: {config.filters.min_stars:,}")
    rprint(f"  Min dependents: {config.filters.min_dependents:,}")
    rprint(f"  Min health score: {config.filters.min_health_score}")

    rprint("\n[bold]Budget[/bold]")
    rprint(f"  Weekly token budget: {config.budget.weekly_token_budget:,}")
    rprint(f"  Max tokens per repo: {config.budget.max_tokens_per_repo:,}")


def _show_dashboard(config) -> None:
    """Show the status dashboard."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    # Header panel
    header = Panel(
        "[bold cyan]GlobaLLM Status Dashboard[/bold cyan]\n"
        f"Budget: 0 / {config.budget.weekly_token_budget:,} tokens (0%)",
        title="Status",
    )
    console.print(header)

    # Repository table
    table = Table(title="Active Repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Issues", justify="right")
    table.add_column("PRs", justify="right")
    table.add_column("Merged", justify="right")
    table.add_column("Impact", justify="right")

    # Add placeholder row
    table.add_row("No active repositories", "0", "0", "0", "0.0")

    console.print(table)

    # Language breakdown
    rprint("\n[bold]Language Breakdown:[/bold]")
    rprint("  Python:      [blue]░░░░░░░░░░░░░░░░░░░░░[/blue] 0 PRs")
    rprint("  JavaScript:  [blue]░░░░░░░░░░░░░░░░░░░░░[/blue] 0 PRs")
