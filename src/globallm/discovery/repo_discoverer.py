"""Enhanced repository discoverer with language-specific queries."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from globallm.config.loader import load_config
from globallm.discovery.package_registry import DependentFinder
from globallm.filtering.health_scorer import HealthScorer
from globallm.filtering.repo_filter import RepositoryFilter
from globallm.logging_config import get_logger
from globallm.models.repository import Language, RepoCandidate
from globallm.scanner import GitHubScanner

if TYPE_CHECKING:
    from github import Github

logger = get_logger(__name__)


@dataclass
class DiscoveryResult:
    """Result from a repository discovery operation."""

    candidates: list[RepoCandidate]
    total_found: int
    filtered_out: int
    language: Language | None = None
    query: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_found == 0:
            return 0.0
        return len(self.candidates) / self.total_found


class EnhancedDiscoverer(GitHubScanner):
    """Enhanced repository discoverer with language-specific queries."""

    def __init__(
        self,
        github_client: Github,
        enable_dependent_lookup: bool = True,
        health_filter: bool = True,
    ) -> None:
        super().__init__(github_client)
        # Load config to get libraries.io API key
        config = load_config()
        api_key = config.libraries_io_api_key

        self.dependent_finder = (
            DependentFinder(api_key=api_key) if enable_dependent_lookup else None
        )
        self.health_scorer = HealthScorer()
        self.repo_filter = RepositoryFilter(self.health_scorer)
        self.enable_dependent_lookup = enable_dependent_lookup
        self.health_filter = health_filter

    def discover_by_language(
        self,
        language: Language,
        min_stars: int = 1000,
        min_dependents: int = 100,
        max_results: int = 100,
    ) -> DiscoveryResult:
        """Discover repositories for a specific language.

        Args:
            language: Programming language to search
            min_stars: Minimum star count
            min_dependents: Minimum dependent packages
            max_results: Maximum results to return

        Returns:
            DiscoveryResult with filtered candidates
        """
        logger.info(
            "discovering_by_language",
            language=language.value,
            min_stars=min_stars,
            min_dependents=min_dependents,
        )

        # Build language-specific query
        query = self._build_language_query(language, min_stars)
        logger.debug("language_query", query=query)

        # Search repositories
        raw_results = self.search_repos(query, max_results=max_results * 2)

        # Convert to RepoCandidates with language detection
        candidates = self._convert_to_candidates(raw_results, language)

        # Fetch dependent counts
        if self.dependent_finder:
            candidates = self._enrich_with_dependents(candidates, language)

        # Apply health filtering
        if self.health_filter:
            candidates = self.repo_filter.filter_by_health(candidates)

        # Apply threshold filtering
        filtered = [
            c
            for c in candidates
            if c.stars >= min_stars and c.dependents >= min_dependents
        ]

        total_found = len(candidates)
        filtered_out = total_found - len(filtered)

        logger.info(
            "discovery_complete",
            language=language.value,
            found=total_found,
            passed=len(filtered),
            filtered=filtered_out,
        )

        return DiscoveryResult(
            candidates=filtered,
            total_found=total_found,
            filtered_out=filtered_out,
            language=language,
            query=query,
        )

    def _build_language_query(self, language: Language, min_stars: int) -> str:
        """Build a language-specific search query."""
        base_query = f"stars:>={min_stars} language:{language.value}"

        # Add language-specific quality indicators
        quality_terms = {
            Language.PYTHON: "pytest OR unittest OR testing",
            Language.JAVASCRIPT: "jest OR mocha OR testing",
            Language.TYPESCRIPT: "jest OR vitest OR testing",
            Language.GO: "testing OR test",
            Language.RUST: "testing OR cargo test",
            Language.JAVA: "junit OR testing OR maven",
        }

        if language in quality_terms:
            return f'{base_query} "{quality_terms[language]}"'

        return base_query

    def _convert_to_candidates(
        self, metrics_list: list, language: Language | None
    ) -> list[RepoCandidate]:
        """Convert scanner metrics to RepoCandidates."""
        candidates = []
        for metrics in metrics_list:
            # Detect language if not specified
            detected_lang = language
            if not detected_lang and metrics.language:
                detected_lang = Language.from_string(metrics.language)

            candidates.append(
                RepoCandidate(
                    name=metrics.name,
                    stars=metrics.stars,
                    forks=metrics.forks,
                    open_issues=metrics.open_issues,
                    watchers=metrics.watchers,
                    subscribers=0,  # Will be fetched if needed
                    language=detected_lang,
                    description=None,
                    last_commit_at=None,
                    created_at=None,
                    dependents=0,  # Will be enriched
                )
            )
        return candidates

    def _enrich_with_dependents(
        self, candidates: list[RepoCandidate], language: Language
    ) -> list[RepoCandidate]:
        """Enrich candidates with dependent counts."""
        logger.info("enriching_dependents", count=len(candidates))
        for i, candidate in enumerate(candidates):
            if candidate.dependents > 0:
                continue  # Already has data

            logger.debug("fetching_dependents", repo=candidate.name, index=i)
            dependents = self.dependent_finder.find_dependents_from_repo(
                candidate.name, language
            )
            candidate.dependents = dependents

        return candidates

    def analyze_repo_full(self, repo_name: str) -> RepoCandidate:
        """Fully analyze a repository with health scoring."""
        logger.info("analyzing_repo_full", repo=repo_name)

        # Get detailed repo info
        try:
            repo = self.github.get_repo(repo_name)

            # Detect language
            detected_lang = (
                Language.from_string(repo.language) if repo.language else None
            )

            # Calculate health score
            health_score = None
            if self.health_scorer:
                health_score = self.health_scorer.calculate_health_score(repo)

            candidate = RepoCandidate(
                name=repo.full_name,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                open_issues=repo.open_issues_count,
                watchers=repo.subscribers_count,
                subscribers=repo.subscribers_count,
                language=detected_lang,
                description=repo.description,
                last_commit_at=datetime.now(tz=None),  # Would need commit API
                created_at=repo.created_at,
                dependents=0,  # Would be fetched separately
                health_score=health_score,
            )

            logger.info(
                "repo_analysis_complete",
                repo=repo_name,
                stars=candidate.stars,
                health=f"{health_score.overall:.2f}" if health_score else None,
            )

            return candidate

        except Exception as e:
            logger.error("repo_analysis_failed", repo=repo_name, error=str(e))
            raise
