"""Solution validation and self-review."""

import ast
import re
from dataclasses import dataclass

from globallm.llm.base import BaseLLM
from globallm.logging_config import get_logger
from globallm.models.repository import Language
from globallm.models.solution import Solution, CodePatch, FeasibilityReport, RiskLevel

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result from solution validation."""

    is_valid: bool
    syntax_valid: bool
    type_hints_present: bool
    error_handling_present: bool
    tests_generated: bool
    issues: list[str]
    confidence: float  # 0-1


class SolutionValidator:
    """Validate generated solutions."""

    def __init__(self, llm: BaseLLM | None = None) -> None:
        """Initialize validator.

        Args:
            llm: Optional LLM for advanced validation
        """
        self.llm = llm

    def validate_solution(self, solution: Solution) -> ValidationResult:
        """Validate a complete solution.

        Args:
            solution: Solution to validate

        Returns:
            ValidationResult with validation results
        """
        logger.info(
            "validating_solution",
            repo=solution.repository,
            issue_number=solution.issue_number,
        )

        issues = []
        confidence = 1.0

        # Check syntax for each patch
        syntax_valid = True
        for patch in solution.patches:
            if not self._validate_syntax(patch, solution.language or "python"):
                syntax_valid = False
                issues.append(f"Syntax error in {patch.file_path}")
                confidence -= 0.3

        # Check for type hints
        type_hints = self._check_type_hints(solution)
        if not type_hints and solution.language in ("python", "typescript", "rust"):
            issues.append("Missing type hints")
            confidence -= 0.1

        # Check for error handling
        error_handling = self._check_error_handling(solution)
        if not error_handling:
            issues.append("Insufficient error handling")
            confidence -= 0.1

        # Check tests
        tests_generated = len(solution.test_patches) > 0
        if not tests_generated and solution.complexity > 3:
            issues.append(f"No tests for complexity {solution.complexity}")
            confidence -= 0.2

        # LLM-based review if available
        if self.llm and syntax_valid:
            llm_issues = self._llm_review(solution)
            issues.extend(llm_issues)
            if llm_issues:
                confidence -= min(0.3, len(llm_issues) * 0.1)

        return ValidationResult(
            is_valid=syntax_valid and len(issues) == 0,
            syntax_valid=syntax_valid,
            type_hints_present=type_hints,
            error_handling_present=error_handling,
            tests_generated=tests_generated,
            issues=issues,
            confidence=max(0.0, confidence),
        )

    def _validate_syntax(self, patch: CodePatch, language: str) -> bool:
        """Validate syntax of a code patch.

        Args:
            patch: Code patch to validate
            language: Programming language

        Returns:
            True if syntax is valid
        """
        try:
            match language:
                case "python":
                    ast.parse(patch.new_content)
                    return True
                case "javascript" | "typescript" | "json":
                    # Basic JS syntax check
                    # (Full validation would require a JS parser)
                    return bool(patch.new_content.strip())
                case _:
                    # For other languages, do basic checks
                    return bool(patch.new_content.strip())
        except SyntaxError:
            return False
        except Exception:
            # If parsing fails, assume invalid
            return False

    def _check_type_hints(self, solution: Solution) -> bool:
        """Check if type hints are present.

        Args:
            solution: Solution to check

        Returns:
            True if type hints detected
        """
        hint_indicators = {
            "python": [": ", "def ", "->"],
            "typescript": [": "],
            "rust": [": "],
            "go": [": "],
        }

        language = solution.language or "python"
        indicators = hint_indicators.get(language.lower(), [])

        for patch in solution.patches:
            content = patch.new_content
            for indicator in indicators:
                if indicator in content:
                    return True

        return False

    def _check_error_handling(self, solution: Solution) -> bool:
        """Check if error handling is present.

        Args:
            solution: Solution to check

        Returns:
            True if error handling detected
        """
        error_patterns = [
            r"try\s*:",
            r"except",
            r"catch",
            r"error\s*=",
            r"Error\(",
            r"throw\s+new",
            r"raise\s+",
            r"\.unwrap\(\)",  # Rust explicit unwrap
            r"\?expect\(",  # Rust expect
        ]

        combined = re.compile("|".join(error_patterns), re.IGNORECASE)

        for patch in solution.patches:
            if combined.search(patch.new_content):
                return True

        return False

    def _llm_review(self, solution: Solution) -> list[str]:
        """Use LLM to review solution quality.

        Args:
            solution: Solution to review

        Returns:
            List of issues found
        """
        prompt = f"""Review this code solution for quality and correctness.

