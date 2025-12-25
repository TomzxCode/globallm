"""CLI for GlobalLM."""

from pathlib import Path

import typer
from dotenv import load_dotenv

from globallm.logging_config import configure_logging, get_logger
from globallm.config.loader import load_config

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


# Import and register commands (must come after app is defined)
from . import (  # noqa: E402
    discover,
    analyze,
    redundancy,
    status,
    issues,
    prioritize,
    fix,
    user,
    repos,
)

app.add_typer(discover.app)
app.add_typer(analyze.app)
app.add_typer(redundancy.app)
app.add_typer(status.app)
app.add_typer(issues.app)
app.add_typer(prioritize.app)
app.add_typer(fix.app)
app.add_typer(user.app)
app.add_typer(repos.app)

from . import config, budget  # noqa: E402

config_app.add_typer(config.app, help="Configuration management")
budget_app.add_typer(budget.app, help="Budget management")


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
