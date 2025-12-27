"""Fix command."""

import os
import re
from typing import TYPE_CHECKING

import typer
from rich import print as rprint

if TYPE_CHECKING:
    from github import Github

app = typer.Typer(help="Analyze an issue and generate a fix")


@app.command()
def fix(
    issue_url: str = typer.Option(
        None, help="GitHub issue URL (optional - if not provided, works on highest priority available issue)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't actually create PR"),
    auto_merge: bool = typer.Option(True, help="Enable auto-merge if safe"),
    branch: str = typer.Option("main", help="Target branch"),
) -> None:
    """Analyze an issue and generate a fix."""
    from globallm.agent.heartbeat import HeartbeatManager
    from globallm.agent.identity import AgentIdentity
    from globallm.github import create_github_client
    from globallm.storage.issue_store import IssueStore

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        rprint("[red]GITHUB_TOKEN required for PR creation[/red]")
        raise typer.Exit(1)

    github_client = create_github_client(token)

    # Initialize components
    issue_store = IssueStore()
    agent = AgentIdentity.create()
    heartbeat_mgr = HeartbeatManager(agent.agent_id, issue_store)

    # Determine which issue to work on
    if issue_url:
        # Explicit URL provided - work on that specific issue
        match = re.match(r"https://github.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
        if not match:
            rprint("[red]Invalid issue URL format[/red]")
            rprint("Expected: https://github.com/owner/repo/issues/123")
            raise typer.Exit(1)

        owner, repo_name, issue_number_str = match.groups()
        repo = f"{owner}/{repo_name}"
        issue_number = int(issue_number_str)

        # Try to claim it if available
        issue_dict = issue_store.get_issue(repo, issue_number)
        if not issue_dict:
            rprint(f"[red]Issue #{issue_number} not found in issue store[/red]")
            rprint("[yellow]Run 'globallm prioritize' first to populate the issue store[/yellow]")
            raise typer.Exit(1)

        # Attempt assignment
        if not issue_store.assign_issue(repo, issue_number, agent.agent_id):
            rprint(f"[red]Issue #{issue_number} is already assigned to another agent[/red]")
            raise typer.Exit(1)

        rprint(f"[bold cyan]Claimed issue #{issue_number} in {repo}[/bold cyan]")

    else:
        # No URL provided - claim next available issue
        issue_dict = issue_store.claim_next_available_issue(agent.agent_id)
        if not issue_dict:
            rprint("[yellow]No available issues to work on[/yellow]")
            rprint("[yellow]Run 'globallm prioritize' to populate issues[/yellow]")
            raise typer.Exit(0)

        repo = issue_dict["repository"]
        issue_number = int(issue_dict["number"])

        rprint(f"[bold cyan]Claimed issue #{issue_number} in {repo}[/bold cyan]")
        rprint(f"  Title: {issue_dict.get('title', 'N/A')}")
        rprint(f"  Priority: {issue_dict.get('priority', 'N/A')}")

    # Start heartbeat monitoring
    heartbeat_mgr.start_monitoring(repo, issue_number)

    try:
        _process_issue(
            repo, issue_number, github_client, dry_run, auto_merge, branch, agent
        )
        # Mark as completed
        issue_store.release_issue(repo, issue_number, agent.agent_id, "completed")
        rprint(f"[green]Issue #{issue_number} marked as completed[/green]")
    except Exception:
        # Mark as failed
        issue_store.release_issue(repo, issue_number, agent.agent_id, "failed")
        rprint(f"[yellow]Issue #{issue_number} marked as failed[/yellow]")
        raise
    finally:
        # Always stop heartbeat monitoring
        heartbeat_mgr.stop_monitoring()


def _process_issue(
    repo: str,
    issue_number: int,
    github_client: Github,
    dry_run: bool,
    auto_merge: bool,
    branch: str,
    agent,  # AgentIdentity
) -> None:
    """Process an issue (existing logic from original fix command)."""
    from globallm.automation.pr_automation import PRAutomation
    from globallm.budget.budget_manager import BudgetManager
    from globallm.issues.analyzer import IssueAnalyzer
    from globallm.issues.fetcher import IssueFetcher
    from globallm.llm.claude import ClaudeLLM
    from globallm.solution.code_generator import CodeGenerator
    from globallm.solution.engine import SolutionEngine

    rprint(f"[bold cyan]Analyzing issue #{issue_number} in {repo}...[/bold cyan]")

    # Check budget
    manager = BudgetManager()
    if not manager.can_process_repo(repo, 10000):
        rprint(f"[red]Insufficient budget for {repo}[/red]")
        raise typer.Exit(1)

    # Initialize LLM and components
    llm = ClaudeLLM()
    analyzer = IssueAnalyzer(llm)
    code_generator = CodeGenerator(llm)
    engine = SolutionEngine(analyzer=analyzer, code_generator=code_generator)

    # Fetch the issue
    fetcher = IssueFetcher(github_client)
    issue = fetcher.fetch_single_issue(repo, issue_number)

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
    pr_automation = PRAutomation(github_client)
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
