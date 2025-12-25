"""LLM-powered code generation."""

from dataclasses import dataclass
from typing import Any

from globallm.llm.base import BaseLLM
from globallm.llm.prompts import format_code_generation_prompt
from globallm.logging_config import get_logger
from globallm.models.issue import Issue, IssueCategory
from globallm.models.repository import Language
from globallm.models.solution import CodePatch

logger = get_logger(__name__)


@dataclass
class CodeGenerationResult:
    """Result from code generation."""

    explanation: str
    files: list[CodePatch]
    tests: list[CodePatch]
    tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "explanation": self.explanation,
            "files": [
                {
                    "path": f.path,
                    "description": f.description,
                    "lines_added": f.lines_added,
                    "lines_removed": f.lines_removed,
                }
                for f in self.files
            ],
            "tests": [
                {
                    "path": t.path,
                    "description": t.description,
                }
                for t in self.tests
            ],
            "tokens_used": self.tokens_used,
        }


class CodeGenerator:
    """Generate code solutions using LLMs."""

    def __init__(self, llm: BaseLLM) -> None:
        """Initialize code generator.

        Args:
            llm: LLM instance for code generation
        """
        self.llm = llm

    def generate_solution(
        self,
        issue: Issue,
        language: Language,
        repo_context: dict[str, Any] | None = None,
    ) -> CodeGenerationResult:
        """Generate a complete solution for an issue.

        Args:
            issue: Issue to solve
            language: Programming language
            repo_context: Optional repository context

        Returns:
            CodeGenerationResult with patches and explanation
        """
        logger.info(
            "generating_solution",
            repo=issue.repository,
            number=issue.number,
            language=language.value,
        )

        # Build prompt
        prompt = self._build_prompt(issue, language, repo_context)

        try:
            response = self.llm.complete_json(prompt)

            # Parse response
            explanation = response.get("explanation", "")

            files = []
            for file_data in response.get("files", []):
                patch = CodePatch(
                    file_path=file_data["path"],
                    original_content=file_data.get("original_content", ""),
                    new_content=file_data["new_content"],
                    description=file_data.get("description", ""),
                    language=language.value,
                )
                files.append(patch)

            tests = []
            for test_data in response.get("tests", []):
                test_patch = CodePatch(
                    file_path=test_data["path"],
                    original_content="",
                    new_content=test_data["content"],
                    description="Test file",
                    language=language.value,
                )
                tests.append(test_patch)

            result = CodeGenerationResult(
                explanation=explanation,
                files=files,
                tests=tests,
                tokens_used=response.get("tokens_used", 0),
            )

            logger.info(
                "solution_generated",
                repo=issue.repository,
                number=issue.number,
                files=len(files),
                tests=len(tests),
            )

            return result

        except Exception as e:
            logger.error(
                "solution_generation_failed",
                repo=issue.repository,
                number=issue.number,
                error=str(e),
            )
            raise

    def _build_prompt(
        self,
        issue: Issue,
        language: Language,
        repo_context: dict[str, Any] | None = None,
    ) -> str:
        """Build prompt for code generation.

        Args:
            issue: Issue to solve
            language: Programming language
            repo_context: Repository context

        Returns:
            Formatted prompt string
        """
        # Build requirements from issue
        requirements = self._extract_requirements(issue)

        # Add language-specific context
        if repo_context:
            requirements += "\n\nRepository Context:\n"
            if "code_style" in repo_context:
                requirements += f"- Code style: {repo_context['code_style']}\n"
            if "testing_framework" in repo_context:
                requirements += (
                    f"- Testing framework: {repo_context['testing_framework']}\n"
                )

        return format_code_generation_prompt(
            repo=issue.repository,
            language=language.value,
            title=issue.title,
            description=issue.body or "",
            requirements=requirements,
        )

    def _extract_requirements(self, issue: Issue) -> str:
        """Extract requirements from issue.

        Args:
            issue: Issue to analyze

        Returns:
            Requirements string
        """
        requirements = []

        # Add category-specific guidance
        if issue.category == IssueCategory.BUG:
            requirements.append("- Fix the bug without breaking existing functionality")
        elif issue.category == IssueCategory.FEATURE:
            requirements.append(
                "- Implement the new feature following existing patterns"
            )
        elif issue.category == IssueCategory.DOCUMENTATION:
            requirements.append("- Update documentation with clear examples")
        elif issue.category == IssueCategory.PERFORMANCE:
            requirements.append(
                "- Optimize for performance while maintaining correctness"
            )

        # Add safety constraints
        requirements.append("- Ensure type hints are included")
        requirements.append("- Add appropriate error handling")
        requirements.append("- Follow the repository's coding conventions")

        return "\n".join(requirements)

    def generate_fix_only(
        self,
        issue: Issue,
        file_path: str,
        original_content: str,
        language: Language,
    ) -> CodePatch:
        """Generate a fix for a single file.

        Args:
            issue: Issue to fix
            file_path: Path to file to fix
            original_content: Original file content
            language: Programming language

        Returns:
            CodePatch with the fix
        """
        logger.info(
            "generating_fix",
            repo=issue.repository,
            number=issue.number,
            file=file_path,
        )

        prompt = f"""Generate a fix for this GitHub issue.

Repository: {issue.repository}
Language: {language.value}
File: {file_path}

Issue:
Title: {issue.title}
Description: {issue.body or ""}

Original file content:
```
{original_content}
```

Generate the complete fixed file content. Respond with JSON:
{{
  "explanation": "what was fixed",
  "new_content": "complete fixed file content",
  "risk_level": "low" | "medium" | "high"
}}
"""

        try:
            response = self.llm.complete_json(prompt)

            return CodePatch(
                file_path=file_path,
                original_content=original_content,
                new_content=response.get("new_content", original_content),
                description=response.get("explanation", "Bug fix"),
                language=language.value,
            )

        except Exception as e:
            logger.error("fix_generation_failed", file=file_path, error=str(e))
            raise


# Language-specific code style guidance
LANGUAGE_STYLES: dict[Language, dict[str, str]] = {
    Language.PYTHON: {
        "indentation": "4 spaces",
        "naming": "snake_case for functions/variables, PascalCase for classes",
        "docstrings": "Google style docstrings",
        "typing": "Use type hints from typing module",
    },
    Language.JAVASCRIPT: {
        "indentation": "2 spaces",
        "naming": "camelCase for functions/variables, PascalCase for classes",
        "semicolons": "Always use semicolons",
    },
    Language.TYPESCRIPT: {
        "indentation": "2 spaces",
        "naming": "camelCase for functions/variables, PascalCase for classes",
        "types": "Always specify types",
    },
    Language.GO: {
        "indentation": "tab",
        "naming": "PascalCase for exports, camelCase for internal",
        "errors": "Always handle errors explicitly",
    },
    Language.RUST: {
        "indentation": "4 spaces",
        "naming": "snake_case for functions/variables, PascalCase for types",
        "errors": "Use Result types for error handling",
    },
    Language.JAVA: {
        "indentation": "4 spaces",
        "naming": "camelCase for methods, PascalCase for classes",
        "access": "Explicit access modifiers",
    },
}


def get_language_style(language: Language) -> dict[str, str]:
    """Get coding style guidelines for a language.

    Args:
        language: Programming language

    Returns:
        Dict of style guidelines
    """
    return LANGUAGE_STYLES.get(language, {})
