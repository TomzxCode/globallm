"""CLI for GitHub scanner."""

import argparse
import os
import time

from dotenv import load_dotenv
from globallm.logging_config import configure_logging, get_logger

logger = get_logger(__name__)

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

DOMAIN_CHOICES = [
    "overall",
    "ai_ml",
    "web_dev",
    "data_science",
    "cloud_devops",
    "mobile",
    "security",
    "games",
]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Search GitHub for impactful repositories"
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=DOMAIN_CHOICES,
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
        choices=LOG_LEVELS,
        default="INFO",
        help="Set logging level (default: INFO)",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    """Run the GitHub scanner command."""
    from globallm.scanner import GitHubScanner, Domain

    if args.verbose:
        logger.debug("Verbose mode enabled")

    token = os.getenv("GITHUB_TOKEN")
    if token:
        logger.debug("GitHub token found in environment")
    else:
        logger.warning(
            "No GITHUB_TOKEN found - using unauthenticated API (rate limited)"
        )

    logger.info(
        "initializing_scanner",
        domain=args.domain,
        language=args.language,
        max_results=args.max_results,
    )

    scanner = GitHubScanner(token)

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


def main() -> None:
    """Run the GitHub scanner CLI."""
    load_dotenv()
    args = parse_args()
    configure_logging(args.log_level)
    run(args)


if __name__ == "__main__":
    main()
