"""Fix command."""

import re
import os

import typer
from rich import print as rprint
from github import Github

app = typer.Typer(help="Analyze an issue and generate a fix")


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
    from globallm.issues.fetcher import IssueFetcher
    from globallm.issues.analyzer import IssueAnalyzer
    from globallm.solution.code_generator import CodeGenerator
    from globallm.llm.claude import ClaudeLLM

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

    # Check for LLM API key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        rprint("[red]ANTHROPIC_API_KEY required for solution generation[/red]")
        raise typer.Exit(1)

    # Initialize LLM and components
    llm = ClaudeLLM()
    analyzer = IssueAnalyzer(llm)
    code_generator = CodeGenerator(llm)
    engine = SolutionEngine(analyzer=analyzer, code_generator=code_generator)

    # Fetch the issue
    github_client = Github(token)
    fetcher = IssueFetcher(github_client)
    issue = fetcher.fetch_single_issue(repo, int(issue_number))

    rprint("\n[yellow]Phase 1: Analyzing issue...[/yellow]")
    result = engine.generate_solution(issue=issue)

    if not result.success or not result.solution:
        rprint("[red]Failed to generate solution[/red]")
        if result.error:
            rprint(f"[red]Error: {result.error}[/red]")
        raise typer.Exit(1)

    solution = result.solution

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
    pr_result = pr_automation.create_pr(
        solution,
        base_branch=branch,
        enable_auto_merge=auto_merge,
        dry_run=False,
    )

    if pr_result.success:
        rprint("\n[green]PR created successfully![/green]")
        rprint(f"  PR #{pr_result.pr_number}: {pr_result.pr_url}")
        if pr_result.auto_merge_enabled:
            rprint("  [green]Auto-merge enabled[/green]")
        if pr_result.warnings:
            for warning in pr_result.warnings:
                rprint(f"  [yellow]Warning: {warning}[/yellow]")
    else:
        rprint(f"\n[red]Failed to create PR: {pr_result.error}[/red]")
        raise typer.Exit(1)
