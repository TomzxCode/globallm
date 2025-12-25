"""Repository filtering based on health and quality criteria."""

from datetime import datetime

from github.Repository import Repository

from globallm.filtering.health_scorer import HealthScorer
from globallm.models.repository import RepoCandidate, MaintenanceVerdict
from globallm.logging_config import get_logger

logger = get_logger(__name__)


class RepositoryFilter:
    """Filter repositories based on health and quality criteria."""

    def __init__(self, health_scorer: HealthScorer | None = None) -> None:
        self.health_scorer = health_scorer or HealthScorer()

    def filter_by_health(
        self,
        candidates: list[RepoCandidate],
        min_health_score: float = 0.5,
        max_days_since_last_commit: int = 365,
    ) -> list[RepoCandidate]:
        """Filter candidates by health criteria.

        Args:
            candidates: List of repository candidates
            min_health_score: Minimum overall health score (0-1)
            max_days_since_last_commit: Maximum days since last commit

        Returns:
            Filtered list of candidates
        """
        logger.info(
            "filtering_by_health",
            input_count=len(candidates),
            min_health=min_health_score,
            max_days=max_days_since_last_commit,
        )

        passed = []
        for candidate in candidates:
            # Skip if health score is too low
            if (
                candidate.health_score
                and candidate.health_score.overall < min_health_score
            ):
                logger.debug(
                    "filtered_low_health",
                    repo=candidate.name,
                    health=f"{candidate.health_score.overall:.2f}",
                )
                continue

            # Skip if no recent commits
            if candidate.last_commit_at:
                days_since = (
                    datetime.now(tz=candidate.last_commit_at.tzinfo)
                    - candidate.last_commit_at
                ).days
                if days_since > max_days_since_last_commit:
                    logger.debug(
                        "filtered_stale",
                        repo=candidate.name,
                        days_since=days_since,
                    )
                    continue

            passed.append(candidate)

        filtered_out = len(candidates) - len(passed)
        logger.info(
            "health_filter_complete",
            passed=len(passed),
            filtered_out=filtered_out,
        )

        return passed

    def has_active_maintenance(
        self, repo: Repository, max_days_stale: int = 180
    ) -> bool:
        """Check if repository has active maintenance.

        Args:
            repo: PyGithub Repository object
            max_days_stale: Maximum days without commits to consider active

        Returns:
            True if actively maintained
        """
        try:
            last_commit = repo.get_commits()[0]
            last_commit_date = last_commit.last_modified_datetime
            if not last_commit_date:
                return False

            days_since = (datetime.now(last_commit_date.tzinfo) - last_commit_date).days
            return days_since <= max_days_stale

        except Exception as e:
            logger.warning(
                "maintenance_check_failed", repo=repo.full_name, error=str(e)
            )
            return False

    def has_ci_configured(self, repo: Repository) -> bool:
        """Check if repository has CI configured.

        Args:
            repo: PyGithub Repository object

        Returns:
            True if CI configuration detected
        """
        try:
            contents = repo.get_contents("")
            if not isinstance(contents, list):
                return False

            ci_indicators = [
                ".github/workflows",
                ".gitlab-ci.yml",
                ".travis.yml",
                "circleci",
                "Jenkinsfile",
            ]

            for item in contents:
                if any(indicator in item.name for indicator in ci_indicators):
                    return True

            return False

        except Exception as e:
            logger.warning("ci_check_failed", repo=repo.full_name, error=str(e))
            return False

    def has_tests(self, repo: Repository) -> bool:
        """Check if repository has tests.

        Args:
            repo: PyGithub Repository object

        Returns:
            True if test directory or files detected
        """
        try:
            contents = repo.get_contents("")
            if not isinstance(contents, list):
                return False

            test_indicators = ["test", "tests", "spec", "specs", "__tests__"]

            for item in contents:
                name_lower = item.name.lower()
                if any(indicator in name_lower for indicator in test_indicators):
                    return True

            return False

        except Exception as e:
            logger.warning("test_check_failed", repo=repo.full_name, error=str(e))
            return False

    def is_worthy_of_maintenance(self, candidate: RepoCandidate) -> MaintenanceVerdict:
        """Determine if repository is worth maintaining.

        Args:
            candidate: Repository candidate to evaluate

        Returns:
            MaintenanceVerdict with recommendation
        """
        if not candidate.health_score:
            return MaintenanceVerdict(
                worthy=True,
                reason="Health score not calculated, assuming worthy",
            )

        # Abandoned: no commits in 6+ months AND low health
        if candidate.last_commit_at:
            days_since = (
                datetime.now(tz=candidate.last_commit_at.tzinfo)
                - candidate.last_commit_at
            ).days
            if days_since > 180 and candidate.health_score.overall < 0.3:
                return MaintenanceVerdict(
                    worthy=False,
                    reason=f"Abandoned: {days_since} days since last commit, low health score",
                )

        # Low health overall
        if candidate.health_score.overall < 0.2:
            return MaintenanceVerdict(
                worthy=False,
                reason=f"Very low health score: {candidate.health_score.overall:.2f}",
            )

        # No contributors
        if candidate.health_score.contributor_diversity < 0.1:
            return MaintenanceVerdict(
                worthy=False,
                reason="No contributor diversity",
            )

        # Worthy of maintenance
        return MaintenanceVerdict(
            worthy=True,
            reason=f"Health score: {candidate.health_score.overall:.2f}",
        )
