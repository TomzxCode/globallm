"""Package registry integration for dependency data."""

from urllib.parse import quote
from typing import Any

import httpx

from globallm.models.repository import Language
from globallm.logging_config import get_logger

logger = get_logger(__name__)


class PackageRegistryClient:
    """Client for fetching package data from various registries."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def get_pypi_dependents(self, package_name: str) -> int:
        """Get dependent count for a PyPI package from libraries.io."""
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/pypi/{quote(package_name)}/dependent-repositories"
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(
                "pypi_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_npm_dependents(self, package_name: str) -> int:
        """Get dependent count for an npm package from libraries.io."""
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/npm/{quote(package_name)}/dependent-repositories"
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(
                "npm_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_crates_dependents(self, package_name: str) -> int:
        """Get dependent count for a crates.io package from libraries.io."""
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/cratesio/{quote(package_name)}/dependent-repositories"
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(
                "crates_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_maven_dependents(self, group_id: str, artifact_id: str) -> int:
        """Get dependent count for a Maven package from libraries.io."""
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/maven/{quote(group_id)}/{quote(artifact_id)}/dependent-repositories"
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(
                "maven_dependents_fetch_failed",
                package=f"{group_id}:{artifact_id}",
                error=str(e),
            )
        return 0

    def get_dependents(
        self, language: Language, package_name: str, **kwargs: Any
    ) -> int:
        """Get dependent count for a package based on its language."""
        match language:
            case Language.PYTHON:
                return self.get_pypi_dependents(package_name)
            case Language.JAVASCRIPT | Language.TYPESCRIPT:
                return self.get_npm_dependents(package_name)
            case Language.RUST:
                return self.get_crates_dependents(package_name)
            case Language.JAVA:
                group_id = kwargs.get("group_id", "")
                artifact_id = kwargs.get("artifact_id", package_name)
                return self.get_maven_dependents(group_id, artifact_id)
            case _:
                logger.warning(
                    "unsupported_language_for_dependents", language=language.value
                )
                return 0

    def get_go_dependents(self, package_name: str) -> int:
        """Get dependent count for a Go package from libraries.io."""
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/go/{quote(package_name)}/dependent-repositories"
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return len(data) if isinstance(data, list) else 0
        except Exception as e:
            logger.warning(
                "go_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def search_popular_packages(
        self, language: Language, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Search for popular packages by language from libraries.io."""
        try:
            client = self._get_client()
            platform_map = {
                Language.PYTHON: "pypi",
                Language.JAVASCRIPT: "npm",
                Language.TYPESCRIPT: "npm",
                Language.GO: "go",
                Language.RUST: "cratesio",
                Language.JAVA: "maven",
            }
            platform = platform_map.get(language)
            if not platform:
                return []

            url = f"https://libraries.io/api/platforms/{platform}/top"
            response = client.get(url, params={"limit": limit})
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(
                "popular_packages_fetch_failed", language=language.value, error=str(e)
            )
        return []


class DependentFinder:
    """Find dependent packages for a given repository."""

    def __init__(self, registry_client: PackageRegistryClient | None = None) -> None:
        self.registry_client = registry_client or PackageRegistryClient()

    def find_dependents_from_repo(
        self, repo_name: str, language: Language | None
    ) -> int:
        """Find dependent count by analyzing repository metadata."""
        if not language:
            return 0

        # For GitHub repos, try to infer package name
        package_name = repo_name.split("/")[-1]

        match language:
            case Language.PYTHON:
                return self.registry_client.get_pypi_dependents(package_name)
            case Language.JAVASCRIPT | Language.TYPESCRIPT:
                return self.registry_client.get_npm_dependents(package_name)
            case Language.GO:
                # Go packages use full import path
                return self.registry_client.get_go_dependents(f"github.com/{repo_name}")
            case Language.RUST:
                return self.registry_client.get_crates_dependents(package_name)
            case Language.JAVA:
                # Maven uses group:artifact format
                return self.registry_client.get_maven_dependents("", package_name)
            case _:
                return 0
