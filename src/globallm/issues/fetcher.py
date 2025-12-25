"""GitHub issue fetching."""

from globallm.logging_config import get_logger
from globallm.models.issue import Issue

logger = get_logger(__name__)


class IssueFetcher:
    """Fetch issues from GitHub repositories."""

    def __init__(self, github_client) -> None:
        """Initialize with a GitHub client.

        Args:
            github_client: PyGithub Github instance
        """
        self.github = github_client

    def fetch_repo_issues(
        self,
        repo_name: str,
        state: str = "open",
        limit: int = 100,
        labels: list[str] | None = None,
    ) -> list[Issue]:
        """Fetch issues from a repository.

        Args:
            repo_name: Repository name (owner/repo)
            state: Issue state ("open", "closed", "all")
            limit: Maximum number of issues to fetch
            labels: Filter by labels (if specified, only issues with these labels)

        Returns:
            List of Issue objects
        """
        logger.info(
            "fetching_repo_issues",
            repo=repo_name,
            state=state,
            limit=limit,
            labels=labels,
        )

        try:
            # Build query
            query = f"repo:{repo_name} is:issue state:{state}"
            if labels:
                query += " " + " ".join(f"label:{label}" for label in labels)

            issues = self.github.search_issues(query, sort="created", order="desc")

            results: list[Issue] = []
            for i, issue in enumerate(issues):
                if i >= limit:
                    break

                # Skip pull requests
                if issue.pull_request:
                    continue

                results.append(Issue.from_github_issue(issue, repo_name))

            logger.info(
                "issues_fetched",
                repo=repo_name,
                count=len(results),
            )

            return results

        except Exception as e:
            logger.error("fetch_issues_failed", repo=repo_name, error=str(e))
            raise

    def fetch_issues_by_language(
        self,
        language: str,
        stars_min: int = 1000,
        state: str = "open",
        limit_per_repo: int = 10,
        max_repos: int = 20,
    ) -> dict[str, list[Issue]]:
        """Fetch issues from top repositories by language.

        Args:
            language: Programming language
            stars_min: Minimum stars for repositories
            state: Issue state
            limit_per_repo: Max issues per repository
            max_repos: Maximum repositories to query

        Returns:
            Dict mapping repo names to their issues
        """
        logger.info(
            "fetching_issues_by_language",
            language=language,
            stars_min=stars_min,
            max_repos=max_repos,
        )

        # Search for repos
        repo_query = f"language:{language} stars:>={stars_min}"
        repos = self.github.search_repositories(repo_query, sort="stars", order="desc")

        results: dict[str, list[Issue]] = {}

        for i, repo in enumerate(repos):
            if i >= max_repos:
                break

            repo_name = repo.full_name
            try:
                issues = self.fetch_repo_issues(
                    repo_name, state=state, limit=limit_per_repo
                )
                if issues:
                    results[repo_name] = issues
            except Exception as e:
                logger.warning("skip_repo_issues", repo=repo_name, error=str(e))
                continue

        total_issues = sum(len(issues) for issues in results.values())
        logger.info(
            "language_issues_fetched",
            language=language,
            repos=len(results),
            total_issues=total_issues,
        )

        return results

    def fetch_single_issue(self, repo_name: str, issue_number: int) -> Issue:
        """Fetch a single issue by number.

        Args:
            repo_name: Repository name (owner/repo)
            issue_number: Issue number

        Returns:
            Issue object
        """
        logger.info("fetching_single_issue", repo=repo_name, number=issue_number)

        try:
            repo = self.github.get_repo(repo_name)
            issue = repo.get_issue(issue_number)

            return Issue.from_github_issue(issue, repo_name)

        except Exception as e:
            logger.error(
                "fetch_single_issue_failed",
                repo=repo_name,
                number=issue_number,
                error=str(e),
            )
            raise
