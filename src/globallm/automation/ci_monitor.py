"""CI status monitoring for PR automation."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from github.PullRequest import PullRequest
from github.Repository import Repository

from globallm.logging_config import get_logger

logger = get_logger(__name__)


class CIStatus(Enum):
    """CI check status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class CICheckResult:
    """Result of a CI check."""

    name: str
    status: CIStatus
    url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_successful(self) -> bool:
        return self.status == CIStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status in (CIStatus.FAILURE, CIStatus.ERROR)

    @property
    def is_pending(self) -> bool:
        return self.status in (CIStatus.PENDING, CIStatus.RUNNING)


@dataclass
class CIStatusReport:
    """Overall CI status for a PR."""

    status: CIStatus
    checks: list[CICheckResult]
    total_checks: int
    passed_checks: int
    failed_checks: int
    pending_checks: int

    @property
    def all_passed(self) -> bool:
        """Check if all CI checks passed."""
        return self.status == CIStatus.SUCCESS and self.failed_checks == 0

    @property
    def has_failures(self) -> bool:
        """Check if there are any failures."""
        return self.failed_checks > 0

    @property
    def is_pending(self) -> bool:
        """Check if any checks are still pending."""
        return self.pending_checks > 0

    @property
    def completion_percent(self) -> float:
        """Calculate percentage of checks completed."""
        if self.total_checks == 0:
            return 0.0
        completed = self.passed_checks + self.failed_checks
        return (completed / self.total_checks) * 100


class CIMonitor:
    """Monitor CI status for PRs."""

    def __init__(self) -> None:
        """Initialize CI monitor."""

    def get_pr_status(self, pr: PullRequest) -> CIStatusReport:
        """Get CI status for a pull request.

        Args:
            pr: PullRequest to check

        Returns:
            CIStatusReport with status details
        """
        logger.info("checking_ci_status", repo=pr.base.repo.full_name, pr=pr.number)

        try:
            # Get combined status
            combined_status = pr.get_commits().reversed[0].get_combined_status()

            checks = []
            total = 0
            passed = 0
            failed = 0
            pending = 0

            # Process individual statuses
            for status in combined_status.statuses:
                total += 1
                check = CICheckResult(
                    name=status.context,
                    status=self._map_status(status.state),
                    url=status.target_url,
                    started_at=status.created_at,
                    completed_at=None,  # Status doesn't have completion time
                )

                if check.is_successful:
                    passed += 1
                elif check.is_failed:
                    failed += 1
                elif check.is_pending:
                    pending += 1

                checks.append(check)

            # Determine overall status
            if combined_status.state == "success":
                overall = CIStatus.SUCCESS
            elif combined_status.state == "failure":
                overall = CIStatus.FAILURE
            elif combined_status.state == "pending":
                overall = CIStatus.PENDING
            else:
                overall = CIStatus.UNKNOWN

            report = CIStatusReport(
                status=overall,
                checks=checks,
                total_checks=total,
                passed_checks=passed,
                failed_checks=failed,
                pending_checks=pending,
            )

            logger.info(
                "ci_status_report",
                repo=pr.base.repo.full_name,
                pr=pr.number,
                status=overall.value,
                passed=passed,
                failed=failed,
                pending=pending,
            )

            return report

        except Exception as e:
            logger.error("ci_status_check_failed", pr=pr.number, error=str(e))
            # Return unknown status on error
            return CIStatusReport(
                status=CIStatus.UNKNOWN,
                checks=[],
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                pending_checks=0,
            )

    def wait_for_ci(
        self,
        pr: PullRequest,
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 30,
    ) -> CIStatusReport:
        """Wait for CI to complete.

        Args:
            pr: PullRequest to monitor
            timeout_seconds: Maximum time to wait
            poll_interval_seconds: Time between checks

        Returns:
            Final CI status report
        """
        import time

        logger.info(
            "waiting_for_ci",
            repo=pr.base.repo.full_name,
            pr=pr.number,
            timeout=timeout_seconds,
        )

        start_time = datetime.now()

        while True:
            report = self.get_pr_status(pr)

            # Check if complete
            if not report.is_pending:
                return report

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning(
                    "ci_timeout",
                    repo=pr.base.repo.full_name,
                    pr=pr.number,
                    elapsed=elapsed,
                )
                return report

            # Wait before next poll
            time.sleep(poll_interval_seconds)

    def get_check_runs(self, repo: Repository, sha: str) -> list[CICheckResult]:
        """Get GitHub Actions check runs for a commit.

        Args:
            repo: Repository
            sha: Commit SHA

        Returns:
            List of check results
        """
        checks = []

        try:
            # Try to get check runs (GitHub Actions)
            check_runs = repo.get_commit(sha).get_check_runs()

            for run in check_runs:
                check = CICheckResult(
                    name=run.name,
                    status=self._map_check_run_status(run.conclusion),
                    url=run.html_url,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                )
                checks.append(check)

        except Exception as e:
            logger.warning("check_runs_fetch_failed", sha=sha[:8], error=str(e))

        return checks

    def _map_status(self, state: str) -> CIStatus:
        """Map GitHub state to CIStatus.

        Args:
            state: GitHub state string

        Returns:
            CIStatus enum value
        """
        mapping = {
            "success": CIStatus.SUCCESS,
            "failure": CIStatus.FAILURE,
            "error": CIStatus.ERROR,
            "pending": CIStatus.PENDING,
            "expected": CIStatus.PENDING,
        }
        return mapping.get(state, CIStatus.UNKNOWN)

    def _map_check_run_status(self, conclusion: str | None) -> CIStatus:
        """Map GitHub Actions conclusion to CIStatus.

        Args:
            conclusion: Check run conclusion string

        Returns:
            CIStatus enum value
        """
        if conclusion is None:
            return CIStatus.RUNNING

        mapping = {
            "success": CIStatus.SUCCESS,
            "failure": CIStatus.FAILURE,
            "neutral": CIStatus.SUCCESS,
            "cancelled": CIStatus.ERROR,
            "timed_out": CIStatus.ERROR,
            "action_required": CIStatus.FAILURE,
        }
        return mapping.get(conclusion, CIStatus.UNKNOWN)


