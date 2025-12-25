"""LLM-based issue analysis and categorization."""

from dataclasses import dataclass
from typing import Any

from globallm.llm.base import BaseLLM
from globallm.llm.prompts import format_issue_categorization_prompt
from globallm.logging_config import get_logger
from globallm.models.issue import (
    Issue,
    IssueCategory,
    IssueRequirements,
)

logger = get_logger(__name__)


@dataclass
class IssueAnalysis:
    """Result of analyzing an issue with LLM."""

    category: IssueCategory
    complexity: int  # 1-10
    solvability: float  # 0-1
    breaking_change: bool
    test_required: bool
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "complexity": self.complexity,
            "solvability": self.solvability,
            "breaking_change": self.breaking_change,
            "test_required": self.test_required,
            "tokens_used": self.tokens_used,
        }


class IssueAnalyzer:
    """Analyze issues using LLMs."""

    def __init__(self, llm: BaseLLM) -> None:
        """Initialize with an LLM instance.

        Args:
            llm: LLM instance for analysis
        """
        self.llm = llm

    def categorize_issue(self, issue: Issue) -> IssueAnalysis:
        """Categorize an issue using LLM.

        Args:
            issue: Issue to categorize

        Returns:
            IssueAnalysis with categorization results
        """
        logger.info("categorizing_issue", repo=issue.repository, number=issue.number)

        prompt = format_issue_categorization_prompt(
            title=issue.title,
            body=issue.body or "",
            labels=issue.labels,
            comment_count=issue.comments_count,
            reactions=issue.reactions,
        )

        try:
            response = self.llm.complete_json(prompt)

            # Parse response
            category_str = response.get("category", "unknown")
            category = IssueCategory.from_string(category_str)

            # Map complexity to 1-10 range
            complexity = max(1, min(10, int(response.get("complexity", 5))))

            solvability = max(0.0, min(1.0, float(response.get("solvability", 0.5))))

            breaking_change = bool(response.get("breaking_change", False))
            test_required = bool(response.get("test_required", True))

            analysis = IssueAnalysis(
                category=category,
                complexity=complexity,
                solvability=solvability,
                breaking_change=breaking_change,
                test_required=test_required,
                tokens_used=response.get("tokens_used", 0),
            )

            logger.info(
                "issue_categorized",
                repo=issue.repository,
                number=issue.number,
                category=category.value,
                complexity=complexity,
                solvability=f"{solvability:.2f}",
            )

            return analysis

        except Exception as e:
            logger.warning(
                "llm_categorization_failed", issue=issue.number, error=str(e)
            )
            # Fallback to basic categorization
            return self._fallback_categorization(issue)

    def estimate_complexity(self, issue: Issue) -> int:
        """Estimate issue complexity without full LLM call.

        Uses heuristics based on issue content.

        Args:
            issue: Issue to analyze

        Returns:
            Complexity estimate (1-10)
        """
        complexity = 5  # Default

        # Adjust based on title length
        if len(issue.title) > 100:
            complexity += 1

        # Adjust based on body length
        if issue.body:
            body_len = len(issue.body)
            if body_len > 2000:
                complexity += 2
            elif body_len > 1000:
                complexity += 1

        # Adjust based on labels
        if any(
            label.lower() in ("good first issue", "beginner", "help wanted")
            for label in issue.labels
        ):
            complexity = min(complexity, 3)
        elif any(
            label.lower() in ("complex", "epic", "architecture")
            for label in issue.labels
        ):
            complexity = min(complexity + 3, 10)

        # Adjust based on category
        if issue.category in (
            IssueCategory.CRITICAL_SECURITY,
            IssueCategory.BUG_CRITICAL,
        ):
            complexity += 2
        elif issue.category in (IssueCategory.DOCUMENTATION, IssueCategory.STYLE):
            complexity = min(complexity, 3)

        return max(1, min(10, complexity))

    def extract_requirements(self, issue: Issue) -> IssueRequirements:
        """Extract requirements from an issue.

        Args:
            issue: Issue to analyze

        Returns:
            IssueRequirements with extracted information
        """
        # Basic extraction from body
        description = issue.body or issue.title

        # Look for code blocks
        import re

        affected_files = []

        # Look for file mentions
        file_mentions = re.findall(
            r"`?([\w./]+\.(?:py|js|ts|go|rs|java))`?", description
        )
        affected_files.extend(file_mentions[:10])

        # Determine breaking change
        breaking_keywords = ["breaking", "deprecated", "remove", "delete", "replace"]
        breaking_change = any(
            keyword in description.lower() for keyword in breaking_keywords
        )

        return IssueRequirements(
            description=description[:1000],  # Truncate long descriptions
            affected_files=list(set(affected_files)),
            complexity=self.estimate_complexity(issue),
            breaking_change=breaking_change,
            test_required=True,
        )

    def _fallback_categorization(self, issue: Issue) -> IssueAnalysis:
        """Fallback categorization when LLM fails.

        Uses labels and heuristics.

        Args:
            issue: Issue to categorize

        Returns:
            IssueAnalysis with basic categorization
        """
        # Category from labels (already set in Issue.from_github_issue)
        category = issue.category

        # Complexity estimation
        complexity = self.estimate_complexity(issue)

        # Solvability based on category
        solvability_map = {
            IssueCategory.CRITICAL_SECURITY: 0.3,
            IssueCategory.BUG_CRITICAL: 0.5,
            IssueCategory.BUG: 0.7,
            IssueCategory.FEATURE: 0.6,
            IssueCategory.DOCUMENTATION: 0.9,
            IssueCategory.STYLE: 0.95,
            IssueCategory.TESTS: 0.8,
        }
        solvability = solvability_map.get(category, 0.6)

        return IssueAnalysis(
            category=category,
            complexity=complexity,
            solvability=solvability,
            breaking_change=False,
            test_required=True,
        )
