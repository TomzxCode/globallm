"""Redundancy detection for identifying duplicate projects."""

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any

import numpy as np

from globallm.logging_config import get_logger

logger = get_logger(__name__)


class RedundancyReason(Enum):
    """Reason for redundancy flag."""

    SIMILAR_README = "similar_readme"
    IDENTICAL_API = "identical_api"
    SIMILAR_API = "similar_api"
    FORK_ABANDONED = "fork_abandoned"
    STALE_CANDIDATE = "stale_candidate"


@dataclass
class RedundancyReport:
    """Report on redundant projects."""

    repo_a: str
    repo_b: str
    similarity_score: float  # 0-1
    reason: RedundancyReason
    details: str = ""
    recommend_archive: str | None = None  # Which repo to archive

    @property
    def is_redundant(self) -> bool:
        """Check if this represents significant redundancy."""
        return self.similarity_score > 0.7


@dataclass
class APISignature:
    """Signature of a project's API."""

    module_names: list[str]
    function_names: list[str]
    class_names: list[str]
    public_exports: int = 0

    @property
    def signature_vector(self) -> np.ndarray:
        """Create a vector representation of the API."""
        # Combine all identifiers
        all_names = self.module_names + self.function_names + self.class_names
        if not all_names:
            return np.zeros(100)

        # Simple hash-based embedding
        vector = np.zeros(100)
        for name in all_names:
            idx = hash(name) % 100
            vector[idx] += 1

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector


@dataclass
class ClusterResult:
    """Result of clustering similar projects."""

    cluster_id: int
    repositories: list[str]
    similarity_scores: dict[str, float]
    recommend_keep: str | None = None
    recommend_archive: list[str] = field(default_factory=list)


