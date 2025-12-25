"""GitHub repository scanner."""

from github import Github
from github.Repository import Repository
from github.GithubException import GithubException
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from hashlib import sha256
import yaml

from globallm.logging_config import get_logger

logger = get_logger(__name__)


class Domain(Enum):
    """Predefined search domains."""

    OVERALL = "overall"
    AI_ML = "ai_ml"
    WEB_DEV = "web_dev"
    DATA_SCIENCE = "data_science"
    CLOUD_DEVOPS = "cloud_devops"
    MOBILE = "mobile"
    SECURITY = "security"
    GAMES = "games"


DOMAIN_QUERIES: dict[Domain, str] = {
    Domain.OVERALL: "stars:>1000",
    Domain.AI_ML: "machine learning OR ai OR deep learning OR llm OR transformer",
    Domain.WEB_DEV: "web framework OR frontend OR backend OR fullstack OR api",
    Domain.DATA_SCIENCE: "data science OR analytics OR visualization OR pandas OR numpy",
    Domain.CLOUD_DEVOPS: "kubernetes OR docker OR terraform OR devops OR cicd",
    Domain.MOBILE: "android OR ios OR react native OR flutter OR mobile",
    Domain.SECURITY: "security OR cybersecurity OR penetration testing OR authentication",
    Domain.GAMES: "game engine OR unity OR unreal OR game development OR pygame",
}


@dataclass
class RepoMetrics:
    """Repository impact metrics."""

    name: str
    stars: int
    forks: int
    open_issues: int
    watchers: int
    language: str | None
    score: float

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        d = asdict(self)
        d["language"] = self.language
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RepoMetrics":
        """Create from dictionary for YAML deserialization."""
        return cls(**data)


