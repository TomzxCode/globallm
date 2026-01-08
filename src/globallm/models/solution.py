"""Solution-related data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SolutionStatus(Enum):
    """Status of a generated solution."""

    DRAFT = "draft"
    READY = "ready"
    REVIEWED = "reviewed"
    TESTED = "tested"
    SUBMITTED = "submitted"
    MERGED = "merged"
    FAILED = "failed"


class RiskLevel(Enum):
    """Risk level for a solution."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_complexity(cls, complexity: int, breaking: bool = False) -> "RiskLevel":
        """Determine risk level from complexity and breaking change flag."""
        if breaking:
            return cls.CRITICAL
        if complexity >= 8:
            return cls.CRITICAL
        if complexity >= 6:
            return cls.HIGH
        if complexity >= 4:
            return cls.MEDIUM
        return cls.LOW

    @property
    def auto_merge_allowed(self) -> bool:
        """Check if auto-merge is allowed for this risk level."""
        return self in (RiskLevel.LOW, RiskLevel.MEDIUM)


@dataclass
class CodePatch:
    """A code patch for a single file."""

    file_path: str
    original_content: str
    new_content: str
    description: str
    language: str

    # Computed metrics
    lines_added: int = 0
    lines_removed: int = 0

    def __post_init__(self) -> None:
        """Calculate diff metrics."""
        original_lines = self.original_content.splitlines()
        new_lines = self.new_content.splitlines()
        self.lines_added = len(new_lines) - len(original_lines)
        # Rough approximation for removed lines
        self.lines_removed = max(0, len(original_lines) - len(new_lines))


@dataclass
class FeasibilityReport:
    """Report on solution feasibility."""

    is_feasible: bool
    confidence: float  # 0-1
    estimated_tokens: int
    estimated_time_seconds: int
    risk_level: RiskLevel
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_automerge(self) -> bool:
        """Check if auto-merge is appropriate."""
        return self.is_feasible and self.risk_level.auto_merge_allowed


@dataclass
class Solution:
    """Generated solution for an issue."""

    issue_url: str
    repository: str
    issue_number: int
    issue_title: str

    # Solution content
    description: str
    patches: list[CodePatch]
    test_patches: list[CodePatch] = field(default_factory=list)

    # Metadata
    complexity: int = 5  # 1-10
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: SolutionStatus = SolutionStatus.DRAFT
    language: str | None = None  # Programming language

    # Generation info
    generated_at: datetime = field(default_factory=datetime.now)
    llm_model: str = "unknown"
    tokens_used: int = 0

    # Validation results
    feasibility: FeasibilityReport | None = None
    syntax_valid: bool = True
    tests_generated: bool = False
    breaking_change: bool = False

    # PR info (set after submission)
    pr_number: int | None = None
    pr_url: str | None = None
    merged_at: datetime | None = None

    @property
    def affected_files(self) -> list[str]:
        """List of affected file paths."""
        return [patch.file_path for patch in self.patches]

    @property
    def total_lines_changed(self) -> int:
        """Total lines changed across all patches."""
        return sum(p.lines_added + p.lines_removed for p in self.patches)

    @property
    def can_auto_merge(self) -> bool:
        """Check if this solution can be auto-merged."""
        if not self.syntax_valid:
            return False
        if not self.tests_generated and self.complexity > 2:
            return False
        return self.risk_level.auto_merge_allowed

    def to_pr_description(self) -> str:
        """Generate PR description from this solution."""
        files_list = "\n".join(f"- `{f}`" for f in self.affected_files)

        # Format test status
        if self.tests_generated:
            test_status = "✅ Tests generated/updated"
            test_check = "[x] Tests included"
        else:
            test_status = "⚠️ No tests generated"
            test_check = "[ ] Tests needed"

        # Format breaking change warning
        breaking_warning = ""
        if self.breaking_change:
            breaking_warning = "\n\n**⚠️ Breaking Change**: This PR modifies public API. Review required before merging."

        return f"""## Summary
{self.description}

## Changes
- **Files modified**: {len(self.patches)}
- **Lines changed**: {self.total_lines_changed}
- **Complexity**: {self.complexity}/10
- **Risk level**: {self.risk_level.value.upper()}
{"- **Breaking change**: Yes" if self.breaking_change else ""}

### Affected files
{files_list}

## Tests
{test_status}
{"### Test files modified" if self.test_patches else ""}

## Auto-Merge
This PR is configured to auto-merge when all CI checks pass.

**Requirements for auto-merge:**
- [x] Syntax validated
- [x] Risk level: {self.risk_level.value.upper()}
- [x] Complexity: {self.complexity}/10
- {test_check}
{breaking_warning}
---

*Generated by GlobaLLM - LLM-powered open source contribution*
*Issue: #{self.issue_number} in {self.repository}*
"""
