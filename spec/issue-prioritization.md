# Issue Prioritization Specification

## Overview

The Issue Prioritization feature ranks GitHub issues across multiple repositories using a multi-factor scoring algorithm. It identifies the highest-value work by considering repository health, impact, issue solvability, urgency, and redundancy.

## Requirements

### Functional Requirements

#### IP-001: Multi-Factor Scoring
The system MUST calculate priority scores based on:
- Repository health score (weight: 25%)
- Repository impact score (weight: 25%)
- Issue solvability score (weight: 20%)
- Issue urgency score (weight: 15%)
- Redundancy score (weight: 15%)

#### IP-002: Repository Store Integration
The system MUST read repository data from the repository store, filtering to only "approved" repositories where `worth_working_on=true`.

#### IP-003: Issue Categorization
The system MUST automatically categorize issues into:
- Bug (defects, errors, crashes)
- Feature (new functionality)
- Enhancement (improvements to existing features)
- Documentation (docs, guides, examples)
- Performance (optimization, speed improvements)
- Security (vulnerabilities, exploits)
- Refactoring (code quality, technical debt)
- Testing (test coverage, test fixes)
- Other (miscellaneous)

#### IP-004: Severity Classification
The system MUST classify issue severity as:
- Critical (system-breaking, security vulnerabilities)
- High (major functionality broken)
- Medium (workarounds available)
- Low (minor inconveniences)

#### IP-005: Solvability Assessment
The system MUST assess issue solvability based on:
- Issue description clarity
- Reproduction steps presence
- Code context availability
- Labels and metadata
- Comments and discussion quality

#### IP-006: Urgency Scoring
The system MUST assess urgency based on:
- Issue age (older issues = higher urgency)
- Critical/high severity
- Number of affected users (comments, reactions)
- Dependencies blocked (linked issues, PRs)

#### IP-007: Redundancy Detection
The system MUST detect redundant issues by:
- Comparing issue titles and descriptions
- Identifying duplicate reports across repositories
- Checking for similar feature requests

#### IP-008: Language Filtering
The system MUST support filtering issues by programming language.

#### IP-009: Result Limiting
The system MUST support limiting results to the top N issues via `--top` parameter.

#### IP-010: Minimum Priority Threshold
The system MUST support filtering issues by minimum priority score via `--min-priority` parameter.

#### IP-011: Result Export
The system MUST support exporting prioritized issues to JSON format.

### Non-Functional Requirements

#### IP-N001: Performance
The system SHOULD complete prioritization across 100 repositories within 120 seconds.

#### IP-N002: Database Query Efficiency
The system MUST use efficient database queries to avoid N+1 query problems when fetching issues across repositories.

#### IP-N003: Batch Processing
The system SHOULD process issues in batches to minimize memory usage.

#### IP-N004: Caching
The system SHOULD cache priority scores for 1 hour to avoid redundant calculations.

## API/CLI Interface

### Command
```bash
globallm prioritize [options]
```

### Options
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--language` | string | No | all | Filter by programming language |
| `--top` | integer | No | 20 | Maximum number of results |
| `--min-priority` | float | No | 0.0 | Minimum priority score (0-1) |
| `--export` | string | No | - | Export format (json) |

### Example Usage
```bash
# Show top 20 priority issues
globallm prioritize

# Filter by language
globallm prioritize --language python

# Show top 50 with minimum priority
globallm prioritize --top 50 --min-priority 0.5

# Export to JSON
globallm prioritize --export json > priorities.json
```

## Data Model

### Issue Priority
```python
class IssuePriority:
    issue_url: str
    repository: str
    title: str
    category: IssueCategory
    severity: IssueSeverity
    priority_score: float        # 0.0 to 1.0
    health_contribution: float   # Repository health contribution
    impact_contribution: float   # Repository impact contribution
    solvability_score: float     # Estimated difficulty
    urgency_score: float         # Time sensitivity
    redundancy_score: float      # Uniqueness value
    reason: str                  # Human-readable explanation
```

### Issue Category (Enum)
```python
class IssueCategory(Enum):
    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    REFACTORING = "refactoring"
    TESTING = "testing"
    OTHER = "other"
```

### Issue Severity (Enum)
```python
class IssueSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

## Algorithm Details

### Priority Score Formula
```
priority_score = (
    health_contribution * 0.25 +
    impact_contribution * 0.25 +
    solvability_score * 0.20 +
    urgency_score * 0.15 +
    redundancy_score * 0.15
)
```

### Solvability Score Factors
- Clear description: +0.3
- Reproduction steps: +0.2
- Code context available: +0.2
- Good labels: +0.1
- Quality discussion: +0.2

### Urgency Score Factors
- Critical severity: +0.4
- High severity: +0.3
- Age > 90 days: +0.2
- Age > 30 days: +0.1
- 10+ comments: +0.1
- 5+ reactions: +0.1

### Redundancy Score
- Unique issue: 1.0
- Potential duplicate: 0.5
- Confirmed duplicate: 0.0

### Category Severity Defaults
- Security issues: CRITICAL
- Bug reports: HIGH/MEDIUM
- Feature requests: MEDIUM
- Documentation: LOW
- Refactoring: LOW

## Success Criteria

An issue prioritization operation is considered successful when:
1. Issues are ranked by priority score in descending order
2. Each issue has a category and severity assigned
3. A human-readable explanation is provided
4. Results are filtered according to command-line options
5. The operation completes within performance targets
6. Database queries are efficient (no N+1 problems)