class RedundancyDetector:
    """Detect redundant projects for consolidation."""

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2") -> None:
        """Initialize redundancy detector.

        Args:
            embedding_model: Name of sentence-transformers model
        """
        self.embedding_model = embedding_model
        self._embedder = None

    @property
    def embedder(self):
        """Lazy-load the sentence transformer."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self.embedding_model)
                logger.info("embedder_loaded", model=self.embedding_model)
            except ImportError:
                logger.warning("sentence_transformers_not_available")
                self._embedder = False
        return self._embedder

    def compute_readme_similarity(self, readme_a: str, readme_b: str) -> float:
        """Compute similarity between two READMEs.

        Args:
            readme_a: First README text
            readme_b: Second README text

        Returns:
            Similarity score 0-1
        """
        if not readme_a or not readme_b:
            return 0.0

        embedder = self.embedder
        if embedder is False:
            # Fallback to simple word overlap
            return self._word_overlap_similarity(readme_a, readme_b)

        try:
            emb_a = embedder.encode(readme_a, convert_to_numpy=True)
            emb_b = embedder.encode(readme_b, convert_to_numpy=True)

            # Cosine similarity
            similarity = np.dot(emb_a, emb_b) / (
                np.linalg.norm(emb_a) * np.linalg.norm(emb_b)
            )
            return float(similarity)
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))
            return self._word_overlap_similarity(readme_a, readme_b)

    def _word_overlap_similarity(self, text_a: str, text_b: str) -> float:
        """Fallback similarity using word overlap."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union) if union else 0.0

    def compare_api_signatures(self, sig_a: APISignature, sig_b: APISignature) -> float:
        """Compare two API signatures.

        Args:
            sig_a: First API signature
            sig_b: Second API signature

        Returns:
            Similarity score 0-1
        """
        vec_a = sig_a.signature_vector
        vec_b = sig_b.signature_vector

        # Cosine similarity
        similarity = np.dot(vec_a, vec_b) / (
            np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        )

        return float(similarity)

    def detect_redundancy(
        self,
        repo_a: str,
        readme_a: str,
        api_sig_a: APISignature,
        stars_a: int,
        updated_a: str,
        repo_b: str,
        readme_b: str,
        api_sig_b: APISignature,
        stars_b: int,
        updated_b: str,
    ) -> RedundancyReport | None:
        """Detect if two repos are redundant.

        Args:
            repo_a: First repo name
            readme_a: First README text
            api_sig_a: First API signature
            stars_a: First repo star count
            updated_a: First repo last updated date
            repo_b: Second repo name
            readme_b: Second README text
            api_sig_b: Second API signature
            stars_b: Second repo star count
            updated_b: Second repo last updated date

        Returns:
            RedundancyReport if redundant, None otherwise
        """
        readme_sim = self.compute_readme_similarity(readme_a, readme_b)
        api_sim = self.compare_api_signatures(api_sig_a, api_sig_b)

        # Check for redundancy
        if readme_sim > 0.85:
            # Very similar READMEs
            recommend_archive = repo_b if stars_a >= stars_b else repo_a
            return RedundancyReport(
                repo_a=repo_a,
                repo_b=repo_b,
                similarity_score=readme_sim,
                reason=RedundancyReason.SIMILAR_README,
                details=f"READMEs are {readme_sim:.1%} similar",
                recommend_archive=recommend_archive,
            )

        if api_sim > 0.9:
            # Identical APIs
            recommend_archive = repo_b if stars_a >= stars_b else repo_a
            return RedundancyReport(
                repo_a=repo_a,
                repo_b=repo_b,
                similarity_score=api_sim,
                reason=RedundancyReason.IDENTICAL_API,
                details=f"API signatures are {api_sim:.1%} similar",
                recommend_archive=recommend_archive,
            )

        if api_sim > 0.75:
            # Similar APIs
            recommend_archive = repo_b if stars_a >= stars_b else repo_a
            return RedundancyReport(
                repo_a=repo_a,
                repo_b=repo_b,
                similarity_score=api_sim,
                reason=RedundancyReason.SIMILAR_API,
                details=f"API signatures are {api_sim:.1%} similar",
                recommend_archive=recommend_archive,
            )

        return None

    def cluster_repositories(
        self,
        repos: list[dict[str, Any]],
        similarity_threshold: float = 0.75,
    ) -> list[ClusterResult]:
        """Cluster repositories by similarity.

        Args:
            repos: List of repo dicts with name, readme, api_signature, stars
            similarity_threshold: Minimum similarity to cluster

        Returns:
            List of cluster results
        """
        if not repos:
            return []

        logger.info("clustering_repos", count=len(repos))

        # Simple clustering based on pairwise similarity
        clusters: list[ClusterResult] = []
        assigned = set()

        for i, repo_a in enumerate(repos):
            if repo_a["name"] in assigned:
                continue

            cluster_members = [repo_a["name"]]
            similarity_scores = {repo_a["name"]: 1.0}

            for j, repo_b in enumerate(repos):
                if i >= j:
                    continue
                if repo_b["name"] in assigned:
                    continue

                sig_a = repo_a.get("api_signature")
                sig_b = repo_b.get("api_signature")

                if sig_a is None or sig_b is None:
                    continue

                sim = self.compare_api_signatures(sig_a, sig_b)
                if sim >= similarity_threshold:
                    cluster_members.append(repo_b["name"])
                    similarity_scores[repo_b["name"]] = sim
                    assigned.add(repo_b["name"])

            # Determine which to keep
            if len(cluster_members) > 1:
                # Keep the one with most stars
                sorted_members = sorted(
                    cluster_members,
                    key=lambda n: next(r["stars"] for r in repos if r["name"] == n),
                    reverse=True,
                )
                recommend_keep = sorted_members[0]
                recommend_archive = sorted_members[1:]

                clusters.append(
                    ClusterResult(
                        cluster_id=len(clusters),
                        repositories=cluster_members,
                        similarity_scores=similarity_scores,
                        recommend_keep=recommend_keep,
                        recommend_archive=recommend_archive,
                    )
                )

            assigned.add(repo_a["name"])

        logger.info("clusters_found", count=len(clusters))
        return clusters

    def generate_archival_recommendation(self, cluster: ClusterResult) -> str:
        """Generate recommendation for archiving redundant repos.

        Args:
            cluster: Cluster result

        Returns:
            Formatted recommendation
        """
        lines = [
            f"## Redundancy Cluster {cluster.cluster_id}",
            "",
            f"**Found {len(cluster.repositories)} similar projects:**",
        ]

        for repo in cluster.repositories:
            score = cluster.similarity_scores.get(repo, 0.0)
            lines.append(f"- `{repo}` (similarity: {score:.1%})")

        if cluster.recommend_keep:
            lines.extend(
                [
                    "",
                    f"**Recommendation:** Keep `{cluster.recommend_keep}` as the primary project.",
                ]
            )

        if cluster.recommend_archive:
            lines.extend(
                [
                    "",
                    "**Suggested actions:**",
                ]
            )
            for repo in cluster.recommend_archive:
                lines.append(
                    f"- Archive `{repo}` and add a note pointing to `{cluster.recommend_keep}`"
                )

        return "\n".join(lines)


