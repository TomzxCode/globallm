# Redundancy Detection Specification

## Overview

The Redundancy Detection feature identifies duplicate or overlapping projects by comparing README similarity using semantic analysis. It helps consolidate efforts and deprecate redundant libraries to focus resources on high-impact repositories.

## Requirements

### Functional Requirements

#### RD-001: README Comparison
The system MUST compare repositories by analyzing their README files using:
- Semantic text similarity (embeddings)
- Keyword overlap
- Description similarity
- Feature set comparison

#### RD-002: Similarity Scoring
The system MUST produce a similarity score between 0.0 (no similarity) and 1.0 (identical).

#### RD-003: Configurable Threshold
The system MUST support a configurable similarity threshold via `--threshold` parameter (default: 0.7). Repositories scoring above this threshold are considered redundant.

#### RD-004: Multi-Repository Comparison
The system MUST support comparing multiple repositories in a single command:
```bash
globallm redundancy repo1/project repo2/project repo3/project
```

#### RD-005: Semantic Embeddings
The system SHOULD use sentence-transformers or similar embedding models for semantic text comparison.

#### RD-006: Caching
The system SHOULD cache repository READMEs and embeddings to avoid redundant API calls.

#### RD-007: Redundancy Report
The system MUST generate a redundancy report including:
- Pairwise similarity scores
- Redundancy determination
- Recommendations for consolidation/deprecation

#### RD-008: Metadata Comparison
The system SHOULD compare additional metadata:
- Programming language
- Primary category/domain
- Star counts
- Last update date

### Non-Functional Requirements

#### RD-N001: Performance
The system SHOULD complete redundancy analysis for 10 repositories within 60 seconds.

#### RD-N002: Scalability
The system MUST handle comparisons for up to 100 repositories without performance degradation.

#### RD-N003: Embedding Model
The system MUST use a performant embedding model (e.g., `all-MiniLM-L6-v2`) for efficient computation.

#### RD-N004: Error Handling
The system MUST handle missing READMEs gracefully by using repository descriptions as fallback.

## API/CLI Interface

### Command
```bash
globallm redundancy [options] <repository>...
```

### Options
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--threshold` | float | No | 0.7 | Similarity threshold (0-1) |

### Example Usage

```bash
# Compare two repositories
globallm redundancy requests/urllib3 python/cpython

# Compare multiple repositories with custom threshold
globallm redundancy --threshold 0.8 repo1/project repo2/project repo3/project

# High threshold for strict redundancy detection
globallm redundancy --threshold 0.9 numpy/pandas numpy/polars
```

### Example Output
```
Redundancy Analysis:
─────────────────────────────────────
Threshold: 0.7

Pairwise Similarity:
─────────────────────────────────────
requests/urllib3 vs python/cpython:
  Similarity: 0.12
  Redundant:   NO

numpy/pandas vs numpy/polars:
  Similarity: 0.85
  Redundant:   YES
  ⚠ Recommendation: Consolidate on higher-star repository (pandas)

repo1/httpx vs repo2/requests:
  Similarity: 0.78
  Redundant:   YES
  ⚠ Recommendation: Evaluate feature overlap, consider deprecation
```

## Data Model

### RedundancyResult
```python
class RedundancyResult:
    repo1: str
    repo2: str
    similarity_score: float      # 0.0 to 1.0
    is_redundant: bool
    threshold: float
    metadata_comparison: MetadataComparison
    recommendation: str
```

### MetadataComparison
```python
class MetadataComparison:
    same_language: bool
    same_domain: bool
    star_ratio: float
    activity_overlap: float
```

### RepositoryContent
```python
class RepositoryContent:
    name: str
    readme: str
    description: str
    language: str
    topics: List[str]
    embedding: Optional[np.ndarray]
```

## Algorithm Details

### Similarity Calculation

```
overall_similarity = (
    semantic_similarity * 0.60 +
    keyword_overlap * 0.20 +
    description_similarity * 0.15 +
    feature_overlap * 0.05
)
```

### Semantic Similarity
- Generate embeddings using sentence-transformers
- Calculate cosine similarity between embeddings
- Range: 0.0 to 1.0

### Keyword Overlap
- Extract keywords from READMEs (using TF-IDF or RAKE)
- Calculate Jaccard similarity
- Range: 0.0 to 1.0

### Description Similarity
- Compare repository descriptions
- Use Levenshtein distance or sequence matching
- Range: 0.0 to 1.0

### Feature Overlap
- Extract feature lists from READMEs
- Calculate overlap percentage
- Range: 0.0 to 1.0

### Redundancy Determination

```
if similarity_score >= threshold:
    is_redundant = true
else:
    is_redundant = false
```

### Recommendation Logic

```
if is_redundant:
    if same_language and same_domain:
        if star_ratio > 5:
            recommend = "Deprecate lower-star repository"
        elif star_ratio > 2:
            recommend = "Consider consolidating on higher-star repository"
        else:
            recommend = "Evaluate feature overlap, consider merger"
    else:
        recommend = "Review for potential collaboration"
else:
    recommend = "No action needed"
```

### Embedding Model

Recommended model: `all-MiniLM-L6-v2`
- Fast inference
- Good quality for short-medium texts
- Dimension: 384

## Success Criteria

A redundancy detection operation is considered successful when:
1. Pairwise similarity scores are calculated for all repository pairs
2. Redundancy determination is made based on the threshold
3. Recommendations are provided for redundant repositories
4. The operation completes within performance targets
5. READMEs are cached for future comparisons
6. Missing READMEs are handled gracefully
7. Results are clearly presented to the user
