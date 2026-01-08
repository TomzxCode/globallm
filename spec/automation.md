# Automation Specification

## Overview

The Automation feature enables GlobaLLM to automatically merge safe pull requests and monitor CI/CD status. It removes human review bottlenecks for trusted, low-risk changes while maintaining quality through automated checks.

## Requirements

### Functional Requirements

#### AU-001: Auto-Merge Eligibility
The system MUST automatically merge pull requests that meet ALL of the following criteria:
- Risk level: LOW
- All CI checks passing
- No merge conflicts
- No review requirements
- Not a protected branch

#### AU-002: Auto-Merge Ineligibility
The system MUST NOT automatically merge pull requests that meet ANY of the following criteria:
- Risk level: MEDIUM or HIGH
- Failing CI checks
- Merge conflicts present
- Required reviews pending
- Protected branch with review requirements

#### AU-003: CI/CD Monitoring
The system MUST monitor CI/CD status for:
- GitHub Actions
- Travis CI
- CircleCI
- GitLab CI
- Azure Pipelines

#### AU-004: CI Status Polling
The system MUST poll CI status at regular intervals (default: 30 seconds) until completion.

#### AU-005: CI Timeout
The system MUST timeout CI checks after a configurable duration (default: 30 minutes).

#### AU-006: Merge Conflict Detection
The system MUST detect merge conflicts before attempting auto-merge.

#### AU-007: Protected Branch Detection
The system MUST detect protected branch settings that require human review.

#### AU-008: Merge Strategy Selection
The system MUST support multiple merge strategies:
- Merge commit
- Squash and merge
- Rebase and merge

#### AU-009: PR Comment Automation
The system SHOULD automatically comment on PRs with:
- Summary of changes
- Test results
- Auto-merge decision

#### AU-010: Failure Notification
The system MUST notify when auto-merge fails, including:
- Failure reason
- Relevant logs
- Suggested actions

### Non-Functional Requirements

#### AU-N001: API Rate Limits
The system MUST respect GitHub API rate limits during CI polling.

#### AU-N002: Idempotency
Auto-merge operations MUST be idempotent (safe to retry).

#### AU-N003: Audit Logging
The system MUST log all auto-merge decisions with:
- PR URL
- Decision (merge/skip)
- Reason for decision
- Timestamp

#### AU-N004: Error Recovery
The system MUST handle transient failures gracefully and retry appropriately.

## API/CLI Interface

### Integration with Fix Command

Auto-merge is integrated into the solution generation workflow:

```bash
# Enable auto-merge (default for safe changes)
globallm fix

# Disable auto-merge
globallm fix --no-auto-merge
```

### Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--auto-merge` | flag | true | Enable auto-merge for safe changes |
| `--no-auto-merge` | flag | false | Disable auto-merge |
| `--merge-strategy` | string | merge | Merge strategy (merge, squash, rebase) |

## Data Model

### AutoMergeDecision
```python
class AutoMergeDecision:
    pr_url: str
    repository: str
    pr_number: int
    should_merge: bool
    reason: str
    risk_level: RiskLevel
    ci_status: CIStatus
    has_conflicts: bool
    is_protected: bool
    merge_strategy: MergeStrategy
    timestamp: datetime
```

### CIStatus (Enum)
```python
class CIStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"
```

### MergeStrategy (Enum)
```python
class MergeStrategy(Enum):
    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"
```

### CIMonitor
```python
class CIMonitor:
    pr_url: str
    repository: str
    workflows: List[CIWorkflow]
    status: CIStatus
    last_checked: datetime
    timeout_seconds: int
```

### CIWorkflow
```python
class CIWorkflow:
    name: str
    platform: str        # github, travis, circleci, etc.
    status: CIStatus
    url: Optional[str]
    conclusion: Optional[str]
```

## Algorithm Details

### Auto-Merge Decision Flow

```
┌─────────────────────┐
│ PR Created          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Check Risk Level    │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────────┐
│ LOW     │  │ MEDIUM / HIGH   │
│         │  │                 │
└────┬────┘  └────────┬────────┘
     │                 │
     ▼                 ▼
┌─────────────────────┐  ┌─────────────────┐
│ Check CI Status     │  │ Skip Auto-Merge │
└──────────┬──────────┘  └─────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────────┐
│ PASSED  │  │ FAILED/PENDING  │
│         │  │                 │
└────┬────┘  └────────┬────────┘
     │                 │
     ▼                 ▼
┌─────────────────────┐  ┌─────────────────┐
│ Check Conflicts     │  │ Skip Auto-Merge │
└──────────┬──────────┘  └─────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────────┐
│ NONE    │  │ CONFLICTS       │
│         │  │                 │
└────┬────┘  └────────┬────────┘
     │                 │
     ▼                 ▼
┌─────────────────────┐  ┌─────────────────┐
│ Check Protection    │  │ Skip Auto-Merge │
└──────────┬──────────┘  └─────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────────┐
│ NOT     │  │ PROTECTED       │
│ PROTECTED│  │                 │
└────┬────┘  └────────┬────────┘
     │                 │
     ▼                 ▼
┌─────────────────────┐  ┌─────────────────┐
│ AUTO-MERGE          │  │ Skip Auto-Merge │
└─────────────────────┘  └─────────────────┘
```

### CI Polling Logic

```python
while time_elapsed < timeout:
    status = fetch_ci_status(pr_url)
    if status == PASSED:
        return True
    elif status == FAILED:
        return False
    elif status == NOT_CONFIGURED:
        # No CI configured, can't verify
        return False
    sleep(poll_interval)
return False  # Timeout
```

### Merge Strategy Selection

- **Merge commit**: Default for most repositories
- **Squash and merge**: Used when repository prefers clean history
- **Rebase and merge**: Used when repository prefers linear history

The system should respect repository default merge strategy.

## Success Criteria

An automation operation is considered successful when:
1. Auto-merge decisions are made correctly based on criteria
2. CI status is accurately monitored
3. Merges are executed for eligible PRs
4. Ineligible PRs are skipped with appropriate reasons
5. All decisions are logged for audit
6. Failures are handled gracefully
7. API rate limits are respected
