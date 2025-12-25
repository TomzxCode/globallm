"""Dependency graph construction and analysis."""

from dataclasses import dataclass

import networkx as nx

from globallm.logging_config import get_logger
from globallm.models.repository import Language

logger = get_logger(__name__)


@dataclass
class GraphMetrics:
    """Metrics calculated from dependency graph."""

    pagerank: dict[str, float]
    betweenness_centrality: dict[str, float]
    in_degree: dict[str, int]
    out_degree: dict[str, int]
    downstream_reach: dict[str, int]

    def get_top_nodes(
        self, metric: str = "pagerank", limit: int = 10
    ) -> list[tuple[str, float]]:
        """Get top nodes by metric."""
        match metric:
            case "pagerank":
                data = self.pagerank
            case "betweenness":
                data = self.betweenness_centrality
            case "in_degree":
                data = {k: float(v) for k, v in self.in_degree.items()}
            case "out_degree":
                data = {k: float(v) for k, v in self.out_degree.items()}
            case "downstream":
                data = {k: float(v) for k, v in self.downstream_reach.items()}
            case _:
                data = self.pagerank

        return sorted(data.items(), key=lambda x: x[1], reverse=True)[:limit]


class DependencyGraphBuilder:
    """Build dependency graphs for different ecosystems."""

    def __init__(self) -> None:
        self._graphs: dict[Language, nx.DiGraph] = {}

    def build_python_graph(
        self, packages: list[str] | None = None, max_depth: int = 2
    ) -> nx.DiGraph:
        """Build Python dependency graph.

        Args:
            packages: Seed packages to start from. If None, uses common packages.
            max_depth: Maximum depth to traverse dependencies.

        Returns:
            Directed graph of package dependencies.
        """
        logger.info(
            "building_python_graph", seed_count=len(packages) if packages else 0
        )

        graph = nx.DiGraph()

        # Common seed packages if none provided
        if packages is None:
            packages = [
                "requests",
                "django",
                "flask",
                "numpy",
                "pandas",
                "pytest",
                "click",
                "pydantic",
                "fastapi",
                "sqlalchemy",
            ]

        # Try to use importlib.metadata for local dependencies
        try:
            self._build_python_from_metadata(graph, packages, max_depth)
        except Exception as e:
            logger.warning("python_metadata_build_failed", error=str(e))
            # Fallback to hardcoded relationships
            self._build_python_stub_graph(graph, packages)

        logger.info(
            "python_graph_built",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
        )
        self._graphs[Language.PYTHON] = graph
        return graph

    def _build_python_from_metadata(
        self, graph: nx.DiGraph, packages: list[str], max_depth: int
    ) -> None:
        """Build graph using importlib.metadata."""
        try:
            from importlib.metadata import distributions
        except ImportError:
            return

        # Get all installed packages
        dists = {d.metadata["Name"]: d for d in distributions()}

        # Build edges from dependencies
        for pkg_name in packages:
            if pkg_name not in dists:
                continue

            graph.add_node(pkg_name, language="python")

            dist = dists[pkg_name]
            for req in dist.requires or []:
                # Parse requirement name (remove version specs)
                req_name = req.split(">")[0].split("=")[0].split("<")[0].strip()
                if req_name in dists:
                    graph.add_node(req_name, language="python")
                    graph.add_edge(pkg_name, req_name)

    def _build_python_stub_graph(self, graph: nx.DiGraph, packages: list[str]) -> None:
        """Build a stub graph with known common dependencies."""
        # Common dependencies map
        dependencies = {
            "django": ["sqlalchemy", "pytz", "asgiref"],
            "flask": ["werkzeug", "jinja2", "click"],
            "fastapi": ["pydantic", "starlette", "click"],
            "pandas": ["numpy", "python-dateutil"],
            "pytest": ["pluggy", "py", "colorama"],
            "requests": ["urllib3", "certifi", "charset-normalizer"],
            "pydantic": ["typing-extensions", "annotated-types"],
            "sqlalchemy": ["typing-extensions"],
            "numpy": [],
            "click": [],
        }

        for pkg in packages:
            graph.add_node(pkg, language="python")
            for dep in dependencies.get(pkg, []):
                graph.add_node(dep, language="python")
                graph.add_edge(pkg, dep)

    def build_javascript_graph(self, packages: list[str] | None = None) -> nx.DiGraph:
        """Build JavaScript/TypeScript dependency graph.

        Args:
            packages: Seed packages. If None, uses common packages.

        Returns:
            Directed graph of npm package dependencies.
        """
        logger.info("building_javascript_graph")

        graph = nx.DiGraph()

        if packages is None:
            packages = [
                "react",
                "vue",
                "angular",
                "lodash",
                "axios",
                "express",
                "typescript",
                "vite",
                "webpack",
                "jest",
            ]

        # Stub implementation with known dependencies
        dependencies = {
            "react": [],
            "vue": [],
            "angular": ["rxjs", "zone.js"],
            "lodash": [],
            "axios": [],
            "express": [],
            "typescript": [],
            "vite": ["esbuild"],
            "webpack": [],
            "jest": [],
        }

        for pkg in packages:
            graph.add_node(pkg, language="javascript")
            for dep in dependencies.get(pkg, []):
                graph.add_node(dep, language="javascript")
                graph.add_edge(pkg, dep)

        logger.info(
            "javascript_graph_built",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
        )
        self._graphs[Language.JAVASCRIPT] = graph
        return graph

    def build_go_graph(self, packages: list[str] | None = None) -> nx.DiGraph:
        """Build Go dependency graph.

        Args:
            packages: Seed packages. If None, uses common packages.

        Returns:
            Directed graph of Go module dependencies.
        """
        logger.info("building_go_graph")

        graph = nx.DiGraph()

        if packages is None:
            packages = [
                "github.com/golang/go",
                "github.com/gin-gonic/gin",
                "github.com/gorilla/mux",
                "github.com/stretchr/testify",
                "google.golang.org/grpc",
                "k8s.io/client-go",
            ]

        for pkg in packages:
            graph.add_node(pkg, language="go")

        logger.info(
            "go_graph_built",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
        )
        self._graphs[Language.GO] = graph
        return graph

    def build_rust_graph(self, packages: list[str] | None = None) -> nx.DiGraph:
        """Build Rust dependency graph.

        Args:
            packages: Seed packages. If None, uses common packages.

        Returns:
            Directed graph of crate dependencies.
        """
        logger.info("building_rust_graph")

        graph = nx.DiGraph()

        if packages is None:
            packages = [
                "serde",
                "tokio",
                "clap",
                "rayon",
                "anyhow",
                "thiserror",
                "tracing",
                "axum",
                "reqwest",
                "rand",
            ]

        # Stub implementation
        dependencies = {
            "tokio": [],
            "axum": ["tokio"],
            "serde": [],
            "clap": [],
            "rayon": [],
            "anyhow": [],
            "thiserror": [],
            "tracing": [],
            "reqwest": ["tokio"],
            "rand": [],
        }

        for pkg in packages:
            graph.add_node(pkg, language="rust")
            for dep in dependencies.get(pkg, []):
                graph.add_node(dep, language="rust")
                graph.add_edge(pkg, dep)

        logger.info(
            "rust_graph_built",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
        )
        self._graphs[Language.RUST] = graph
        return graph

    def build_graph(
        self, language: Language, packages: list[str] | None = None
    ) -> nx.DiGraph:
        """Build dependency graph for a language.

        Args:
            language: Programming language
            packages: Seed packages

        Returns:
            Directed graph of dependencies
        """
        match language:
            case Language.PYTHON:
                return self.build_python_graph(packages)
            case Language.JAVASCRIPT | Language.TYPESCRIPT:
                return self.build_javascript_graph(packages)
            case Language.GO:
                return self.build_go_graph(packages)
            case Language.RUST:
                return self.build_rust_graph(packages)
            case _:
                logger.warning("unsupported_language", language=language.value)
                return nx.DiGraph()

    def get_graph(self, language: Language) -> nx.DiGraph | None:
        """Get cached graph for language."""
        return self._graphs.get(language)


