"""CLI for GitHub scanner."""

import os
from globallm.scanner import GitHubScanner


def main() -> None:
    """Run the GitHub scanner CLI."""
    token = os.getenv("GITHUB_TOKEN")
    scanner = GitHubScanner(token)

    # Example: Search for popular Python ML libraries
    query = "language:python machine learning"
    results = scanner.search_repos(query, max_results=20)

    print("Most impactful Python ML libraries:")
    print("-" * 60)
    for i, repo in enumerate(results[:10], 1):
        print(f"{i}. {repo.name}")
        print(f"   Stars: {repo.stars:,} | Forks: {repo.forks:,} | Score: {repo.score:.1f}")
        print(f"   Language: {repo.language}")
        print()


if __name__ == "__main__":
    main()
