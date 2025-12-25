"""Analyze command."""

import typer
from rich import print as rprint

app = typer.Typer()


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
    include_dependents: bool = typer.Option(False, help="Include dependent analysis"),
) -> None:
    """Analyze a single repository."""
    from globallm.scanner import GitHubScanner
    import os

    token = os.getenv("GITHUB_TOKEN")

    rprint(f"[bold cyan]Analyzing {repo}...[/bold cyan]")

    scanner = GitHubScanner(token)
    metrics = scanner.analyze_repo(repo)

    rprint("\n[bold]Repository Metrics[/bold]")
    rprint(f"  Stars: {metrics.stars:,}")
    rprint(f"  Forks: {metrics.forks:,}")
    rprint(f"  Open issues: {metrics.open_issues:,}")
    rprint(f"  Watchers: {metrics.watchers:,}")
    rprint(f"  Language: {metrics.language or 'N/A'}")
    rprint(f"  Score: {metrics.score:.1f}")
