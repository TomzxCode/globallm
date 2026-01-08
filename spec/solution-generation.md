# Solution Generation Specification

## Overview

The Solution Generation feature automatically analyzes GitHub issues and generates complete solutions including code patches and tests. It uses LLMs to understand the problem, generate fixes, and create appropriate test coverage.

## Requirements

### Functional Requirements

#### SG-001: Issue Analysis
The system MUST analyze GitHub issues to extract:
- Problem description
- Expected behavior
- Actual behavior
- Reproduction steps
- Relevant code context
- Related files

#### SG-002: Code Patch Generation
The system MUST generate code patches that:
- Address the root cause of the issue
- Follow project coding style
- Include appropriate error handling
- Maintain backward compatibility
- Include docstrings/comments

#### SG-003: Test Generation
The system MUST generate tests that:
- Cover the fix (positive case)
- Cover edge cases
- Include regression tests
- Follow the project's testing framework
- Include descriptive test names

#### SG-004: Solution Validation
The system MUST validate generated solutions by:
- Checking syntax correctness
- Verifying imports are available
- Ensuring code compiles/runs
- Running generated tests

#### SG-005: Risk Assessment
The system MUST assess solution risk as:
- Low (simple fixes, tests only, documentation)
- Medium (isolated changes, new features)
- High (core logic, breaking changes, complex refactors)

#### SG-006: Dry Run Mode
The system MUST support a `--dry-run` mode that generates solutions without creating pull requests.

#### SG-007: Branch Targeting
The system MUST support targeting specific branches via `--branch` parameter.

#### SG-008: Auto-Merge Control
The system MUST support `--no-auto-merge` flag to disable automatic merging of safe changes.

#### SG-009: Issue URL Handling
The system MUST accept either:
- A specific issue URL via `--issue-url`
- No URL (automatically claim highest-priority available issue)

#### SG-010: LLM Abstraction
The system MUST support multiple LLM providers through a common interface (Claude, OpenAI, etc.).

### Non-Functional Requirements

#### SG-N001: Token Estimation
The system MUST estimate token usage before generation and respect budget limits.

#### SG-N002: Timeout Handling
The system MUST implement appropriate timeouts for LLM API calls (default: 5 minutes).

#### SG-N003: Retry Logic
The system MUST implement exponential backoff retry logic for transient API failures.

#### SG-N004: Progress Reporting
The system MUST report progress during solution generation (analysis, generation, validation).

#### SG-N005: Error Handling
The system MUST provide clear error messages when generation fails, including partial results for debugging.

## API/CLI Interface

### Command
```bash
globallm fix [options]
```

### Options
| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--issue-url` | string | No | null | Specific issue URL to fix |
| `--dry-run` | flag | No | false | Generate without creating PR |
| `--branch` | string | No | main/default | Target branch |
| `--no-auto-merge` | flag | No | false | Disable auto-merge for safe changes |

### Example Usage
```bash
# Fix highest-priority available issue
globallm fix

# Fix specific issue
globallm fix --issue-url https://github.com/owner/repo/issues/123

# Dry run (no PR)
globallm fix --dry-run

# Target specific branch
globallm fix --branch develop

# Disable auto-merge
globallm fix --no-auto-merge
```

## Data Model

### Solution
```python
class Solution:
    issue_url: str
    repository: str
    issue_number: int
    title: str
    description: str
    code_patches: List[CodePatch]
    tests: List[GeneratedTest]
    risk_level: RiskLevel
    status: SolutionStatus
    created_at: datetime
    llm_tokens_used: int
```

### CodePatch
```python
class CodePatch:
    file_path: str
    original_content: str
    modified_content: str
    diff: str
    description: str
```

### GeneratedTest
```python
class GeneratedTest:
    file_path: str
    test_name: str
    test_code: str
    framework: str           # pytest, unittest, jest, etc.
    description: str
```

### RiskLevel (Enum)
```python
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

### SolutionStatus (Enum)
```python
class SolutionStatus(Enum):
    GENERATING = "generating"
    VALIDATING = "validating"
    READY = "ready"
    SUBMITTED = "submitted"
    MERGED = "merged"
    FAILED = "failed"
```

## Algorithm Details

### Risk Assessment Criteria

#### Low Risk
- Test-only changes
- Documentation updates
- Simple bug fixes in isolated code
- Type hints/annotations
- Comment improvements

#### Medium Risk
- New features with clear scope
- Bug fixes in core logic
- Refactoring with test coverage
- Performance improvements
- API additions (backward compatible)

#### High Risk
- Breaking changes
- Core algorithm modifications
- Complex refactors
- Security fixes
- Database schema changes
- API removals

### Generation Pipeline

1. **Issue Analysis**
   - Fetch issue details from GitHub
   - Extract problem statement
   - Identify affected files
   - Gather code context

2. **Code Generation**
   - Send prompt to LLM with context
   - Generate code patches
   - Ensure style consistency

3. **Test Generation**
   - Generate test cases
   - Include edge cases
   - Generate regression tests

4. **Validation**
   - Check syntax
   - Verify imports
   - Run tests (if possible)
   - Assess risk level

5. **Submission**
   - Create git branch
   - Apply patches
   - Commit changes
   - Create pull request
   - Auto-merge if safe

### Auto-Merge Logic

Auto-merge is enabled for:
- Risk level: LOW
- Tests pass
- No merge conflicts
- No human reviewers required

Auto-merge is disabled for:
- Risk level: MEDIUM or HIGH
- Test failures
- Merge conflicts
- Protected branches requiring review

## Success Criteria

A solution generation operation is considered successful when:
1. Code patches are generated that address the issue
2. Tests are generated that verify the fix
3. The solution passes validation checks
4. A pull request is created (unless dry-run)
5. Low-risk solutions are auto-merged (if enabled)
6. Token usage is within budget limits
7. The operation completes within timeout limits
