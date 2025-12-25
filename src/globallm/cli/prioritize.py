"""Prioritize command."""

import json

import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console

from globallm.config.loader import load_config
from globallm.storage.repository_store import RepositoryStore

app = typer.Typer(help="Prioritize issues across repositories")


@app.command()
def prioritize(
    language: str = typer.Option(None, help="Filter by programming language"),
    top: int = typer.Option(20, help="Number of top issues to show"),
    min_priority: float = typer.Option(0.0, help="Minimum priority score"),
    export: str = typer.Option(None, help="Export to file (json, csv)"),
) -> None:
    """Prioritize issues across approved repositories.

    Reads repositories from the store that are marked as 'worth_working_on'.
    If no approved repositories exist, automatically runs discover to find candidates.
    """
    from globallm.issues.prioritizer import IssuePrioritizer
    from globallm.budget.budget_manager import BudgetManager
    from globallm.issues.fetcher import IssueFetcher
    from globallm.issues.analyzer import IssueAnalyzer
    from globallm.llm.claude import ClaudeLLM
    from github import Github
    import os

    token = os.getenv("GITHUB_TOKEN")
    github_client = Github(token)
    config = load_config()
    store = RepositoryStore()

    rprint("[bold cyan]Prioritizing issues...[/bold cyan]")

    # Get approved repositories from store
    approved_repos = store.get_approved()

    if not approved_repos:
        rprint("[yellow]No approved repositories found in store.[/yellow]")
        rprint("[dim]Please run discover and analyze some repositories first:[/dim]")
        rprint("  1. globallm discover --domain ai_ml --language python")
        rprint("  2. globallm analyze django/django")
        rprint("  3. globallm analyze psf/requests")
        raise typer.Exit(1)

    # Extract repo names
    repos = [r.get("name") for r in approved_repos if r.get("name")]

    if language:
        # Filter by language
        repos = [r for r in repos if _get_repo_language(store, r) == language]

    if not repos:
        rprint("[yellow]No repositories matching criteria[/yellow]")
        raise typer.Exit(1)

    rprint(f"[dim]Found {len(repos)} approved repositories[/dim]")

    # Initialize LLM and prioritizer
    llm = ClaudeLLM(
        model=config.llm_model,
        temperature=config.llm_temperature,
        max_tokens=config.llm_max_tokens,
    )
    analyzer = IssueAnalyzer(llm)
    prioritizer = IssuePrioritizer(analyzer)
    manager = BudgetManager()

    # Fetch and prioritize issues
    all_issues = []
    for repo in repos:
        if not manager.can_process_repo(repo):
            rprint(f"[yellow]Skipping {repo} - budget limit[/yellow]")
            continue

        fetcher = IssueFetcher(github_client)
        issues = fetcher.fetch_repo_issues(repo, state="open", limit=50)
        all_issues.extend(issues)

    if not all_issues:
        rprint("[yellow]No issues found[/yellow]")
        return

    # Calculate priority scores
    rprint(
        f"\n[yellow]Calculating priority scores for {len(all_issues)} issues...[/yellow]"
    )
    for issue in all_issues:
        priority = prioritizer.calculate_priority(issue)
        issue.priority_score = priority.overall

    # Filter and sort
    filtered_issues = [i for i in all_issues if i.priority_score >= min_priority]
    filtered_issues.sort(key=lambda i: i.priority_score, reverse=True)

    # Display results
    _display_results(filtered_issues, top, min_priority)

    # Export if requested
    if export == "json":
        _export_json(filtered_issues[:top])


def _get_repo_language(store: RepositoryStore, repo_name: str) -> str | None:
    """Get language for a repository from store."""
    repo = store.get_repository(repo_name)
    return repo.get("language") if repo else None


def _display_results(issues: list, top: int, min_priority: float) -> None:
    """Display prioritized issues in a table."""
    rprint(f"\n[green]Top {min(top, len(issues))} prioritized issues[/green]")

    if not issues:
        return

    console = Console()
    table = Table(title=f"Top Issues (Priority > {min_priority})")
    table.add_column("Repository", style="cyan")
    table.add_column("#", style="dim")
    table.add_column("Title", style="white")
    table.add_column("Category", style="yellow")
    table.add_column("Priority", style="green", justify="right")

    for issue in issues[:top]:
        table.add_row(
            issue.repository,
            str(issue.number),
            issue.title[:40] + "..." if len(issue.title) > 40 else issue.title,
            issue.category.value,
            f"{issue.priority_score:.1f}",
        )

    console.print(table)


def _export_json(issues: list) -> None:
    """Export issues to JSON file."""
    data = [
        {
            "repository": i.repository,
            "number": i.number,
            "title": i.title,
            "priority": i.priority_score,
            "category": i.category.value,
        }
        for i in issues
    ]
    with open("prioritized_issues.json", "w") as f:
        json.dump(data, f, indent=2)
    rprint("\n[green]Exported to prioritized_issues.json[/green]")
