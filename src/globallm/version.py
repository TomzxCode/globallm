"""Version information for GlobalLM."""

from __future__ import annotations

from pathlib import Path

from structlog import get_logger

logger = get_logger(__name__)


def _get_git_commit() -> str | None:
    """Get the git commit hash, trying multiple methods.

    Prioritizes live git methods over build metadata to ensure fresh
    values during development.
    """

    repo_root = Path(__file__).parent.parent.parent

    # Method 1: Try reading .git/HEAD directly (works when running from clone)
    try:
        git_dir = repo_root / ".git"
        logger.debug("Attempting to read git commit from .git directory", git_dir=str(git_dir))
        if git_dir.exists():
            head = (git_dir / "HEAD").read_text().strip()
            if head.startswith("ref:"):
                ref = head.split(" ", 1)[1]
                commit = (git_dir / ref).read_text().strip()
                logger.debug("Successfully read commit from .git/HEAD ref", commit=commit, ref=ref)
                return commit
            logger.debug("Successfully read commit from .git/HEAD (detached)", commit=head)
            return head
        logger.debug(".git directory does not exist")
    except Exception as e:
        logger.debug("Failed to read from .git directory", error=str(e))

    # Method 2: Try git command (works when git is available)
    try:
        import subprocess

        logger.debug("Attempting to read git commit via git command")
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            logger.debug("Successfully read commit via git command", commit=commit[:8])
            return commit
        logger.debug("Git command failed", returncode=result.returncode, stderr=result.stderr.strip())
    except Exception as e:
        logger.debug("Failed to run git command", error=str(e))

    # Method 3: Try reading from _build_metadata.py (created during build, used as fallback)
    try:
        logger.debug("Attempting to read git commit from _build_metadata.py")
        from globallm._build_metadata import GIT_COMMIT  # type: ignore

        logger.debug("Successfully read commit from _build_metadata.py", commit=GIT_COMMIT)
        return GIT_COMMIT
    except Exception as e:
        logger.debug("Failed to read from _build_metadata.py", error=str(e))

    logger.debug("All methods failed to determine git commit")
    return None


def get_git_commit() -> str | None:
    """Get the current git commit hash.

    Returns the commit hash at call time rather than caching at import time,
    ensuring fresh values during development and in long-running processes.
    """
    return _get_git_commit()
