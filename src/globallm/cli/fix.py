"""Fix command."""

import re

import typer
from rich import print as rprint

app = typer.Typer()


@app.command()
def fix(
    issue_url: str = typer.Argument(..., help="GitHub issue URL"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't actually create PR"),
    auto_merge: bool = typer.Option(True, help="Enable auto-merge if safe"),
    branch: str = typer.Option("main", help="Target branch"),
) -> None:
    """Analyze an issue and generate a fix."""
    from globallm.solution.engine import SolutionEngine
    from globallm.automation.pr_automation import PRAutomation
    from globallm.budget.budget_manager import BudgetManager
    import os

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        rprint("[red]GITHUB_TOKEN required for PR creation[/red]")
        raise typer.Exit(1)

    # Parse issue URL
    match = re.match(r"https://github.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
    if not match:
        rprint("[red]Invalid issue URL format[/red]")
        rprint("Expected: https://github.com/owner/repo/issues/123")
        raise typer.Exit(1)

    owner, repo_name, issue_number = match.groups()
    repo = f"{owner}/{repo_name}"

    rprint(f"[bold cyan]Analyzing issue #{issue_number} in {repo}...[/bold cyan]")

    # Check budget
    manager = BudgetManager()
    if not manager.can_process_repo(repo, 10000):
        rprint(f"[red]Insufficient budget for {repo}[/red]")
        raise typer.Exit(1)

    # Generate solution
    engine = SolutionEngine()
    rprint("\n[yellow]Phase 1: Analyzing issue...[/yellow]")
    solution = engine.generate_solution(
        repo_url=f"https://github.com/{repo}",
        issue_number=int(issue_number),
        dry_run=dry_run,
    )

    if not solution:
        rprint("[red]Failed to generate solution[/red]")
        raise typer.Exit(1)

    # Display solution summary
    rprint("\n[bold green]Solution Generated![/bold green]")
    rprint(f"  Description: {solution.description[:100]}...")
    rprint(f"  Complexity: {solution.complexity}/10")
    rprint(f"  Risk Level: {solution.risk_level.value.upper()}")
    rprint(f"  Files: {len(solution.patches)}")
    rprint(f"  Auto-merge: {'Yes' if solution.can_auto_merge else 'No'}")

    if dry_run:
        rprint("\n[yellow]Dry run mode - skipping PR creation[/yellow]")
        rprint("\n[bold]Proposed Changes:[/bold]")
        for patch in solution.patches:
            rprint(f"  - {patch.file_path}")
        return

    # Create PR
    rprint("\n[yellow]Phase 2: Creating PR...[/yellow]")
    pr_automation = PRAutomation(token)
    result = pr_automation.create_pr(
        solution,
        base_branch=branch,
        enable_auto_merge=auto_merge,
        dry_run=False,
    )

    if result.success:
        rprint("\n[green]PR created successfully![/green]")
        rprint(f"  PR #{result.pr_number}: {result.pr_url}")
        if result.auto_merge_enabled:
            rprint("  [green]Auto-merge enabled[/green]")
        if result.warnings:
            for warning in result.warnings:
                rprint(f"  [yellow]Warning: {warning}[/yellow]")
    else:
        rprint(f"\n[red]Failed to create PR: {result.error}[/red]")
        raise typer.Exit(1)
