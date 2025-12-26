"""Repos command for managing stored repositories."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

import typer
from rich import print as rprint
from rich.table import Table

if TYPE_CHECKING:
    pass

app = typer.Typer(help="Manage stored repositories")


@app.command()
def list(
    filter: str = typer.Option("all", help="Filter: all, approved, rejected, unanalyzed"),
    limit: int = typer.Option(50, help="Max results to show"),
) -> None:
    """List stored repositories.

    Shows repositories from the store with their analysis status.
    """
    from globallm.storage.repository_store import RepositoryStore  # noqa: PLC0415

    store = RepositoryStore()

    # Get repositories based on filter
    if filter == "approved":
        repos = store.get_approved()
        title = "Approved Repositories (worth_working_on=true)"
    elif filter == "rejected":
        repos = store.get_rejected()
        title = "Rejected Repositories (worth_working_on=false)"
    elif filter == "unanalyzed":
        repos = store.get_unanalyzed()
        title = "Unanalyzed Repositories"
    else:
        repos = store.load_repositories()
        title = "All Stored Repositories"

    if not repos:
        rprint("[yellow]No repositories found[/yellow]")
        return

    # Sort by stars (descending)
    repos.sort(key=lambda r: r.get("stars", 0), reverse=True)

    # Apply limit
    repos = repos[:limit]

    # Display table
    _display_table(repos, title, rprint)


def _display_table(repos: list[dict[str, Any]], title: str, rprint: Callable) -> None:
    """Display repositories in a table."""
    table = Table(title=title)
    table.add_column("Repository", style="cyan")
    table.add_column("Stars", style="yellow", justify="right")
    table.add_column("Language", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Health", style="green")
    table.add_column("Impact", style="blue")
    table.add_column("Reason", style="dim")

    for repo in repos:
        name = repo.get("name", "N/A")
        stars = repo.get("stars", 0)
        language = repo.get("language") or "N/A"

        worth_working_on = repo.get("worth_working_on")

        if worth_working_on is True:
            status = "[green]✓ Approved[/green]"
        elif worth_working_on is False:
            status = "[red]✗ Rejected[/red]"
        else:
            status = "[dim]Unanalyzed[/dim]"

        health = repo.get("health_score")
        impact = repo.get("impact_score")
        reason = repo.get("analysis_reason", "")

        health_str = f"{health:.0%}" if health is not None else "N/A"
        impact_str = f"{impact:.0%}" if impact is not None else "N/A"

        table.add_row(
            name,
            f"{stars:,}",
            language,
            status,
            health_str,
            impact_str,
            reason[:30] + "..." if len(reason) > 30 else reason,
        )

    rprint("")
    rprint(table)
    rprint(f"\n[dim]Showing {len(repos)} repositories[/dim]")


@app.command()
def show(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
) -> None:
    """Show detailed information about a stored repository."""
    from globallm.storage.repository_store import RepositoryStore  # noqa: PLC0415

    store = RepositoryStore()
    repo_data = store.get_repository(repo)

    if not repo_data:
        rprint(f"[red]Repository '{repo}' not found in store[/red]")
        raise typer.Exit(1)

    rprint(f"\n[bold cyan]Repository: {repo_data.get('name')}[/bold cyan]")

    # Basic info
    rprint("\n[bold]Basic Information[/bold]")
    rprint(f"  Stars: {repo_data.get('stars', 0):,}")
    rprint(f"  Forks: {repo_data.get('forks', 0):,}")
    rprint(f"  Open Issues: {repo_data.get('open_issues', 0):,}")
    rprint(f"  Watchers: {repo_data.get('watchers', 0):,}")
    rprint(f"  Language: {repo_data.get('language') or 'N/A'}")
    rprint(f"  Score: {repo_data.get('score', 0):.1f}")

    # Analysis info
    rprint("\n[bold]Analysis[/bold]")

    worth_working_on = repo_data.get("worth_working_on")
    if worth_working_on is True:
        rprint("  Status: [green]✓ Worth working on[/green]")
    elif worth_working_on is False:
        rprint("  Status: [red]✗ Not worth working on[/red]")
    else:
        rprint("  Status: [dim]Not analyzed yet[/dim]")

    health = repo_data.get("health_score")
    impact = repo_data.get("impact_score")
    if health is not None:
        rprint(f"  Health Score: {health:.1%}")
    if impact is not None:
        rprint(f"  Impact Score: {impact:.1%}")

    reason = repo_data.get("analysis_reason")
    if reason:
        rprint(f"  Reason: {reason}")

    analyzed_at = repo_data.get("analyzed_at")
    if analyzed_at:
        try:
            dt = datetime.fromisoformat(analyzed_at)
            rprint(f"  Analyzed: {dt.strftime('%Y-%m-%d %H:%M')}")
        except ValueError:
            rprint(f"  Analyzed: {analyzed_at}")


@app.command()
def remove(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
) -> None:
    """Remove a repository from the store."""
    from globallm.storage.repository_store import RepositoryStore  # noqa: PLC0415

    store = RepositoryStore()

    if not store.get_repository(repo):
        rprint(f"[red]Repository '{repo}' not found in store[/red]")
        raise typer.Exit(1)

    # Load all repos, remove the specified one
    repos = store.load_repositories()
    repos = [r for r in repos if r.get("name") != repo]

    # Save back
    from datetime import datetime

    store.save_repositories(repos, discovered_at=datetime.now())

    rprint(f"[green]Removed '{repo}' from store[/green]")
