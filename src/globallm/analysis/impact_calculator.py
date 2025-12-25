"""Impact score calculation using dependency graph metrics."""

from dataclasses import dataclass

from globallm.analysis.dependency_graph import DependencyGraphAnalyzer, GraphMetrics
from globallm.logging_config import get_logger
from globallm.models.repository import Language, RepoCandidate

logger = get_logger(__name__)


@dataclass
class ImpactScore:
    """Comprehensive impact score for a repository."""

    overall: float
    pagerank: float
    centrality: float
    downstream_reach: int
    normalized_downstream: float
    stars_factor: float
    dependents_factor: float

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "overall": self.overall,
            "pagerank": self.pagerank,
            "centrality": self.centrality,
            "downstream_reach": self.downstream_reach,
            "normalized_downstream": self.normalized_downstream,
            "stars_factor": self.stars_factor,
            "dependents_factor": self.dependents_factor,
        }


class ImpactCalculator:
    """Calculate impact scores for repositories.

    Combines:
    - Dependency graph metrics (PageRank, centrality, downstream reach)
    - Popularity metrics (stars, dependents)
    """

    def __init__(
        self,
        graph_analyzer: DependencyGraphAnalyzer | None = None,
        pagerank_weight: float = 0.35,
        centrality_weight: float = 0.15,
        downstream_weight: float = 0.20,
        stars_weight: float = 0.15,
        dependents_weight: float = 0.15,
    ) -> None:
        self.graph_analyzer = graph_analyzer or DependencyGraphAnalyzer()
        self.pagerank_weight = pagerank_weight
        self.centrality_weight = centrality_weight
        self.downstream_weight = downstream_weight
        self.stars_weight = stars_weight
        self.dependents_weight = dependents_weight

        # Normalization factors (for scaling to 0-1 range)
        self._max_stars_seen = 0
        self._max_dependents_seen = 0

    def calculate_impact(
        self,
        repo: RepoCandidate,
        metrics: GraphMetrics | None = None,
    ) -> ImpactScore:
        """Calculate comprehensive impact score for a repository.

        Args:
            repo: Repository candidate to score
            metrics: Pre-calculated graph metrics (optional)

        Returns:
            ImpactScore with all components
        """
        if not repo.language:
            logger.warning("impact_calc_no_language", repo=repo.name)
            return self._fallback_impact(repo)

        # Get graph metrics
        if metrics is None:
            metrics = self.graph_analyzer.get_metrics(repo.language)

        # Extract graph-based scores
        pagerank = 0.0
        centrality = 0.0
        downstream = 0
        normalized_downstream = 0.0

        if metrics:
            # Use package name (last part of repo name)
            package_name = repo.name.split("/")[-1]
            pagerank = metrics.pagerank.get(package_name, 0.0)
            centrality = metrics.betweenness_centrality.get(package_name, 0.0)
            downstream = metrics.downstream_reach.get(package_name, 0)

            # Normalize downstream
            max_downstream = (
                max(metrics.downstream_reach.values())
                if metrics.downstream_reach
                else 1
            )
            normalized_downstream = (
                downstream / max_downstream if max_downstream > 0 else 0.0
            )

        # Update normalization factors
        self._max_stars_seen = max(self._max_stars_seen, repo.stars)
        self._max_dependents_seen = max(self._max_dependents_seen, repo.dependents)

        # Normalize popularity metrics
        normalized_stars = (
            repo.stars / self._max_stars_seen if self._max_stars_seen > 0 else 0
        )
        normalized_dependents = (
            repo.dependents / self._max_dependents_seen
            if self._max_dependents_seen > 0
            else 0
        )

        # Calculate weighted overall score
        overall = (
            pagerank * self.pagerank_weight
            + centrality * self.centrality_weight
            + normalized_downstream * self.downstream_weight
            + normalized_stars * self.stars_weight
            + normalized_dependents * self.dependents_weight
        )

        return ImpactScore(
            overall=overall,
            pagerank=pagerank,
            centrality=centrality,
            downstream_reach=downstream,
            normalized_downstream=normalized_downstream,
            stars_factor=normalized_stars,
            dependents_factor=normalized_dependents,
        )

    def _fallback_impact(self, repo: RepoCandidate) -> ImpactScore:
        """Calculate impact without graph metrics.

        Uses only stars and dependents.
        """
        self._max_stars_seen = max(self._max_stars_seen, repo.stars)
        self._max_dependents_seen = max(self._max_dependents_seen, repo.dependents)

        normalized_stars = (
            repo.stars / self._max_stars_seen if self._max_stars_seen > 0 else 0
        )
        normalized_dependents = (
            repo.dependents / self._max_dependents_seen
            if self._max_dependents_seen > 0
            else 0
        )

        # Recalculate weights proportionally
        total_weight = self.stars_weight + self.dependents_weight
        star_w = self.stars_weight / total_weight
        dep_w = self.dependents_weight / total_weight

        overall = normalized_stars * star_w + normalized_dependents * dep_w

        return ImpactScore(
            overall=overall,
            pagerank=0.0,
            centrality=0.0,
            downstream_reach=repo.dependents,
            normalized_downstream=normalized_dependents,
            stars_factor=normalized_stars,
            dependents_factor=normalized_dependents,
        )

    def calculate_batch(
        self, repos: list[RepoCandidate], language: Language
    ) -> list[tuple[RepoCandidate, ImpactScore]]:
        """Calculate impact scores for multiple repositories.

        Args:
            repos: List of repository candidates
            language: Language for graph metrics

        Returns:
            List of (repo, impact_score) tuples sorted by overall impact
        """
        logger.info(
            "calculating_batch_impact", count=len(repos), language=language.value
        )

        # Build/analyze graph if needed
        if self.graph_analyzer.get_metrics(language) is None:
            self.graph_analyzer.analyze_language(language)

        metrics = self.graph_analyzer.get_metrics(language)

        # Calculate scores
        results = []
        for repo in repos:
            impact = self.calculate_impact(repo, metrics)
            results.append((repo, impact))

        # Sort by overall impact
        results.sort(key=lambda x: x[1].overall, reverse=True)

        logger.info("batch_impact_complete", count=len(results))
        return results

    def rank_repos(
        self, repos: list[RepoCandidate], language: Language
    ) -> list[RepoCandidate]:
        """Rank repositories by impact score.

        Args:
            repos: List of repository candidates
            language: Language for graph metrics

        Returns:
            Repositories sorted by impact score (highest first)
        """
        results = self.calculate_batch(repos, language)
        return [repo for repo, _ in results]
