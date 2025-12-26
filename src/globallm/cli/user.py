"""User repository analysis command."""

import time
from typing import TYPE_CHECKING

import typer
from rich import print as rprint
from rich.table import Table

if TYPE_CHECKING:
    from globallm.scanner import RepoMetrics

app = typer.Typer(help="Analyze user repositories")


@app.command()
def analyze_user(
    username: str = typer.Argument(..., help="GitHub username to analyze"),
    min_stars: int = typer.Option(0, help="Minimum star count"),
    include_forks: bool = typer.Option(False, help="Include forked repositories"),
    max_results: int = typer.Option(100, help="Max results to return"),
    recommend: bool = typer.Option(True, help="Show keep/archive recommendations"),
) -> None:
    """Analyze all repositories owned by a user."""
    from globallm.scanner import GitHubScanner
    from globallm.github import create_github_client
    import os

    token = os.getenv("GITHUB_TOKEN")

    rprint(f"[bold cyan]Analyzing repositories for {username}...[/bold cyan]")
    rprint(f"  Min stars: {min_stars:,}")
    rprint(f"  Include forks: {include_forks}")

    scanner = GitHubScanner(create_github_client(token))

    start_time = time.time()
    results = scanner.analyze_user_repos(
        username=username,
        min_stars=min_stars,
        include_forks=include_forks,
        max_results=max_results,
    )
    duration = time.time() - start_time

    rprint(f"\n[green]Found {len(results)} repositories in {duration:.1f}s[/green]")

    if not results:
        rprint("[yellow]No repositories found matching criteria[/yellow]")
        return

    # Display results in a table
    table = Table(title=f"\n{username}'s Repositories (by impact score)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Repository", style="cyan")
    table.add_column("Stars", justify="right")
    table.add_column("Forks", justify="right")
    table.add_column("Issues", justify="right")
    table.add_column("Language")
    table.add_column("Score", justify="right")
    if recommend:
        table.add_column("Recommendation")

    for i, repo in enumerate(results, 1):
        recommendation = _get_recommendation(repo)
        rec_style = _get_recommendation_style(recommendation)

        table.add_row(
            str(i),
            repo.name,
            f"{repo.stars:,}",
            f"{repo.forks:,}",
            f"{repo.open_issues:,}",
            repo.language or "N/A",
            f"{repo.score:.1f}",
            f"[{rec_style}]{recommendation}[/{rec_style}]" if recommend else "",
        )

    rprint(table)

    if recommend:
        _print_summary(results, username)


def _get_recommendation(repo: RepoMetrics) -> str:
    """Get keep/archive recommendation for a repository."""
    # Archive if low impact
    if repo.stars < 100 and repo.forks < 10:
        return "Archive"
    # Keep if meaningful stars
    if repo.stars >= 1000:
        return "Keep"
    # Evaluate if medium impact
    if repo.stars >= 100:
        return "Evaluate"
    return "Archive"


def _get_recommendation_style(recommendation: str) -> str:
    """Get style for recommendation."""
    styles = {
        "Keep": "green",
        "Archive": "red",
        "Evaluate": "yellow",
    }
    return styles.get(recommendation, "white")


def _print_summary(results: list, username: str) -> None:
    """Print summary of recommendations."""
    keep = sum(1 for r in results if _get_recommendation(r) == "Keep")
    evaluate = sum(1 for r in results if _get_recommendation(r) == "Evaluate")
    archive = sum(1 for r in results if _get_recommendation(r) == "Archive")

    rprint(f"\n[bold]Summary for {username}:[/bold]")
    rprint(f"  [green]Keep: {keep}[/green] (high impact)")
    rprint(f"  [yellow]Evaluate: {evaluate}[/yellow] (medium impact)")
    rprint(f"  [red]Archive: {archive}[/red] (low impact)")
