"""CLI for GlobalLM."""

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print as rprint

from globallm.logging_config import configure_logging, get_logger
from globallm.config.loader import load_config, save_config, get_config_path

logger = get_logger(__name__)

app = typer.Typer(
    name="globallm",
    help="Scan GitHub to identify impactful libraries and contribute to their success",
    no_args_is_help=True,
)

# Config subcommand app
config_app = typer.Typer(name="config", help="Configuration management")

# Budget subcommand app
budget_app = typer.Typer(name="budget", help="Budget management")

# Add subcommands
app.add_typer(config_app, name="config", help="Configuration management")
app.add_typer(budget_app, name="budget", help="Budget management")


def config_callback(log_level: str) -> None:
    """Configure logging based on log level."""
    configure_logging(log_level)


@app.callback()
def main(
    ctx: typer.Context,
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Set logging level",
        callback=lambda x: config_callback(x),
    ),
    config_file: str = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file",
    ),
) -> None:
    """GlobalLM - AI-powered open source contribution tool."""
    load_dotenv()

    # Load config if specified
    if config_file:
        ctx.ensure_object(dict)
        ctx.obj["config_path"] = Path(config_file)
        load_config(Path(config_file))


@app.command()
def discover(
    domain: str = typer.Option("overall", help="Domain to search"),
    language: str = typer.Option(None, help="Filter by programming language"),
    min_stars: int = typer.Option(None, help="Minimum stars"),
    min_dependents: int = typer.Option(None, help="Minimum dependents"),
    max_results: int = typer.Option(20, help="Max results to return"),
    use_cache: bool = typer.Option(True, help="Use cache"),
) -> None:
    """Discover repositories by domain and language."""
    from globallm.scanner import GitHubScanner, Domain
    import os

    config = load_config()
    token = os.getenv("GITHUB_TOKEN")

    # Apply config filters if CLI args not specified
    if min_stars is None:
        min_stars = config.filters.min_stars
    if min_dependents is None:
        min_dependents = config.filters.min_dependents

    rprint("[bold cyan]Discovering repositories...[/bold cyan]")
    rprint(f"  Domain: {domain}")
    rprint(f"  Language: {language or 'All'}")
    rprint(f"  Min stars: {min_stars:,}")
    rprint(f"  Min dependents: {min_dependents:,}")

    scanner = GitHubScanner(token, use_cache=use_cache)

    try:
        domain_enum = Domain(domain)
    except ValueError:
        rprint(f"[red]Invalid domain: {domain}[/red]")
        available = [d.value for d in Domain]
        rprint(f"Available domains: {', '.join(available)}")
        raise typer.Exit(1)

    import time

    start_time = time.time()
    results = scanner.search_by_domain(
        domain_enum,
        language=language,
        max_results=max_results,
    )
    duration = time.time() - start_time

    rprint(f"\n[green]Found {len(results)} repositories in {duration:.1f}s[/green]")
    _display_results(results)


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="Repository name (owner/repo)"),
    include_dependents: bool = typer.Option(False, help="Include dependent analysis"),
) -> None:
    """Analyze a single repository."""
    from globallm.scanner import GitHubScanner
    import os

    token = os.getenv("GITHUB_TOKEN")

    rprint(f"[bold cyan]Analyzing {repo}...[/bold cyan]")

    scanner = GitHubScanner(token)
    metrics = scanner.analyze_repo(repo)

    rprint("\n[bold]Repository Metrics[/bold]")
    rprint(f"  Stars: {metrics.stars:,}")
    rprint(f"  Forks: {metrics.forks:,}")
    rprint(f"  Open issues: {metrics.open_issues:,}")
    rprint(f"  Watchers: {metrics.watchers:,}")
    rprint(f"  Language: {metrics.language or 'N/A'}")
    rprint(f"  Score: {metrics.score:.1f}")