class CacheEntry:
    """Cache entry for search results."""

    def __init__(self, results: list[RepoMetrics], ttl_hours: int = 24) -> None:
        self.results = results
        self.ttl_hours = ttl_hours

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return False

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "results": [r.to_dict() for r in self.results],
            "ttl_hours": self.ttl_hours,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Create from dictionary for YAML deserialization."""
        return cls(
            results=[RepoMetrics.from_dict(r) for r in data["results"]],
            ttl_hours=data.get("ttl_hours", 24),
        )


class GitHubScanner:
    """Scan GitHub repositories for impact metrics."""

    CACHE_DIR = Path.home() / ".cache" / "globallm"
    DEFAULT_CACHE_TTL_HOURS = 24

    def __init__(
        self,
        token: str | None = None,
        cache_dir: Path | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize scanner with optional GitHub token."""
        settings = {
            "per_page": 100,
        }
        self.github = Github(token, **settings) if token else Github(**settings)
        self.authenticated = bool(token)
        self.cache_dir = cache_dir or self.CACHE_DIR
        self.use_cache = use_cache
        if self.authenticated:
            logger.debug("scanner_initialized", authenticated=True)
        else:
            logger.debug("scanner_initialized", authenticated=False)

    def _cache_key(self, *args: str | int | None) -> str:
        """Generate cache key from arguments."""
        key_str = "|".join(str(a) for a in args if a is not None)
        return sha256(key_str.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{key}.yaml"

    def _load_cache(self, key: str) -> CacheEntry | None:
        """Load cached results if available."""
        if not self.use_cache:
            return None
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            with path.open() as f:
                data = yaml.safe_load(f)
                entry = CacheEntry.from_dict(data)
                if not entry.is_expired():
                    logger.debug("cache_hit", key=key)
                    return entry
        except Exception as e:
            logger.warning("cache_load_failed", key=key, error=str(e))
        return None

    def _save_cache(self, key: str, entry: CacheEntry) -> None:
        """Save results to cache."""
        if not self.use_cache:
            return
        path = self._cache_path(key)
        try:
            with path.open("w") as f:
                yaml.dump(entry.to_dict(), f, default_flow_style=False)
            logger.debug("cache_saved", key=key)
        except Exception as e:
            logger.warning("cache_save_failed", key=key, error=str(e))

    def clear_cache(self) -> None:
        """Clear all cached results."""
        if self.cache_dir.exists():
            for path in self.cache_dir.glob("*.yaml"):
                path.unlink()
            logger.info("cache_cleared")

    def analyze_repo(self, repo_name: str) -> RepoMetrics:
        """Analyze a single repository."""
        logger.debug("analyzing_repo", repo=repo_name)
        try:
            repo = self.github.get_repo(repo_name)
            metrics = self._calculate_metrics(repo)
            logger.debug(
                "repo_analyzed",
                repo=repo_name,
                stars=metrics.stars,
                score=f"{metrics.score:.1f}",
            )
            return metrics
        except GithubException as e:
            logger.error("repo_analysis_failed", repo=repo_name, error=str(e))
            raise

    def search_repos(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        max_results: int = 100,
    ) -> list[RepoMetrics]:
        """Search repositories and return metrics."""
        key = self._cache_key(query, sort, order, max_results)

        logger.debug("cache_check", key=key)
        cached = self._load_cache(key)
        if cached:
            logger.info("cache_hit", query=query, result_count=len(cached.results))
            return cached.results

        logger.debug("cache_miss", key=key)
        logger.info(
            "searching_repos",
            query=query,
            sort=sort,
            order=order,
            max_results=max_results,
        )

        repos = self.github.search_repositories(query=query, sort=sort, order=order)
        results: list[RepoMetrics] = []
        failed_count = 0

        for i, repo in enumerate(repos[:max_results], 1):
            logger.debug(
                "processing_repo",
                index=i,
                total=max_results,
                name=repo.full_name,
            )
            try:
                metrics = self._calculate_metrics(repo)
                results.append(metrics)
                logger.debug(
                    "repo_processed",
                    name=repo.full_name,
                    score=f"{metrics.score:.1f}",
                )
            except GithubException as e:
                failed_count += 1
                logger.warning(
                    "repo_processing_failed",
                    repo=repo.full_name,
                    error=str(e),
                )
                continue

        logger.info(
            "repos_fetched",
            successful=len(results),
            failed=failed_count,
            total=max_results,
        )

        results = sorted(results, key=lambda r: r.score, reverse=True)
        logger.debug("results_sorted", count=len(results))

        self._save_cache(key, CacheEntry(results))

        if results:
            logger.info(
                "top_results",
                first=results[0].name,
                first_score=f"{results[0].score:.1f}",
            )

        return results

    def search_by_domain(
        self,
        domain: Domain,
        language: str | None = None,
        sort: str = "stars",
        order: str = "desc",
        max_results: int = 100,
    ) -> list[RepoMetrics]:
        """Search repositories by domain."""
        query = DOMAIN_QUERIES[domain]
        if language:
            lang_filter = f"language:{language}"
            query = f"{query} {lang_filter}" if query else lang_filter
        logger.debug("domain_search_query", domain=domain.value, query=query)
        return self.search_repos(query, sort, order, max_results)

    def analyze_user_repos(
        self,
        username: str,
        min_stars: int = 0,
        include_forks: bool = False,
        max_results: int = 100,
    ) -> list[RepoMetrics]:
        """Analyze all repositories owned by a user.

        Args:
            username: GitHub username
            min_stars: Minimum star count to include
            include_forks: Whether to include forked repositories
            max_results: Maximum results to return

        Returns:
            List of RepoMetrics for the user's repositories, sorted by score
        """
        logger.info(
            "analyzing_user_repos",
            username=username,
            min_stars=min_stars,
            include_forks=include_forks,
        )

        try:
            user = self.github.get_user(username)
            repos = user.get_repos()

            results: list[RepoMetrics] = []

            for repo in repos[:max_results]:
                # Skip forks if not requested
                if not include_forks and repo.fork:
                    logger.debug("skipping_fork", repo=repo.full_name)
                    continue

                # Skip if below star threshold
                if repo.stargazers_count < min_stars:
                    logger.debug(
                        "skipping_low_stars",
                        repo=repo.full_name,
                        stars=repo.stargazers_count,
                    )
                    continue

                try:
                    metrics = self._calculate_metrics(repo)
                    results.append(metrics)
                    logger.debug(
                        "repo_analyzed",
                        name=repo.full_name,
                        stars=metrics.stars,
                        score=f"{metrics.score:.1f}",
                    )
                except GithubException as e:
                    logger.warning(
                        "repo_analysis_failed",
                        repo=repo.full_name,
                        error=str(e),
                    )
                    continue

            # Sort by score (impact)
            results = sorted(results, key=lambda r: r.score, reverse=True)

            logger.info(
                "user_repos_analyzed",
                username=username,
                total_found=len(results),
            )

            return results

        except GithubException as e:
            logger.error("user_analysis_failed", username=username, error=str(e))
            raise

    def _calculate_metrics(self, repo: Repository) -> RepoMetrics:
        """Calculate impact score for a repository."""
        # Weighted score formula
        score = (
            repo.stargazers_count * 1.0
            + repo.forks_count * 2.0
            + repo.open_issues_count * 0.1
            + repo.watchers_count * 5.0
        )

        return RepoMetrics(
            name=repo.full_name,
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            open_issues=repo.open_issues_count,
            watchers=repo.watchers_count,
            language=repo.language,
            score=score,
        )
