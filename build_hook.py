"""Custom build hook to embed git commit in the package."""

from __future__ import annotations

import os
import subprocess
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class VersionMetadataHook(BuildHookInterface):
    """Build hook to write version metadata with git commit."""

    def initialize(self, version: str, build_data: dict) -> None:
        """Initialize the build hook and write version metadata."""
        git_commit = self._get_git_commit()
        metadata_path = os.path.join(self.root, "src", "globallm", "_build_metadata.py")

        with open(metadata_path, "w") as f:
            f.write(f'# Auto-generated during build\nGIT_COMMIT = "{git_commit}"\n')

        build_data["force_include"]["src/globallm/_build_metadata.py"] = (
            "globallm/_build_metadata.py"
        )

    def _get_git_commit(self) -> str:
        """Get the current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"