@app.command()
def redundancy(
    repos: list[str] = typer.Argument(..., help="Repositories to compare (owner/repo)"),
    threshold: float = typer.Option(0.75, help="Similarity threshold (0-1)"),
) -> None:
    """Detect redundancy between repositories."""
    from globallm.scanner import GitHubScanner
    from globallm.analysis.redundancy import RedundancyDetector
    from globallm.models.repository import Language
    import os

    token = os.getenv("GITHUB_TOKEN")
    scanner = GitHubScanner(token)
    detector = RedundancyDetector()

    rprint("[bold cyan]Analyzing repository redundancy...[/bold cyan]")

    # Fetch repo data and READMEs
    repo_data = []
    for repo_name in repos:
        try:
            metrics = scanner.analyze_repo(repo_name)

            # Try to get README
            readme = ""
            try:
                repo = scanner.github.get_repo(repo_name)
                readme_content = repo.get_readme()
                readme = readme_content.decoded_content.decode()
            except Exception:
                pass

            # Detect language
            language = None
            if metrics.language:
                language = Language.from_string(metrics.language)

            repo_data.append(
                {
                    "name": repo_name,
                    "stars": metrics.stars,
                    "readme": readme,
                    "language": language,
                    "api_signature": None,  # Would need file analysis
                }
            )
        except Exception as e:
            rprint(f"[yellow]Warning: Could not analyze {repo_name}: {e}[/yellow]")

    # Compare all pairs
    rprint("\n[bold]Redundancy Analysis:[/bold]\n")
    found_redundancy = False

    for i in range(len(repo_data)):
        for j in range(i + 1, len(repo_data)):
            repo_a = repo_data[i]
            repo_b = repo_data[j]

            readme_sim = detector.compute_readme_similarity(
                repo_a["readme"], repo_b["readme"]
            )

            if readme_sim > threshold:
                found_redundancy = True
                keep = (
                    repo_a["name"]
                    if repo_a["stars"] >= repo_b["stars"]
                    else repo_b["name"]
                )
                archive = (
                    repo_b["name"]
                    if repo_a["stars"] >= repo_b["stars"]
                    else repo_a["name"]
                )

                rprint("[red]Redundancy detected:[/red]")
                rprint(f"  {repo_a['name']} <-> {repo_b['name']}")
                rprint(f"  README similarity: {readme_sim:.1%}")
                rprint(
                    f"  Recommendation: Keep [green]{keep}[/green], archive {archive}"
                )
                rprint()

    if not found_redundancy:
        rprint("[green]No significant redundancy found[/green]")
        for repo in repo_data:
            rprint(f"  - {repo['name']}: {repo['stars']:,} stars")


