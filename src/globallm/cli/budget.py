"""Budget subcommands."""

import typer
from rich import print as rprint

app = typer.Typer()


@app.command()
def show() -> None:
    """Show current budget status."""
    from globallm.budget.budget_manager import BudgetManager

    manager = BudgetManager()
    report = manager.get_report()

    rprint("[bold cyan]Budget Status[/bold cyan]")
    rprint("\n[bold]Weekly Budget:[/bold]")
    rprint(f"  Budget: {report.weekly_budget:,} tokens")
    rprint(f"  Used: {report.weekly_used:,} tokens ({report.weekly_percent:.1f}%)")
    rprint(f"  Remaining: {report.weekly_remaining:,} tokens")

    rprint("\n[bold]Totals:[/bold]")
    rprint(f"  Total tokens: {report.total_tokens:,}")
    rprint(f"  Issues processed: {report.total_issues}")
    rprint(f"  PRs created: {report.total_prs}")

    if report.per_repo:
        rprint("\n[bold]Top Repositories by Token Usage:[/bold]")
        sorted_repos = sorted(
            report.per_repo.items(), key=lambda x: x[1]["tokens"], reverse=True
        )[:10]
        for repo, stats in sorted_repos:
            rprint(f"  {repo}: {stats['tokens']:,} tokens, {stats['issues']} issues")

    if report.per_language:
        rprint("\n[bold]By Language:[/bold]")
        for lang, stats in sorted(report.per_language.items()):
            rprint(f"  {lang}: {stats['tokens']:,} tokens, {stats['issues']} issues")


@app.command()
def reset(
    weekly: bool = typer.Option(False, "--weekly", help="Reset weekly budget"),
    repo: str = typer.Option(None, "--repo", help="Reset specific repository"),
    language: str = typer.Option(None, "--language", help="Reset specific language"),
) -> None:
    """Reset budget tracking."""
    from globallm.budget.budget_manager import BudgetManager

    manager = BudgetManager()

    if weekly:
        manager.reset_weekly()
        rprint("[green]Weekly budget reset[/green]")
    elif repo:
        manager.reset_repo(repo)
        rprint(f"[green]Reset budget for {repo}[/green]")
    elif language:
        manager.reset_language(language)
        rprint(f"[green]Reset budget for {language}[/green]")
    else:
        rprint(
            "[yellow]No reset option specified. Use --weekly, --repo, or --language[/yellow]"
        )
        raise typer.Exit(1)