@lru_cache(maxsize=1024)
def extract_api_signature(file_contents: dict[str, str], language: str) -> APISignature:
    """Extract API signature from file contents.

    Args:
        file_contents: Mapping of file paths to contents
        language: Programming language

    Returns:
        APISignature
    """
    module_names = []
    function_names = []
    class_names = []

    if language == "python":
        module_names, function_names, class_names = _extract_python_api(file_contents)
    elif language in ("javascript", "typescript"):
        module_names, function_names, class_names = _extract_js_api(file_contents)
    elif language == "go":
        module_names, function_names, class_names = _extract_go_api(file_contents)
    elif language == "rust":
        module_names, function_names, class_names = _extract_rust_api(file_contents)

    return APISignature(
        module_names=module_names,
        function_names=function_names,
        class_names=class_names,
        public_exports=len(function_names) + len(class_names),
    )


def _extract_python_api(
    file_contents: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """Extract Python API identifiers."""
    import ast

    module_names = []
    function_names = []
    class_names = []

    for path, content in file_contents.items():
        if not path.endswith(".py"):
            continue

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith("_"):
                        function_names.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
        except Exception:
            pass

    return module_names, function_names, class_names


def _extract_js_api(
    file_contents: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """Extract JavaScript/TypeScript API identifiers."""
    import re

    module_names = []
    function_names = []
    class_names = []

    for path, content in file_contents.items():
        if not (path.endswith(".js") or path.endswith(".ts")):
            continue

        # Find function declarations
        for match in re.finditer(r"function\s+(\w+)", content):
            func_name = match.group(1)
            if not func_name.startswith("_"):
                function_names.append(func_name)

        # Find class declarations
        for match in re.finditer(r"class\s+(\w+)", content):
            class_names.append(match.group(1))

        # Find exports
        for match in re.finditer(r"export\s+(?:const|let|var)\s+(\w+)", content):
            function_names.append(match.group(1))

    return module_names, function_names, class_names


def _extract_go_api(
    file_contents: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """Extract Go API identifiers."""
    import re

    module_names = []
    function_names = []
    class_names = []

    for path, content in file_contents.items():
        if not path.endswith(".go"):
            continue

        # Find package names
        for match in re.finditer(r"package\s+(\w+)", content):
            module_names.append(match.group(1))

        # Find functions (exported start with capital)
        for match in re.finditer(r"func\s+([A-Z]\w*)", content):
            function_names.append(match.group(1))

        # Find types/interfaces
        for match in re.finditer(r"type\s+([A-Z]\w+)\s+(?:struct|interface)", content):
            class_names.append(match.group(1))

    return module_names, function_names, class_names


def _extract_rust_api(
    file_contents: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """Extract Rust API identifiers."""
    import re

    module_names = []
    function_names = []
    class_names = []

    for path, content in file_contents.items():
        if not path.endswith(".rs"):
            continue

        # Find module declarations
        for match in re.finditer(r"mod\s+(\w+);", content):
            module_names.append(match.group(1))

        # Find pub functions
        for match in re.finditer(r"pub\s+fn\s+(\w+)", content):
            function_names.append(match.group(1))

        # Find pub structs
        for match in re.finditer(r"pub\s+struct\s+(\w+)", content):
            class_names.append(match.group(1))

        # Find pub traits
        for match in re.finditer(r"pub\s+trait\s+(\w+)", content):
            class_names.append(match.group(1))

    return module_names, function_names, class_names
