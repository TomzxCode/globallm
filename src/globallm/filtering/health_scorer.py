"""Health score calculation for repositories."""

from datetime import datetime, timedelta

from github.Repository import Repository

from globallm.models.repository import HealthScore
from globallm.logging_config import get_logger

logger = get_logger(__name__)


class HealthScorer:
    """Calculate health scores for repositories."""

    def __init__(self) -> None:
        self._commit_cache: dict[str, list[datetime]] = {}

    def calculate_health_score(self, repo: Repository) -> HealthScore:
        """Calculate comprehensive health score for a repository.

        Args:
            repo: PyGithub Repository object

        Returns:
            HealthScore with normalized (0-1) components
        """
        logger.debug("calculating_health", repo=repo.full_name)

        commit_velocity = self._calculate_commit_velocity(repo)
        issue_resolution_rate = self._calculate_issue_resolution_rate(repo)
        ci_status = self._check_ci_status(repo)
        contributor_diversity = self._calculate_contributor_diversity(repo)
        documentation_quality = self._assess_documentation_quality(repo)

        return HealthScore(
            commit_velocity=commit_velocity,
            issue_resolution_rate=issue_resolution_rate,
            ci_status=ci_status,
            contributor_diversity=contributor_diversity,
            documentation_quality=documentation_quality,
        )

    def _calculate_commit_velocity(self, repo: Repository) -> float:
        """Calculate normalized commit velocity (0-1).

        Higher score for more recent commits.
        """
        try:
            # Get recent commits (last 90 days)
            ninety_days_ago = datetime.now() - timedelta(days=90)
            commits = repo.get_commits(since=ninety_days_ago)

            count = 0
            for _ in commits:
                count += 1
                if count >= 100:  # Limit iterations
                    break

            # Normalize: 100+ commits in 90 days = 1.0
            return min(count / 100, 1.0)

        except Exception as e:
            logger.warning(
                "commit_velocity_calc_failed", repo=repo.full_name, error=str(e)
            )
            return 0.5  # Neutral score on failure

    def _calculate_issue_resolution_rate(self, repo: Repository) -> float:
        """Calculate issue resolution rate (0-1).

        Ratio of closed issues to total issues.
        """
        try:
            open_issues = repo.open_issues_count
            # Get closed issues count via search (limited)
            closed_search = repo.get_issues(state="closed")
            closed_count = 0
            for _ in closed_search:
                closed_count += 1
                if closed_count >= 1000:
                    break

            total = open_issues + closed_count
            if total == 0:
                return 0.5  # Neutral if no issues

            return closed_count / total

        except Exception as e:
            logger.warning(
                "issue_resolution_calc_failed", repo=repo.full_name, error=str(e)
            )
            return 0.5

    def _check_ci_status(self, repo: Repository) -> float:
        """Check if CI is configured (0-1).

        Returns 1.0 if CI detected, 0.0 otherwise.
        """
        try:
            contents = repo.get_contents("")
            if not isinstance(contents, list):
                return 0.0

            ci_files = [
                ".github/workflows",
                ".gitlab-ci.yml",
                ".travis.yml",
                "circleci",
                "Jenkinsfile",
                "azure-pipelines.yml",
                ".cirrus.yml",
            ]

            for item in contents:
                if any(ci_file in item.name for ci_file in ci_files):
                    return 1.0

            return 0.0

        except Exception as e:
            logger.warning("ci_check_failed", repo=repo.full_name, error=str(e))
            return 0.0

    def _calculate_contributor_diversity(self, repo: Repository) -> float:
        """Calculate contributor diversity score (0-1).

        Higher score for more unique contributors.
        """
        try:
            contributors = repo.get_contributors()
            count = sum(1 for _ in contributors)

            # Normalize: 50+ contributors = 1.0
            return min(count / 50, 1.0)

        except Exception as e:
            logger.warning(
                "contributor_diversity_calc_failed", repo=repo.full_name, error=str(e)
            )
            return 0.5

    def _assess_documentation_quality(self, repo: Repository) -> float:
        """Assess documentation quality (0-1).

        Based on README, docs folder, and examples.
        """
        try:
            score = 0.0
            contents = repo.get_contents("")

            if not isinstance(contents, list):
                return 0.0

            for item in contents:
                name_lower = item.name.lower()
                # README (+0.4)
                if name_lower.startswith("readme"):
                    score += 0.4
                # Docs folder (+0.3)
                elif name_lower == "docs":
                    score += 0.3
                # Examples (+0.2)
                elif name_lower in ("examples", "example"):
                    score += 0.2
                # Wiki or contributing guide (+0.1)
                elif name_lower in ("contributing.md", "contributing.rst"):
                    score += 0.1

            return min(score, 1.0)

        except Exception as e:
            logger.warning(
                "documentation_quality_calc_failed", repo=repo.full_name, error=str(e)
            )
            return 0.5
