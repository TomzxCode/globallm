"""Version information for GlobalLM."""

from __future__ import annotations

from pathlib import Path


def _get_git_commit() -> str | None:
    """Get the git commit hash, trying multiple methods."""
    # Method 1: Try reading from _build_metadata.py (created during build)
    try:
        from globallm._build_metadata import GIT_COMMIT  # type: ignore

        return GIT_COMMIT
    except Exception:
        pass

    # Method 2: Try reading .git/HEAD directly (works when running from clone)
    try:
        git_dir = Path(__file__).parent.parent.parent.parent / ".git"
        if git_dir.exists():
            head = (git_dir / "HEAD").read_text().strip()
            if head.startswith("ref:"):
                ref = head.split(" ", 1)[1]
                commit = (git_dir / ref).read_text().strip()
                return commit
            return head
    except Exception:
        pass

    # Method 3: Try git command (works when git is available)
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


# Get commit once at import time
GIT_COMMIT = _get_git_commit()
