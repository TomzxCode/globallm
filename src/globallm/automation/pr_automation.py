"""PR automation with auto-merge capability."""

from dataclasses import dataclass, field
from typing import Any

from github import Github
from github.GitRef import GitRef
from github.GithubException import GithubException
from github.Repository import Repository

from globallm.automation.auto_merge import (
    determine_strategy,
    can_enable_auto_merge,
    get_auto_merge_requirements,
)
from globallm.automation.ci_monitor import (
    CIMonitor,
    CIStatusReport,
)
from globallm.logging_config import get_logger
from globallm.models.solution import Solution

logger = get_logger(__name__)


@dataclass
class PRCreationResult:
    """Result from PR creation."""

    success: bool
    pr_number: int | None = None
    pr_url: str | None = None
    auto_merge_enabled: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class PRAutomation:
    """Automate PR creation and management."""

    def __init__(
        self,
        github_client: Github,
        ci_monitor: CIMonitor | None = None,
    ) -> None:
        """Initialize PR automation.

        Args:
            github_client: PyGithub Github instance
            ci_monitor: Optional CI monitor
        """
        self.github = github_client
        self.ci_monitor = ci_monitor or CIMonitor()

    def create_pr(
        self,
        solution: Solution,
        base_branch: str = "main",
        enable_auto_merge: bool = True,
        dry_run: bool = False,
    ) -> PRCreationResult:
        """Create a pull request for a solution.

        Args:
            solution: Solution to create PR for
            base_branch: Target branch
            enable_auto_merge: Whether to attempt auto-merge
            dry_run: If True, don't actually create PR

        Returns:
            PRCreationResult with outcome
        """
        logger.info(
            "creating_pr",
            repo=solution.repository,
            issue_number=solution.issue_number,
            dry_run=dry_run,
        )

        warnings = []

        try:
            # Get repository
            repo = self.github.get_repo(solution.repository)

            # Determine auto-merge strategy
            _strategy = determine_strategy(solution)

            if not solution.can_auto_merge:
                warnings.append("Auto-merge not allowed for this solution")
                enable_auto_merge = False

            # Create branch name
            branch_name = self._generate_branch_name(solution)

            if not dry_run:
                # Create branch
                _branch = self._create_branch(repo, branch_name, base_branch)

                # Commit changes
                self._commit_changes(repo, branch_name, solution)

                # Create PR
                pr = repo.create_pull(
                    title=f"Fix: {solution.issue_title} (#{solution.issue_number})",
                    body=solution.to_pr_description(),
                    head=branch_name,
                    base=base_branch,
                )
            else:
                # Dry run - simulate PR creation
                pr_number = None
                pr_url = f"https://github.com/{solution.repository}/pull/dry-run"

                logger.info(
                    "dry_run_pr",
                    repo=solution.repository,
                    branch=branch_name,
                    title=solution.issue_title,
                )

                return PRCreationResult(
                    success=True,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    auto_merge_enabled=False,
                    warnings=warnings,
                )

            logger.info(
                "pr_created",
                repo=solution.repository,
                pr=pr.number,
                url=pr.html_url,
            )

            # Attempt auto-merge
            auto_merge_enabled = False
            if enable_auto_merge and can_enable_auto_merge(solution):
                auto_merge_enabled = self._enable_auto_merge(repo, pr, solution)

            return PRCreationResult(
                success=True,
                pr_number=pr.number,
                pr_url=pr.html_url,
                auto_merge_enabled=auto_merge_enabled,
                warnings=warnings,
            )

        except GithubException as e:
            logger.error(
                "pr_creation_failed",
                repo=solution.repository,
                error=str(e),
            )
            return PRCreationResult(
                success=False,
                error=str(e),
                warnings=warnings,
            )

    def _generate_branch_name(self, solution: Solution) -> str:
        """Generate branch name for solution.

        Args:
            solution: Solution to create branch for

        Returns:
            Branch name
        """
        # Use issue number and short title
        safe_title = (
            solution.issue_title.lower()
            .replace(" ", "-")
            .replace("(", "")
            .replace(")", "")
            .replace(":", "")
            .replace("/", "-")[:40]
        )

        # Remove any remaining non-alphanumeric chars
        safe_title = "".join(c if c.isalnum() or c in "-_" else "" for c in safe_title)

        return f"globallm/issue-{solution.issue_number}-{safe_title}"

    def _create_branch(
        self, repo: Repository, branch_name: str, base_branch: str
    ) -> GitRef:
        """Create a new branch from base.

        Args:
            repo: Repository
            branch_name: New branch name
            base_branch: Source branch

        Returns:
            Created Branch object
        """
        # Get base branch SHA
        base = repo.get_branch(base_branch)
        sha = base.commit.sha

        # Create branch
        return repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=sha)

    def _commit_changes(
        self, repo: Repository, branch_name: str, solution: Solution
    ) -> None:
        """Commit changes to branch.

        Args:
            repo: Repository
            branch_name: Target branch
            solution: Solution with patches
        """
        from github import InputGitTreeElement, InputGitAuthor

        # Get latest commit on branch
        branch = repo.get_branch(branch_name)
        latest_commit = repo.get_git_commit(branch.commit.sha)
        base_tree = repo.get_git_tree(latest_commit.sha)

        # Create tree elements
        tree_elements = []
        for patch in solution.patches:
            # Create blob for file
            blob = repo.create_git_blob(content=patch.new_content, encoding="utf-8")
            tree_elements.append(
                InputGitTreeElement(
                    path=patch.file_path, mode="100644", type="blob", sha=blob.sha
                )
            )

        # Create tree
        tree = repo.create_git_tree(tree_elements, base_tree)

        # Create commit
        author = InputGitAuthor(name="GlobalLM", email="noreply@globallm.dev")
        commit = repo.create_git_commit(
            message=f"Fix: {solution.issue_title}\n\n{solution.description}",
            tree=tree,
            parents=[latest_commit],
            author=author,
        )

        # Update branch reference
        repo.get_git_ref(f"heads/{branch_name}").edit(sha=commit.sha)

    def _enable_auto_merge(self, repo: Repository, pr, solution: Solution) -> bool:
        """Attempt to enable auto-merge for a PR.

        Args:
            repo: Repository
            pr: PullRequest
            solution: Associated solution

        Returns:
            True if auto-merge was enabled
        """
        logger.info("attempting_auto_merge", repo=repo.full_name, pr=pr.number)

        try:
            # Check if repository has auto-merge enabled
            # (This requires a specific GitHub setting or app)
            # For now, we'll add a comment indicating readiness

            requirements = get_auto_merge_requirements(solution)
            requirements_text = "\n".join(requirements)

            comment = f"""\
This PR is ready for auto-merge when all CI checks pass.

**Auto-merge Requirements:**
{requirements_text}

Once all CI checks pass, this PR can be automatically merged.
"""

            pr.create_issue_comment(comment)

            logger.info(
                "auto_merge_comment_added",
                repo=repo.full_name,
                pr=pr.number,
            )

            # Note: Actual auto-merge requires either:
            # 1. GitHub's built-in auto-merge feature (maintainer enabled)
            # 2. A GitHub App with merge permissions
            # We add the comment as a signal to maintainers

            return True

        except Exception as e:
            logger.error("auto_merge_failed", error=str(e))
            return False

    def monitor_pr_ci(
        self,
        repo_name: str,
        pr_number: int,
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 30,
    ) -> CIStatusReport:
        """Monitor CI status for a PR.

        Args:
            repo_name: Repository name
            pr_number: Pull request number
            timeout_seconds: Max time to wait
            poll_interval_seconds: Time between checks

        Returns:
            Final CI status report
        """
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        return self.ci_monitor.wait_for_ci(
            pr,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    def handle_ci_failure(
        self,
        repo_name: str,
        pr_number: int,
        failure_report: CIStatusReport,
    ) -> str:
        """Handle CI failure by adding comment and suggestions.

        Args:
            repo_name: Repository name
            pr_number: Pull request number
            failure_report: CI status report

        Returns:
            Comment URL
        """
        from globallm.automation.ci_monitor import (
            analyze_failure,
            get_remédiation_actions,
        )

        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        failures = analyze_failure(failure_report)
        remediation = get_remédiation_actions(failures)

        comment = f"""\
**CI Check Failed**

This PR has failing CI checks:
{self._format_failures(failures)}

**Suggested Actions:**
{self._format_actions(remediation)}

Please fix the issues and push a new commit.
"""

        issue_comment = pr.create_issue_comment(comment)

        logger.info(
            "ci_failure_comment_added",
            repo=repo_name,
            pr=pr_number,
            failed=failure_report.failed_checks,
        )

        return issue_comment.html_url

    def _format_failures(self, failures: list) -> str:
        """Format failure list for display.

        Args:
            failures: List of failure info

        Returns:
            Formatted string
        """
        lines = []
        for failure in failures:
            lines.append(f"- ❌ **{failure.check_name}**: {failure.summary}")
        return "\n".join(lines)

    def _format_actions(self, actions: list[str]) -> str:
        """Format remediation actions for display.

        Args:
            actions: List of action strings

        Returns:
            Formatted string
        """
        lines = []
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")
        return "\n".join(lines)

    def list_prs(
        self,
        repo_name: str,
        state: str = "open",
        creator: str | None = None,
    ) -> list[dict[str, Any]]:
        """List PRs created by this automation.

        Args:
            repo_name: Repository name
            state: PR state (open, closed, all)
            creator: Filter by creator (username)

        Returns:
            List of PR info dicts
        """
        query = f"repo:{repo_name}"
        if state != "all":
            query += f" state:{state}"
        if creator:
            query += f" author:{creator}"

        pulls = self.github.search_issues(query)

        results = []
        for pr in pulls:
            if not hasattr(pr, "pull_request"):
                continue

            results.append(
                {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "url": pr.html_url,
                    "created_at": pr.created_at,
                    "updated_at": pr.updated_at,
                }
            )

        return results

    def get_pr_info(self, repo_name: str, pr_number: int) -> dict[str, Any]:
        """Get detailed info about a PR.

        Args:
            repo_name: Repository name
            pr_number: Pull request number

        Returns:
            PR info dict
        """
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "url": pr.html_url,
            "base_branch": pr.base.ref,
            "head_branch": pr.head.ref,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "commits": pr.commits,
            "created_at": pr.created_at,
            "updated_at": pr.updated_at,
            "merged_at": pr.merged_at,
            "mergeable": pr.mergeable,
        }
