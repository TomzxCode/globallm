# Health Scoring Specification

## Overview

The Health Scoring feature evaluates repository maintainability and activity levels. It produces a normalized health score (0-100%) that indicates whether a repository is actively maintained and suitable for AI agent contributions.

## Requirements

### Functional Requirements

#### HS-001: Multi-Factor Scoring
The system MUST calculate health scores based on multiple weighted factors including:
- Commit velocity (frequency of recent commits)
- Issue resolution rate (closed vs. open issues)
- Pull request merge rate
- CI/CD status (passing/failing builds)
- Recent activity (commits, issues, PRs in the last 90 days)
- Documentation quality (README completeness)
- Release frequency (version tags)

#### HS-002: Normalized Score
The system MUST produce a normalized health score between 0% (unhealthy) and 100% (healthy).

#### HS-003: Health Threshold
The system MUST apply a configurable health threshold (default: 50%) to classify repositories as healthy or unhealthy.

#### HS-004: Factor Weights
The system MUST support configurable weights for each health factor. Default weights:
- Commit velocity: 25%
- Issue resolution: 20%
- PR activity: 15%
- CI/CD status: 15%
- Recent activity: 10%
- Documentation: 10%
- Release frequency: 5%

#### HS-005: CI/CD Detection
The system MUST detect CI/CD configuration from common platforms:
- GitHub Actions
- Travis CI
- CircleCI
- GitLab CI
- Azure Pipelines
- Jenkins

#### HS-006: Documentation Quality Assessment
The system MUST assess documentation quality by checking:
- README presence
- README length (minimum 500 characters for basic score)
- CONTRIBUTING guide presence
- API documentation presence
- Examples presence

#### HS-007: Activity Time Windows
The system MUST evaluate activity across multiple time windows:
- Last 30 days (high weight)
- Last 90 days (medium weight)
- Last 365 days (low weight)

#### HS-008: Health Reason Generation
The system MUST generate a human-readable explanation for the health score, indicating which factors contributed positively or negatively.

### Non-Functional Requirements

#### HS-N001: Performance
The system SHOULD complete health scoring for a single repository within 10 seconds.

#### HS-N002: Data Caching
The system SHOULD cache health scores for 24 hours to avoid redundant API calls.

#### HS-N003: API Efficiency
The system MUST minimize GitHub API calls by fetching all necessary data in batch requests where possible.

#### HS-N004: Graceful Degradation
The system MUST handle missing data gracefully (e.g., no CI/CD configured) by excluding that factor from the score rather than failing.

## API/CLI Interface

### Command
```bash
globallm analyze <repository>
```

### Example Usage
```bash
# Analyze a specific repository
globallm analyze django/django

# The output includes:
# - Health Score (0-100%)
# - Individual factor scores
# - Health reason explanation
```

## Data Model

### HealthScore
```python
class HealthScore:
    score: float              # 0.0 to 1.0
    commit_velocity: float    # 0.0 to 1.0
    issue_resolution: float   # 0.0 to 1.0
    pr_activity: float        # 0.0 to 1.0
    ci_status: float          # 0.0 to 1.0
    recent_activity: float    # 0.0 to 1.0
    documentation: float      # 0.0 to 1.0
    release_frequency: float  # 0.0 to 1.0
    reason: str               # Human-readable explanation
```

### Health Factors
```python
class HealthFactors:
    commits_30d: int
    commits_90d: int
    commits_365d: int
    issues_open: int
    issues_closed_90d: int
    prs_open: int
    prs_merged_90d: int
    has_ci: bool
    ci_passing: bool
    has_readme: bool
    readme_length: int
    has_contributing: bool
    has_api_docs: bool
    has_examples: bool
    releases_count: int
    latest_release_days: int
```

## Algorithm Details

### Commit Velocity Score
- 0 commits in 90 days: 0.0
- 1-5 commits in 90 days: 0.3
- 6-20 commits in 90 days: 0.6
- 21+ commits in 90 days: 1.0

### Issue Resolution Score
- No open issues: 1.0
- Closed/(closed+open) ratio >= 0.9: 1.0
- Closed/(closed+open) ratio >= 0.7: 0.7
- Closed/(closed+open) ratio >= 0.5: 0.4
- Below 0.5: 0.1

### Documentation Score
- Has README + contributing + examples: 1.0
- Has README + contributing: 0.7
- Has README only (length > 1000 chars): 0.5
- Has README only (length < 1000 chars): 0.3
- No README: 0.0

### CI/CD Score
- Has passing CI: 1.0
- Has CI but status unknown: 0.5
- No CI configured: 0.3 (not penalized for small projects)

### Release Frequency Score
- Release in last 30 days: 1.0
- Release in last 90 days: 0.7
- Release in last 180 days: 0.5
- Release in last 365 days: 0.3
- No releases: 0.0

## Success Criteria

A health scoring operation is considered successful when:
1. A health score between 0-100% is produced
2. Individual factor scores are calculated
3. A human-readable reason is generated
4. The result is persisted to the repository store
5. API rate limits are respected
