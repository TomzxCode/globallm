# Agent Coordination Specification

## Overview

The Agent Coordination feature enables multiple GlobaLLM agents to run in parallel without conflicts. It manages issue assignments, tracks agent heartbeats for crash recovery, and ensures each agent works on unique issues.

## Requirements

### Functional Requirements

#### AC-001: Agent Identity Generation
The system MUST generate a unique agent identity on startup consisting of:
- Hostname
- Process ID
- Random identifier (e.g., `hostname-1234-abc12345`)

#### AC-002: Issue Assignment
The system MUST assign issues to agents with the following states:
- `available` - Issue is available to be claimed
- `assigned` - Issue is currently assigned to an agent
- `completed` - Issue was successfully completed (removed from pool)
- `failed` - Issue processing failed (released back to available)

#### AC-003: Issue Claiming
When an agent runs `globallm fix` without an issue URL, the system MUST:
1. Query for the highest-priority available issue
2. Atomically assign the issue to the agent
3. Return the issue URL for processing

#### AC-004: Heartbeat Tracking
The system MUST track agent heartbeats to detect crashes:
- Heartbeat interval: 5 minutes (configurable)
- Heartbeat timeout: 30 minutes (configurable)
- Agents update heartbeat during long-running operations

#### AC-005: Stale Assignment Detection
The system MUST identify stale assignments where:
- No heartbeat received for 30+ minutes
- Agent is no longer running

#### AC-006: Assignment Cleanup
The system MUST support cleanup of stale assignments via `globallm assign cleanup --timeout-minutes 30`.

#### AC-007: Manual Release
The system MUST support manual release of assignments via `globallm assign release <agent-id>`.

#### AC-008: Assignment Status Display
The system MUST display current assignment status including:
- Total issues by status
- Per-agent assignment details
- Stale assignment identification

#### AC-009: Concurrent Safety
All assignment operations MUST be atomic to prevent race conditions when multiple agents claim issues simultaneously.

#### AC-010: Persistent Storage
Assignments MUST be persisted to the database to survive process restarts.

### Non-Functional Requirements

#### AC-N001: Database Performance
Assignment queries MUST complete within 100ms to avoid blocking agent operations.

#### AC-N002: Scalability
The system MUST support at least 100 concurrent agents without performance degradation.

#### AC-N003: Atomic Operations
Issue claiming MUST use database-level atomic operations (SELECT FOR UPDATE or equivalent).

#### AC-N004: Idempotency
Heartbeat updates MUST be idempotent (safe to retry).

## API/CLI Interface

### Commands

#### Assignment Status
```bash
globallm assign status [options]
```

**Options:**
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--agent-id` | string | null | Show assignments for specific agent |
| `--stale` | flag | false | Show only stale assignments |

#### Assignment Release
```bash
globallm assign release <agent-id>
```

#### Assignment Cleanup
```bash
globallm assign cleanup --timeout-minutes 30
```

### Example Usage

```bash
# Show all assignments
globallm assign status

# Show stale assignments
globallm assign status --stale

# Show assignments for specific agent
globallm assign status --agent-id hostname-1234-abc12345

# Release all assignments for an agent
globallm assign release hostname-1234-abc12345

# Clean up stale assignments
globallm assign cleanup --timeout-minutes 30
```

### Example Output
```
Assignment Status:
─────────────────────────────────────
Total Issues:         1,234
Available:            1,100
Assigned:             100
Completed:            34
Failed:               0

Active Assignments:
─────────────────────────────────────
agent-001:  5 issues (last heartbeat: 2m ago)
agent-002:  3 issues (last heartbeat: 5m ago)
agent-003:  2 issues (last heartbeat: 45m ago) [STALE]

Stale Assignments:
─────────────────────────────────────
agent-003:  2 issues (timeout: 30m)
  - repo1#123 (assigned 45m ago)
  - repo2#456 (assigned 47m ago)
```

## Data Model

### Issue Assignment
```python
class IssueAssignment:
    issue_url: str
    repository: str
    issue_number: int
    assigned_to: str              # Agent ID
    assigned_at: datetime
    last_heartbeat_at: datetime
    status: AssignmentStatus
```

### AssignmentStatus (Enum)
```python
class AssignmentStatus(Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"
```

### AgentIdentity
```python
class AgentIdentity:
    agent_id: str                 # Unique identifier
    hostname: str
    pid: int
    random_component: str
    created_at: datetime
    last_seen: datetime
```

### Heartbeat
```python
class Heartbeat:
    agent_id: str
    timestamp: datetime
    operation: str                # "fix", "analyze", etc.
    issue_url: Optional[str]
```

## Algorithm Details

### Issue Claiming (Atomic)

```python
def claim_issue(agent_id: str) -> Optional[IssueAssignment]:
    # Use database transaction for atomicity
    with db.transaction():
        # Find highest-priority available issue
        issue = db.query("""
            SELECT issue_url
            FROM issues
            WHERE assignment_status = 'available'
            ORDER BY priority_score DESC
            LIMIT 1
            FOR UPDATE  # Lock the row
        """)

        if not issue:
            return None

        # Assign to agent
        db.execute("""
            UPDATE issues
            SET assignment_status = 'assigned',
                assigned_to = ?,
                assigned_at = NOW(),
                last_heartbeat_at = NOW()
            WHERE issue_url = ?
        """, agent_id, issue.url)

        return IssueAssignment(...)
```

### Heartbeat Update

```python
def update_heartbeat(agent_id: str, issue_url: str):
    db.execute("""
        UPDATE issues
        SET last_heartbeat_at = NOW()
        WHERE assigned_to = ? AND issue_url = ?
    """, agent_id, issue_url)
```

### Stale Detection

```python
def find_stale_assignments(timeout_minutes: int) -> List[IssueAssignment]:
    timeout = datetime.now() - timedelta(minutes=timeout_minutes)
    return db.query("""
        SELECT *
        FROM issues
        WHERE assignment_status = 'assigned'
        AND last_heartbeat_at < ?
    """, timeout)
```

### Cleanup Logic

```python
def cleanup_stale_assignments(timeout_minutes: int):
    stale = find_stale_assignments(timeout_minutes)
    for assignment in stale:
        db.execute("""
            UPDATE issues
            SET assignment_status = 'available',
                assigned_to = NULL,
                assigned_at = NULL,
                last_heartbeat_at = NULL
            WHERE issue_url = ?
        """, assignment.issue_url)
```

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GLOBALLM_AGENT_ID` | string | auto | Manual agent ID override |
| `GLOBALLM_HEARTBEAT_INTERVAL` | int | 300 | Heartbeat interval (seconds) |
| `GLOBALLM_HEARTBEAT_TIMEOUT` | int | 1800 | Heartbeat timeout (seconds) |

## Success Criteria

Agent coordination is considered successful when:
1. Each agent receives unique issue assignments
2. No two agents work on the same issue simultaneously
3. Stale assignments are detected and cleaned up
4. Crash recovery works (agents can resume work after restart)
5. Atomic operations prevent race conditions
6. Database queries remain fast under load
7. Assignment status is accurately reported