@dataclass
class CIFailureInfo:
    """Information about a CI failure."""

    check_name: str
    status: CIStatus
    url: str | None = None
    logs_url: str | None = None
    summary: str = ""


def analyze_failure(report: CIStatusReport) -> list[CIFailureInfo]:
    """Analyze CI failures and extract actionable info.

    Args:
        report: CI status report with failures

    Returns:
        List of failure information
    """
    failures = []

    for check in report.checks:
        if check.is_failed:
            failures.append(
                CIFailureInfo(
                    check_name=check.name,
                    status=check.status,
                    url=check.url,
                    summary=f"Check '{check.name}' failed",
                )
            )

    return failures


def can_auto_merge(report: CIStatusReport) -> bool:
    """Determine if PR can be auto-merged based on CI.

    Args:
        report: CI status report

    Returns:
        True if auto-merge is safe
    """
    # Must have all checks passed
    if not report.all_passed:
        return False

    # Must have at least one check
    if report.total_checks == 0:
        logger.warning("no_ci_checks", pr="unknown")
        return False

    return True


def get_remédiation_actions(failures: list[CIFailureInfo]) -> list[str]:
    """Get suggested remediation actions for CI failures.

    Args:
        failures: List of CI failures

    Returns:
        List of remediation suggestions
    """
    actions = []

    for failure in failures:
        if "lint" in failure.check_name.lower():
            actions.append(f"Run linter and fix style issues in {failure.check_name}")
        elif "test" in failure.check_name.lower():
            actions.append(f"Fix failing tests in {failure.check_name}")
        elif "type" in failure.check_name.lower():
            actions.append("Fix type checking errors")
        elif "security" in failure.check_name.lower():
            actions.append("Address security vulnerabilities")
        else:
            actions.append(f"Investigate failure in {failure.check_name}")

    return actions
