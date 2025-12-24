"""CLI for GitHub scanner."""

import os
import argparse
from globallm.scanner import GitHubScanner, Domain


def main() -> None:
    """Run the GitHub scanner CLI."""
    parser = argparse.ArgumentParser(
        description="Search GitHub for impactful repositories"
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=[d.value for d in Domain],
        default=Domain.OVERALL.value,
        help="Domain to search (default: overall)",
    )
    parser.add_argument("--language", type=str, help="Filter by programming language")
    parser.add_argument(
        "--max-results", type=int, default=20, help="Max results to return"
    )

    args = parser.parse_args()
    token = os.getenv("GITHUB_TOKEN")
    scanner = GitHubScanner(token)

    domain = Domain(args.domain)
    results = scanner.search_by_domain(
        domain, language=args.language, max_results=args.max_results
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
    main()
