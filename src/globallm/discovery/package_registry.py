"""Package registry integration for dependency data.

NOTE: As of 2025-12-25, libraries.io has disabled the dependents endpoints
for performance reasons. API calls to /dependents or /dependent-repositories
will return {"message":"Disabled for performance reasons"}.

Alternative approaches for getting dependent counts:
1. Use GitHub's "Used by" / "Dependents" feature (available for some packages)
2. Use package registry specific APIs (PyPI, npm, etc.)
"""

from urllib.parse import quote
from typing import Any

import httpx

from globallm.models.repository import Language
from globallm.logging_config import get_logger

logger = get_logger(__name__)

# Flag to track if we've logged the libraries.io limitation
_libraries_io_warning_logged = False


class PackageRegistryClient:
    """Client for fetching package data from various registries."""

    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _get_params(self) -> dict[str, str]:
        """Get query parameters including API key if available."""
        params = {}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _check_disabled_response(
        self, data: dict | list, platform: str, package: str
    ) -> bool:
        """Check if the response indicates the endpoint is disabled."""
        global _libraries_io_warning_logged
        if (
            isinstance(data, dict)
            and data.get("message") == "Disabled for performance reasons"
        ):
            if not _libraries_io_warning_logged:
                logger.warning(
                    "libraries_io_dependents_disabled",
                    message="libraries.io has disabled the dependents endpoint for performance reasons",
                    hint="Consider using alternative data sources or filtering by stars/forks instead",
                )
                _libraries_io_warning_logged = True
            return True
        return False

    def get_pypi_dependents(self, package_name: str) -> int:
        """Get dependent count for a PyPI package from libraries.io.

        NOTE: This endpoint is currently disabled by libraries.io.
        """
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/pypi/{quote(package_name)}/dependent-repositories"
            response = client.get(url, params=self._get_params())
            if response.status_code == 200:
                data = response.json()
                if self._check_disabled_response(data, "pypi", package_name):
                    return 0
                return len(data) if isinstance(data, list) else 0
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "pypi_dependents_auth_required",
                    package=package_name,
                    hint="Set libraries_io_api_key in config",
                )
        except Exception as e:
            logger.warning(
                "pypi_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_npm_dependents(self, package_name: str) -> int:
        """Get dependent count for an npm package from libraries.io.

        NOTE: This endpoint is currently disabled by libraries.io.
        """
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/npm/{quote(package_name)}/dependent-repositories"
            response = client.get(url, params=self._get_params())
            if response.status_code == 200:
                data = response.json()
                if self._check_disabled_response(data, "npm", package_name):
                    return 0
                return len(data) if isinstance(data, list) else 0
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "npm_dependents_auth_required",
                    package=package_name,
                    hint="Set libraries_io_api_key in config",
                )
        except Exception as e:
            logger.warning(
                "npm_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_crates_dependents(self, package_name: str) -> int:
        """Get dependent count for a crates.io package from libraries.io.

        NOTE: This endpoint is currently disabled by libraries.io.
        """
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/cratesio/{quote(package_name)}/dependent-repositories"
            response = client.get(url, params=self._get_params())
            if response.status_code == 200:
                data = response.json()
                if self._check_disabled_response(data, "cratesio", package_name):
                    return 0
                return len(data) if isinstance(data, list) else 0
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "crates_dependents_auth_required",
                    package=package_name,
                    hint="Set libraries_io_api_key in config",
                )
        except Exception as e:
            logger.warning(
                "crates_dependents_fetch_failed", package=package_name, error=str(e)
            )
        return 0

    def get_maven_dependents(self, group_id: str, artifact_id: str) -> int:
        """Get dependent count for a Maven package from libraries.io.

        NOTE: This endpoint is currently disabled by libraries.io.
        """
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/maven/{quote(group_id)}/{quote(artifact_id)}/dependent-repositories"
            response = client.get(url, params=self._get_params())
            if response.status_code == 200:
                data = response.json()
                if self._check_disabled_response(
                    data, "maven", f"{group_id}:{artifact_id}"
                ):
                    return 0
                return len(data) if isinstance(data, list) else 0
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "maven_dependents_auth_required",
                    package=f"{group_id}:{artifact_id}",
                    hint="Set libraries_io_api_key in config",
                )
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
        """Get dependent count for a package based on its language.

        NOTE: The underlying libraries.io dependents endpoints are disabled.
        This method will return 0 for all packages until an alternative is found.
        """
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
        """Get dependent count for a Go package from libraries.io.

        NOTE: This endpoint is currently disabled by libraries.io.
        """
        try:
            client = self._get_client()
            url = f"https://libraries.io/api/go/{quote(package_name)}/dependent-repositories"
            response = client.get(url, params=self._get_params())
            if response.status_code == 200:
                data = response.json()
                if self._check_disabled_response(data, "go", package_name):
                    return 0
                return len(data) if isinstance(data, list) else 0
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "go_dependents_auth_required",
                    package=package_name,
                    hint="Set libraries_io_api_key in config",
                )
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
            params = {"limit": limit, **self._get_params()}
            response = client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else []
            elif response.status_code == 403 and not self.api_key:
                logger.warning(
                    "popular_packages_auth_required",
                    language=language.value,
                    hint="Set libraries_io_api_key in config",
                )
        except Exception as e:
            logger.warning(
                "popular_packages_fetch_failed", language=language.value, error=str(e)
            )
        return []


class DependentFinder:
    """Find dependent packages for a given repository.

    NOTE: The libraries.io dependents API has been disabled. This class
    remains for compatibility but will return 0 for all dependent counts.
    """

    def __init__(
        self,
        api_key: str | None = None,
        registry_client: PackageRegistryClient | None = None,
    ) -> None:
        if registry_client:
            self.registry_client = registry_client
        else:
            self.registry_client = PackageRegistryClient(api_key=api_key)

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
