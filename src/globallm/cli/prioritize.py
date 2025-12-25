"""Prioritize command."""

import json

import typer
from rich import print as rprint

from globallm.config.loader import load_config

app = typer.Typer(help="Prioritize issues across repositories")


@app.command()
def prioritize(
    language: str = typer.Option(None, help="Filter by programming language"),
    top: int = typer.Option(20, help="Number of top issues to show"),
    min_priority: float = typer.Option(0.0, help="Minimum priority score"),
    export: str = typer.Option(None, help="Export to file (json, csv)"),
) -> None:
    """Prioritize issues across repositories."""
    from globallm.issues.prioritizer import IssuePrioritizer
    from globallm.budget.budget_manager import BudgetManager
    from globallm.issues.fetcher import IssueFetcher
    import os

    token = os.getenv("GITHUB_TOKEN")
    config = load_config()

    rprint("[bold cyan]Prioritizing issues...[/bold cyan]")

    prioritizer = IssuePrioritizer()
    manager = BudgetManager()

    # Get repositories from config or use defaults
    repos = (
        config.filters.target_repos if hasattr(config.filters, "target_repos") else []
    )

    if not repos:
        rprint(
            "[yellow]No repositories configured. Add some with config set filters.target_repos[/yellow]"
        )
        rprint(
            'Example: globallm config set filters.target_repos \'[["owner/repo1", "owner/repo2"]]\''
        )
        raise typer.Exit(1)

    # Fetch and prioritize issues
    all_issues = []
    for repo in repos:
        if not manager.can_process_repo(repo):
            rprint(f"[yellow]Skipping {repo} - budget limit[/yellow]")
            continue

        fetcher = IssueFetcher(token)
        issues = fetcher.fetch_issues(repo, state="open", limit=50)
        all_issues.extend(issues)

    # Calculate priority scores
    rprint(
        f"\n[yellow]Calculating priority scores for {len(all_issues)} issues...[/yellow]"
    )
    for issue in all_issues:
        score = prioritizer.calculate_priority_score(issue)
        issue.priority_score = score

    # Filter and sort
    filtered_issues = [i for i in all_issues if i.priority_score >= min_priority]
    filtered_issues.sort(key=lambda i: i.priority_score, reverse=True)

    # Display results
    rprint(f"\n[green]Top {min(top, len(filtered_issues))} prioritized issues[/green]")

    if filtered_issues:
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(title=f"Top Issues (Priority > {min_priority})")
        table.add_column("Repository", style="cyan")
        table.add_column("#", style="dim")
        table.add_column("Title", style="white")
        table.add_column("Category", style="yellow")
        table.add_column("Priority", style="green", justify="right")

        for issue in filtered_issues[:top]:
            table.add_row(
                issue.repository,
                str(issue.number),
                issue.title[:40] + "..." if len(issue.title) > 40 else issue.title,
                issue.category.value,
                f"{issue.priority_score:.1f}",
            )

        console.print(table)

        # Export if requested
        if export == "json":
            data = [
                {
                    "repository": i.repository,
                    "number": i.number,
                    "title": i.title,
                    "priority": i.priority_score,
                    "category": i.category.value,
                }
                for i in filtered_issues[:top]
            ]
            with open("prioritized_issues.json", "w") as f:
                json.dump(data, f, indent=2)
            rprint("\n[green]Exported to prioritized_issues.json[/green]")