Repository: {solution.repository}
Issue: {solution.issue_title}
Description: {solution.description}

Code Changes:
{self._format_patches(solution.patches)}

Review for:
1. Logic errors
2. Edge cases not handled
3. Security vulnerabilities
4. Performance issues
5. Code smell

Respond with JSON:
{{
  "issues": ["issue 1", "issue 2"],
  "confidence": 0.0-1.0
}}
"""

        try:
            response = self.llm.complete_json(prompt)
            return response.get("issues", [])
        except Exception as e:
            logger.warning("llm_review_failed", error=str(e))
            return []

    def _format_patches(self, patches: list[CodePatch]) -> str:
        """Format patches for review.

        Args:
            patches: Patches to format

        Returns:
            Formatted string
        """
        formatted = []
        for patch in patches[:5]:  # Limit to 5 patches
            formatted.append(f"File: {patch.file_path}")
            formatted.append(f"Description: {patch.description}")
            formatted.append("```")
            formatted.append(patch.new_content[:1000])  # Truncate long files
            if len(patch.new_content) > 1000:
                formatted.append("... (truncated)")
            formatted.append("```")
            formatted.append("")

        return "\n".join(formatted)

    def estimate_feasibility(
        self,
        issue_description: str,
        language: Language,
        complexity: int = 5,
        files_count: int = 1,
    ) -> FeasibilityReport:
        """Estimate feasibility of solving an issue.

        Args:
            issue_description: Issue to analyze
            language: Programming language
            complexity: Estimated complexity (1-10)
            files_count: Number of files affected

        Returns:
            FeasibilityReport with assessment
        """
        # Determine risk level
        risk_level = RiskLevel.from_complexity(complexity)

        # Estimate tokens
        base_tokens = 500
        complexity_tokens = complexity * 1000
        file_tokens = files_count * 500
        review_tokens = 500
        estimated_tokens = base_tokens + complexity_tokens + file_tokens + review_tokens

        # Estimate time
        estimated_time = max(60, complexity * 300)  # 1min minimum

        # Calculate confidence
        confidence = 1.0
        if complexity > 7:
            confidence -= 0.3
        if files_count > 5:
            confidence -= 0.2
        if risk_level == RiskLevel.CRITICAL:
            confidence -= 0.4

        confidence = max(0.0, confidence)

        # Generate reasons
        reasons = []
        blockers = []

        if complexity <= 3:
            reasons.append("Low complexity suggests high success rate")
        elif complexity >= 8:
            blockers.append("High complexity increases risk")

        if files_count <= 2:
            reasons.append("Few files affected reduces risk")
        elif files_count >= 5:
            blockers.append("Multiple files increase complexity")

        return FeasibilityReport(
            is_feasible=confidence > 0.3,
            confidence=confidence,
            estimated_tokens=estimated_tokens,
            estimated_time_seconds=estimated_time,
            risk_level=risk_level,
            reasons=reasons,
            blockers=blockers,
        )

    def verify_solution_feasibility(self, solution: Solution) -> FeasibilityReport:
        """Verify a solution is feasible to implement.

        Args:
            solution: Solution to verify

        Returns:
            FeasibilityReport
        """
        # Check if solution passes basic validation
        validation = self.validate_solution(solution)

        if not validation.syntax_valid:
            return FeasibilityReport(
                is_feasible=False,
                confidence=0.0,
                estimated_tokens=0,
                estimated_time_seconds=0,
                risk_level=RiskLevel.CRITICAL,
                blockers=["Syntax errors in generated code"],
            )

        # Estimate based on solution properties
        return self.estimate_feasibility(
            issue_description=solution.description,
            language=Language(solution.language)
            if solution.language
            else Language.PYTHON,
            complexity=solution.complexity,
            files_count=len(solution.patches),
        )
