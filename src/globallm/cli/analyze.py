"""Analyze command."""

from datetime import datetime

import typer
from rich import print as rprint

from globallm.storage.repository_store import RepositoryStore

app = typer.Typer(help="Analyze repositories")


@app.command()
def analyze(
    repo: str | None = typer.Argument(None, help="Repository name (owner/repo), or analyze all unanalyzed repositories if not specified"),
    include_dependents: bool = typer.Option(False, help="Include dependent analysis"),
) -> None:
    """Analyze a repository or all unanalyzed repositories.

    The analysis automatically calculates whether the repository is worth working on
    and updates the repository store.
    """
    store = RepositoryStore()

    if repo is None:
        # Analyze all unanalyzed repositories
        unanalyzed = store.get_unanalyzed()
        if not unanalyzed:
            rprint("[dim]No unanalyzed repositories found.[/dim]")
            return

        rprint(f"[bold cyan]Found {len(unanalyzed)} unanalyzed repositories[/bold cyan]")
        for repo_dict in unanalyzed:
            repo_name = repo_dict.get("name")
            if repo_name:
                _analyze_single(repo_name, store, rprint)
    else:
        _analyze_single(repo, store, rprint)


def _analyze_single(repo: str, store: RepositoryStore, rprint) -> None:
    """Analyze a single repository."""
    from globallm.scanner import GitHubScanner
    import os

    token = os.getenv("GITHUB_TOKEN")
    rprint(f"[bold cyan]Analyzing {repo}...[/bold cyan]")

    scanner = GitHubScanner(token)
    metrics = scanner.analyze_repo(repo)

    # Calculate health and impact scores
    health_score = _calculate_health_score(metrics)
    impact_score = _calculate_impact_score(metrics)

    # Determine if worth working on
    worth_working_on = health_score > 0.5 and impact_score > 0.5

    # Generate analysis reason
    analysis_reason = _generate_analysis_reason(health_score, impact_score, worth_working_on)

    # Display results
    rprint("\n[bold]Repository Metrics[/bold]")
    rprint(f"  Stars: {metrics.stars:,}")
    rprint(f"  Forks: {metrics.forks:,}")
    rprint(f"  Open issues: {metrics.open_issues:,}")
    rprint(f"  Watchers: {metrics.watchers:,}")
    rprint(f"  Language: {metrics.language or 'N/A'}")
    rprint(f"  Score: {metrics.score:.1f}")

    # Display analysis results
    rprint("\n[bold]Analysis[/bold]")
    health_color = "green" if health_score > 0.5 else "yellow" if health_score > 0.3 else "red"
    impact_color = "green" if impact_score > 0.5 else "yellow" if impact_score > 0.3 else "red"
    rprint(f"  Health Score: [{health_color}]{health_score:.1%}[/{health_color}]")
    rprint(f"  Impact Score: [{impact_color}]{impact_score:.1%}[/{impact_color}]")

    if worth_working_on:
        rprint("  [green]✓ Worth working on[/green]")
    else:
        rprint("  [yellow]✗ Not recommended for contributions[/yellow]")

    rprint(f"  [dim]Reason: {analysis_reason}[/dim]")

    # Update repository store
    _update_store(store, repo, metrics, health_score, impact_score, worth_working_on, analysis_reason, rprint)


def _calculate_health_score(metrics) -> float:
    """Calculate health score from metrics (0-1)."""
    # Normalize score to 0-1 range (assuming max score around 100000)
    max_score = 100000
    normalized = min(metrics.score / max_score, 1.0)
    return normalized


def _calculate_impact_score(metrics) -> float:
    """Calculate impact score from metrics (0-1)."""
    # Impact based on stars, forks, watchers
    # Normalize each component
    stars_score = min(metrics.stars / 50000, 1.0)  # 50k stars = max
    forks_score = min(metrics.forks / 10000, 1.0)  # 10k forks = max
    watchers_score = min(metrics.watchers / 2000, 1.0)  # 2k watchers = max

    # Weighted average
    return stars_score * 0.5 + forks_score * 0.3 + watchers_score * 0.2


def _generate_analysis_reason(health: float, impact: float, worth_working_on: bool) -> str:
    """Generate human-readable analysis reason."""
    health_pct = f"{health:.0%}"
    impact_pct = f"{impact:.0%}"

    if worth_working_on:
        return f"High impact ({impact_pct}), good health ({health_pct})"
    else:
        if health < 0.3:
            return f"Poor health ({health_pct})"
        elif impact < 0.3:
            return f"Low impact ({impact_pct})"
        else:
            return f"Moderate health ({health_pct}), moderate impact ({impact_pct})"


def _update_store(
    store: RepositoryStore,
    repo_name: str,
    metrics,
    health_score: float,
    impact_score: float,
    worth_working_on: bool,
    analysis_reason: str,
    rprint,
) -> None:
    """Update the repository store with analysis results."""
    # Get existing repo data
    existing = store.get_repository(repo_name)

    if existing:
        # Update existing repo
        existing.update(metrics.to_dict())
        existing["health_score"] = health_score
        existing["impact_score"] = impact_score
        existing["worth_working_on"] = worth_working_on
        existing["analyzed_at"] = datetime.now().isoformat()
        existing["analysis_reason"] = analysis_reason
        store.add_or_update(existing)
    else:
        # Create new entry
        repo_dict = metrics.to_dict()
        repo_dict["health_score"] = health_score
        repo_dict["impact_score"] = impact_score
        repo_dict["worth_working_on"] = worth_working_on
        repo_dict["analyzed_at"] = datetime.now().isoformat()
        repo_dict["analysis_reason"] = analysis_reason
        store.add_or_update(repo_dict)

    rprint("\n[dim]→ Updated repository store[/dim]")
