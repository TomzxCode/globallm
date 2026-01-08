# Impact Analysis Specification

## Overview

The Impact Analysis feature calculates the potential downstream impact of contributing to a repository. It uses dependency graph analysis and popularity metrics to identify repositories where improvements will benefit the most users.

## Requirements

### Functional Requirements

#### IA-001: Dependency Graph Construction
The system MUST construct a dependency graph for discovered repositories using NetworkX, mapping:
- Upstream dependencies (what the repository depends on)
- Downstream dependents (what depends on the repository)
- Transitive relationships (dependencies of dependencies)

#### IA-002: Package Registry Integration
The system MUST integrate with package registries to fetch dependency data:
- PyPI (Python)
- npm (JavaScript/TypeScript)
- crates.io (Rust)
- Go Module Mirror (Go)
- Maven Central (Java)

#### IA-003: Impact Score Calculation
The system MUST calculate an impact score (0-100%) based on:
- Direct dependents count (weight: 40%)
- Transitive dependents count (weight: 30%)
- Stars count (weight: 15%)
- Forks count (weight: 10%)
- Watchers count (weight: 5%)

#### IA-004: Centrality Metrics
The system SHOULD calculate graph centrality metrics including:
- PageRank centrality
- Betweenness centrality
- Degree centrality

#### IA-005: Impact Threshold
The system MUST apply a configurable impact threshold (default: 50%) to classify repositories as high-impact or low-impact.

#### IA-006: Normalized Scoring
The system MUST normalize impact scores across all analyzed repositories to enable meaningful comparison.

#### IA-007: Worth Working On Calculation
The system MUST combine health and impact scores to determine if a repository is "worth working on":
- `worth_working_on = (health_score > 0.5) AND (impact_score > 0.5)`

#### IA-008: Dependency Updates
The system SHOULD support periodic updates to dependency graphs as new repositories are discovered.

### Non-Functional Requirements

#### IA-N001: Performance
The system SHOULD complete impact analysis for a single repository within 30 seconds.

#### IA-N002: Graph Scalability
The system MUST handle dependency graphs with up to 10,000 nodes without performance degradation.

#### IA-N003: Data Persistence
The system MUST persist dependency graphs to enable incremental updates.

#### IA-N004: API Rate Limits
The system MUST respect package registry API rate limits and implement appropriate caching.

#### IA-N005: Error Handling
The system MUST handle missing or incomplete dependency data gracefully by using available metrics as fallback.

## API/CLI Interface

### Command
```bash
globallm analyze <repository>
```

### Example Usage
```bash
# Analyze a repository (includes both health and impact)
globallm analyze django/django

# Output includes:
# - Impact Score (0-100%)
# - Direct dependents count
# - Transitive dependents count
# - Centrality metrics
# - Worth working on (✓ or ✗)
```

## Data Model

### ImpactScore
```python
class ImpactScore:
    score: float                # 0.0 to 1.0
    direct_dependents: int
    transitive_dependents: int
    stars: int
    forks: int
    watchers: int
    pagerank_centrality: float
    betweenness_centrality: float
    degree_centrality: float
    reason: str                 # Human-readable explanation
```

### DependencyGraph
```python
class DependencyGraph:
    graph: nx.DiGraph           # NetworkX directed graph
    repository: str             # Repository being analyzed
    upstream: Set[str]          # Dependencies
    downstream: Set[str]        # Dependents
    last_updated: datetime      # Last update timestamp
```

### Repository Analysis
```python
class Repository:
    name: str
    health_score: HealthScore
    impact_score: ImpactScore
    worth_working_on: bool
    analysis_reason: str
    last_analyzed: datetime
```

## Algorithm Details

### Impact Score Formula
```
direct_dependents_score = min(direct_dependents / 1000, 1.0)
transitive_dependents_score = min(transitive_dependents / 10000, 1.0)
stars_score = min(stars / 100000, 1.0)
forks_score = min(forks / 10000, 1.0)
watchers_score = min(watchers / 1000, 1.0)

impact_score = (
    direct_dependents_score * 0.40 +
    transitive_dependents_score * 0.30 +
    stars_score * 0.15 +
    forks_score * 0.10 +
    watchers_score * 0.05
)
```

### Normalization
Impact scores are normalized using min-max scaling across all analyzed repositories:
```
normalized_score = (score - min_score) / (max_score - min_score)
```

### Worth Working On Logic
```python
worth_working_on = (
    health_score.score > 0.5 and
    impact_score.score > 0.5
)
```

## Success Criteria

An impact analysis operation is considered successful when:
1. An impact score between 0-100% is produced
2. Dependency counts (direct and transitive) are accurate
3. Centrality metrics are calculated
4. A human-readable reason is generated
5. The result is persisted to the repository store
6. API rate limits are respected
