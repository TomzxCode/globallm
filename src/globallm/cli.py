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

# Add subcommands
app.add_typer(config_app, name="config", help="Configuration management")


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