class DependencyGraphAnalyzer:
    """Analyze dependency graphs for impact metrics."""

    def __init__(self, builder: DependencyGraphBuilder | None = None) -> None:
        self.builder = builder or DependencyGraphBuilder()
        self._metrics: dict[Language, GraphMetrics] = {}

    def calculate_pagerank(
        self, graph: nx.DiGraph, alpha: float = 0.85
    ) -> dict[str, float]:
        """Calculate PageRank for all nodes.

        Higher PageRank = more important in dependency network.

        Args:
            graph: Dependency graph
            alpha: Damping parameter

        Returns:
            Dict mapping node names to PageRank scores
        """
        logger.debug("calculating_pagerank", nodes=graph.number_of_nodes())
        return nx.pagerank(graph, alpha=alpha)

    def calculate_betweenness_centrality(self, graph: nx.DiGraph) -> dict[str, float]:
        """Calculate betweenness centrality.

        Higher values = more control over information flow.
        These are bridge packages between clusters.

        Args:
            graph: Dependency graph

        Returns:
            Dict mapping node names to centrality scores
        """
        logger.debug("calculating_betweenness", nodes=graph.number_of_nodes())
        return nx.betweenness_centrality(graph)

    def get_downstream_reach(self, graph: nx.DiGraph, node: str) -> int:
        """Count unique downstream packages for a node.

        Args:
            graph: Dependency graph
            node: Node to analyze

        Returns:
            Count of unique downstream packages
        """
        try:
            descendants = nx.descendants(graph, node)
            return len(descendants)
        except nx.NetworkXError:
            return 0

    def calculate_all_downstream_reach(self, graph: nx.DiGraph) -> dict[str, int]:
        """Calculate downstream reach for all nodes.

        Args:
            graph: Dependency graph

        Returns:
            Dict mapping node names to downstream counts
        """
        return {node: self.get_downstream_reach(graph, node) for node in graph.nodes()}

    def analyze_graph(
        self, graph: nx.DiGraph, language: Language | None = None
    ) -> GraphMetrics:
        """Perform comprehensive graph analysis.

        Args:
            graph: Dependency graph to analyze
            language: Language for caching

        Returns:
            GraphMetrics with all calculated metrics
        """
        logger.info(
            "analyzing_graph",
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
        )

        pagerank = self.calculate_pagerank(graph)
        betweenness = self.calculate_betweenness_centrality(graph)
        downstream = self.calculate_all_downstream_reach(graph)
        in_degree = dict(graph.in_degree())
        out_degree = dict(graph.out_degree())

        metrics = GraphMetrics(
            pagerank=pagerank,
            betweenness_centrality=betweenness,
            in_degree=in_degree,
            out_degree=out_degree,
            downstream_reach=downstream,
        )

        if language:
            self._metrics[language] = metrics

        return metrics

    def analyze_language(self, language: Language) -> GraphMetrics:
        """Analyze dependency graph for a language.

        Args:
            language: Language to analyze

        Returns:
            GraphMetrics for the language
        """
        graph = self.builder.build_graph(language)
        return self.analyze_graph(graph, language)

    def get_metrics(self, language: Language) -> GraphMetrics | None:
        """Get cached metrics for a language."""
        return self._metrics.get(language)

    def get_node_impact(self, node: str, language: Language) -> float:
        """Get composite impact score for a node.

        Combines PageRank and downstream reach.

        Args:
            node: Package/repository name
            language: Programming language

        Returns:
            Impact score
        """
        metrics = self.get_metrics(language)
        if not metrics:
            return 0.0

        pagerank = metrics.pagerank.get(node, 0.0)
        downstream = metrics.downstream_reach.get(node, 0)

        # Weighted combination: PageRank (0-1) + normalized downstream reach
        max_downstream = (
            max(metrics.downstream_reach.values()) if metrics.downstream_reach else 1
        )
        normalized_downstream = downstream / max_downstream if max_downstream > 0 else 0

        return pagerank * 0.6 + normalized_downstream * 0.4
