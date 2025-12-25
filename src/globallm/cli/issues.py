"""Issues command."""

import typer
from rich import print as rprint

app = typer.Typer()


@app.command()
def issues(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
    state: str = typer.Option("open", help="Issue state (open, closed, all)"),
    limit: int = typer.Option(50, help="Max issues to fetch"),
    category: str = typer.Option(None, help="Filter by category"),
    sort: str = typer.Option("priority", help="Sort by (priority, created, updated)"),
) -> None:
    """Fetch and list issues from a repository."""
    from globallm.issues.fetcher import IssueFetcher
    from globallm.issues.analyzer import IssueAnalyzer
    from globallm.budget.budget_manager import BudgetManager
    from globallm.models.issue import IssueCategory
    import os

    token = os.getenv("GITHUB_TOKEN")

    rprint(f"[bold cyan]Fetching issues from {repo}...[/bold cyan]")

    # Check budget first
    manager = BudgetManager()
    if not manager.can_process_repo(repo):
        rprint(f"[red]Budget limit reached for {repo}[/red]")
        raise typer.Exit(1)

    # Fetch issues
    fetcher = IssueFetcher(token)
    issues = fetcher.fetch_issues(repo, state=state, limit=limit)

    # Analyze issues if we have an LLM configured
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"):
        analyzer = IssueAnalyzer()
        rprint("\n[yellow]Analyzing issues with LLM...[/yellow]")
        for issue in issues:
            analyzed = analyzer.analyze_issue(issue)
            issue.category = analyzed.category
            issue.severity = analyzed.severity
            issue.complexity = analyzed.complexity

    # Sort issues
    if sort == "priority":
        issues.sort(key=lambda i: i.priority_score, reverse=True)
    elif sort == "created":
        issues.sort(key=lambda i: i.created_at, reverse=True)
    elif sort == "updated":
        issues.sort(key=lambda i: i.updated_at, reverse=True)

    # Filter by category if specified
    if category:
        cat_enum = IssueCategory.from_string(category)
        issues = [i for i in issues if i.category == cat_enum]

    # Display results
    rprint(f"\n[green]Found {len(issues)} issues[/green]")

    if issues:
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(title=f"Issues from {repo}")
        table.add_column("#", style="dim")
        table.add_column("Title", style="cyan")
        table.add_column("Category", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Priority", style="green", justify="right")
        table.add_column("Created", style="dim")

        for issue in issues[:20]:
            table.add_row(
                str(issue.number),
                issue.title[:50] + "..." if len(issue.title) > 50 else issue.title,
                issue.category.value,
                issue.severity.value,
                f"{issue.priority_score:.1f}",
                issue.created_at.strftime("%Y-%m-%d"),
            )

        console.print(table)

    # Record token usage
    manager.record_usage(repo, "unknown", len(issues) * 100)