@app.command()
def status(
    export: str = typer.Option(None, help="Export format (json)"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Show dashboard"),
) -> None:
    """Show system status and statistics."""
    config = load_config()

    if dashboard:
        _show_dashboard()
        return

    rprint("[bold cyan]GlobalLM Status[/bold cyan]")
    rprint(f"  Log level: {config.log_level}")
    rprint(f"  LLM provider: {config.llm_provider}")
    rprint(f"  LLM model: {config.llm_model}")

    rprint("\n[bold]Filters[/bold]")
    rprint(f"  Min stars: {config.filters.min_stars:,}")
    rprint(f"  Min dependents: {config.filters.min_dependents:,}")
    rprint(f"  Min health score: {config.filters.min_health_score}")

    rprint("\n[bold]Budget[/bold]")
    rprint(f"  Weekly token budget: {config.budget.weekly_token_budget:,}")
    rprint(f"  Max tokens per repo: {config.budget.max_tokens_per_repo:,}")


@app.command("issues")
def cmd_issues(
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
        from globallm.models.issue import IssueCategory

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


@app.command("prioritize")
def cmd_prioritize(
    language: str = typer.Option(None, help="Filter by programming language"),
    top: int = typer.Option(20, help="Number of top issues to show"),
    min_priority: float = typer.Option(0.0, help="Minimum priority score"),
    export: str = typer.Option(None, help="Export to file (json, csv)"),
) -> None:
    """Prioritize issues across repositories."""
    from globallm.issues.prioritizer import IssuePrioritizer
    from globallm.budget.budget_manager import BudgetManager
    from globallm.config.loader import load_config
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

        from globallm.issues.fetcher import IssueFetcher

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
        if export:
            if export == "json":
                import json

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


@app.command("fix")
def cmd_fix(
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
    import re

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


@config_app.command("show")
def config_show(
    key: str = typer.Option(None, help="Show specific config key"),
) -> None:
    """Show current configuration."""
    config = load_config()

    if key:
        # Navigate nested keys with dot notation
        keys = key.split(".")
        value = config
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                rprint(f"[red]Key not found: {key}[/red]")
                raise typer.Exit(1)
        rprint(f"{key}: {value}")
    else:
        rprint("[bold]Configuration file:[/bold]")
        rprint(f"  {get_config_path()}")

        rprint("\n[bold]Current settings:[/bold]")
        rprint(f"  filters.min_stars = {config.filters.min_stars}")
        rprint(f"  filters.min_dependents = {config.filters.min_dependents}")
        rprint(f"  budget.weekly_token_budget = {config.budget.weekly_token_budget}")
        rprint(f"  priority.impact_weight = {config.priority.impact_weight}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (e.g., filters.min_stars)"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Set a configuration value."""
    config = load_config()
    keys = key.split(".")

    # Parse value based on type
    try:
        # Try int first
        parsed_value = int(value)
    except ValueError:
        try:
            # Try float
            parsed_value = float(value)
        except ValueError:
            # Try bool
            if value.lower() in ("true", "yes", "1"):
                parsed_value = True
            elif value.lower() in ("false", "no", "0"):
                parsed_value = False
            else:
                parsed_value = value

    # Set the value
    obj = config
    for k in keys[:-1]:
        if hasattr(obj, k):
            obj = getattr(obj, k)
        elif isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            rprint(f"[red]Key not found: {key}[/red]")
            raise typer.Exit(1)

    final_key = keys[-1]
    if hasattr(obj, final_key):
        setattr(obj, final_key, parsed_value)
    elif isinstance(obj, dict):
        obj[final_key] = parsed_value
    else:
        rprint(f"[red]Key not found: {key}[/red]")
        raise typer.Exit(1)

    save_config(config)
    rprint(f"[green]Set {key} = {parsed_value}[/green]")


@config_app.command("path")
def config_path() -> None:
    """Show the configuration file path."""
    rprint(f"{get_config_path()}")


@budget_app.command("show")
def budget_show() -> None:
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


@budget_app.command("reset")
def budget_reset(
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


def _display_results(results: list) -> None:
    """Display repository results."""

    rprint("\n[bold]Top Results:[/bold]")
    for i, repo in enumerate(results[:10], 1):
        rprint(f"{i}. [bold]{repo.name}[/bold]")
        rprint(
            f"   Stars: {repo.stars:,} | Forks: {repo.forks:,} | Score: {repo.score:.1f}"
        )
        rprint(f"   Language: {repo.language or 'N/A'}")
        rprint()


def _show_dashboard() -> None:
    """Show the status dashboard."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from globallm.config.loader import load_config

    console = Console()
    config = load_config()

    # Header panel
    header = Panel(
        "[bold cyan]GlobalLM Status Dashboard[/bold cyan]\n"
        f"Budget: 0 / {config.budget.weekly_token_budget:,} tokens (0%)",
        title="Status",
    )
    console.print(header)

    # Repository table
    table = Table(title="Active Repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Issues", justify="right")
    table.add_column("PRs", justify="right")
    table.add_column("Merged", justify="right")
    table.add_column("Impact", justify="right")

    # Add placeholder row
    table.add_row("No active repositories", "0", "0", "0", "0.0")

    console.print(table)

    # Language breakdown
    rprint("\n[bold]Language Breakdown:[/bold]")
    rprint("  Python:      [blue]░░░░░░░░░░░░░░░░░░░░░[/blue] 0 PRs")
    rprint("  JavaScript:  [blue]░░░░░░░░░░░░░░░░░░░░░[/blue] 0 PRs")


# Legacy argparse support for backward compatibility
def parse_args():
    """Parse command line arguments (legacy)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Search GitHub for impactful repositories"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="overall",
        help="Domain to search (default: overall)",
    )
    parser.add_argument("--language", type=str, help="Filter by programming language")
    parser.add_argument(
        "--max-results", type=int, default=20, help="Max results to return"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Set logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable cache for this run"
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear the cache and exit"
    )
    return parser.parse_args()


def run(args) -> None:
    """Run the legacy scanner command."""
    from globallm.scanner import GitHubScanner, Domain
    import os
    import time

    if args.verbose:
        logger.debug("Verbose mode enabled")

    token = os.getenv("GITHUB_TOKEN")
    if token:
        logger.debug("GitHub token found in environment")
    else:
        logger.warning(
            "No GITHUB_TOKEN found - using unauthenticated API (rate limited)"
        )

    if args.clear_cache:
        scanner = GitHubScanner(token)
        scanner.clear_cache()
        print("Cache cleared.")
        return

    use_cache = not args.no_cache
    logger.info(
        "initializing_scanner",
        domain=args.domain,
        language=args.language,
        max_results=args.max_results,
        use_cache=use_cache,
    )

    scanner = GitHubScanner(token, use_cache=use_cache)

    domain = Domain(args.domain)

    start_time = time.time()
    results = scanner.search_by_domain(
        domain, language=args.language, max_results=args.max_results
    )
    duration = time.time() - start_time

    logger.info(
        "search_completed",
        result_count=len(results),
        duration_seconds=f"{duration:.2f}",
    )

    domain_label = domain.value.replace("_", " ").title()
    lang_label = f" ({args.language})" if args.language else ""
    print(f"Most impactful {domain_label}{lang_label} repositories:")
    print("-" * 60)
    for i, repo in enumerate(results[:10], 1):
        print(f"{i}. {repo.name}")
        print(
            f"   Stars: {repo.stars:,} | Forks: {repo.forks:,} | Score: {repo.score:.1f}"
        )
        print(f"   Language: {repo.language or 'N/A'}")
        print()


if __name__ == "__main__":
    app()
