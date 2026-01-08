# Budget Management Specification

## Overview

The Budget Management feature tracks and controls LLM token usage to manage costs when running GlobalLM at scale. It provides visibility into resource consumption and enforces limits to prevent unexpected charges.

## Requirements

### Functional Requirements

#### BM-001: Token Tracking
The system MUST track token usage for all LLM operations including:
- Prompt tokens (input to LLM)
- Completion tokens (output from LLM)
- Total tokens (prompt + completion)

#### BM-002: Budget Limits
The system MUST support the following budget limits:
- Maximum total tokens (hard limit)
- Maximum tokens per operation
- Maximum tokens per repository
- Maximum time duration

#### BM-003: Budget State Persistence
The system MUST persist budget state to disk to survive process restarts.

#### BM-004: Token Estimation
The system MUST estimate token usage before LLM operations to prevent exceeding limits.

#### BM-005: Budget Reset
The system MUST support resetting budget tracking via `globallm budget reset` command.

#### BM-006: Budget Display
The system MUST display current budget status including:
- Total tokens used
- Tokens remaining
- Percentage of budget used
- Estimated cost (if pricing configured)

#### BM-007: Budget Enforcement
The system MUST enforce budget limits by refusing operations that would exceed the configured budget.

#### BM-008: Per-Repository Tracking
The system SHOULD track token usage per repository to enable balanced allocation.

#### BM-009: Cost Estimation
The system SHOULD estimate monetary cost based on LLM provider pricing.

#### BM-010: Budget Warnings
The system SHOULD warn when approaching budget limits (e.g., at 80% usage).

### Non-Functional Requirements

#### BM-N001: Performance
Budget state updates MUST complete within 100ms.

#### BM-N002: Thread Safety
Budget state operations MUST be thread-safe for concurrent access.

#### BM-N003: Data Integrity
Budget state MUST be written atomically to prevent corruption.

#### BM-N004: State File Location
The system MUST store budget state in a predictable location:
- `$XDG_DATA_HOME/globallm/budget_state.json` if set
- `~/.local/share/globallm/budget_state.json` otherwise

## API/CLI Interface

### Commands

#### Show Budget Status
```bash
globallm budget show
```

#### Reset Budget
```bash
globallm budget reset
```

### Example Usage
```bash
# Show current budget status
globallm budget show

# Reset budget tracking
globallm budget reset
```

### Example Output
```
Budget Status:
─────────────────────────────────────
Total Tokens Used:    1,234,567
Tokens Remaining:     8,765,433
Budget Percentage:    12.3%
Estimated Cost:       $12.34

Per-Repository Usage:
─────────────────────────────────────
django/django:       456,789 tokens
numpy/numpy:         234,567 tokens
requests/requests:   123,456 tokens
```

## Data Model

### BudgetState
```python
class BudgetState:
    total_tokens_used: int
    max_total_tokens: int
    max_tokens_per_operation: int
    max_tokens_per_repository: Dict[str, int]
    start_time: datetime
    last_updated: datetime
    operations_completed: int
```

### TokenUsage
```python
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Optional[float]
    operation: str
    repository: Optional[str]
    timestamp: datetime
```

### TokenEstimate
```python
class TokenEstimate:
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_total_tokens: int
    estimated_cost: Optional[float]
```

## Configuration

### Budget Limits (via environment variables or config)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GLOBALLM_MAX_TOKENS` | int | 10,000,000 | Maximum total tokens |
| `GLOBALLM_MAX_TOKENS_PER_OP` | int | 100,000 | Max tokens per operation |
| `GLOBALLM_MAX_TOKENS_PER_REPO` | int | 1,000,000 | Max tokens per repository |
| `GLOBALLM_MAX_TIME_SECONDS` | int | 3600 | Maximum operation duration |
| `GLOBALLM_BUDGET_FILE` | string | auto | Path to budget state file |

## Algorithm Details

### Token Estimation
The system estimates tokens using:
- Character count / 4 (rough estimate for English text)
- Code tokenizers for specific languages (more accurate)
- Historical data from previous operations

### Budget Checking
Before each LLM operation:
1. Estimate token usage
2. Check if estimated + used <= max_total_tokens
3. Check if estimated <= max_tokens_per_operation
4. Check if repository limit not exceeded
5. If any check fails, refuse operation

### Budget Warnings
Warning thresholds:
- 80% of budget used: Warning
- 90% of budget used: Strong warning
- 100% of budget used: Refuse operation

### Cost Estimation
Cost is calculated using provider pricing:
```
cost = (prompt_tokens * prompt_price) + (completion_tokens * completion_price)
```

Default pricing (per 1M tokens):
- Claude Sonnet: $3.00 input, $15.00 output
- GPT-4: $30.00 input, $60.00 output
- GPT-3.5: $0.50 input, $1.50 output

## Success Criteria

A budget management operation is considered successful when:
1. Token usage is accurately tracked
2. Budget limits are enforced
3. State is persisted correctly
4. Display shows accurate information
5. Reset clears all tracking data
6. Concurrent access is handled safely
7. Operations are refused when over budget
