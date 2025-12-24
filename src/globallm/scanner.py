"""GitHub repository scanner."""

from github import Github
from github.Repository import Repository
from dataclasses import dataclass
from typing import Any


@dataclass
class RepoMetrics:
    """Repository impact metrics."""

    name: str
    stars: int
    forks: int
    open_issues: int
    watchers: int
    subscribers: int
    language: str | None
    score: float


class GitHubScanner:
    """Scan GitHub repositories for impact metrics."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize scanner with optional GitHub token."""
        self.github = Github(token) if token else Github()

    def analyze_repo(self, repo_name: str) -> RepoMetrics:
        """Analyze a single repository."""
        repo = self.github.get_repo(repo_name)
        return self._calculate_metrics(repo)

    def search_repos(
        self, query: str, sort: str = "stars", order: str = "desc", max_results: int = 100
    ) -> list[RepoMetrics]:
        """Search repositories and return metrics."""
        repos = self.github.search_repositories(query=query, sort=sort, order=order)
        results: list[RepoMetrics] = []

        for repo in repos[:max_results]:
            results.append(self._calculate_metrics(repo))

        return sorted(results, key=lambda r: r.score, reverse=True)

    def _calculate_metrics(self, repo: Repository) -> RepoMetrics:
        """Calculate impact score for a repository."""
        # Weighted score formula
        score = (
            repo.stargazers_count * 1.0
            + repo.forks_count * 2.0
            + repo.open_issues_count * 0.1
            + repo.subscribers_count * 5.0
            + repo.watchers_count * 0.5
        )

        return RepoMetrics(
            name=repo.full_name,
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            open_issues=repo.open_issues_count,
            watchers=repo.watchers_count,
            subscribers=repo.subscribers_count,
            language=repo.language,
            score=score,
        )
