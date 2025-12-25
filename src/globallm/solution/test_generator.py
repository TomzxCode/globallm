"""Test generation for solutions."""

from dataclasses import dataclass

from globallm.llm.base import BaseLLM
from globallm.logging_config import get_logger
from globallm.models.repository import Language
from globallm.models.solution import CodePatch

logger = get_logger(__name__)


@dataclass
class TestGenerationResult:
    """Result from test generation."""

    test_patches: list[CodePatch]
    explanation: str
    tokens_used: int = 0


# Testing framework by language
LANGUAGE_TEST_FRAMEWORKS: dict[Language, str] = {
    Language.PYTHON: "pytest",
    Language.JAVASCRIPT: "jest",
    Language.TYPESCRIPT: "jest",
    Language.GO: "testing",
    Language.RUST: "cargo test",
    Language.JAVA: "JUnit",
}


class TestGenerator:
    """Generate tests for solutions."""

    def __init__(self, llm: BaseLLM) -> None:
        """Initialize test generator.

        Args:
            llm: LLM instance for test generation
        """
        self.llm = llm

    def generate_tests(
        self,
        code_patches: list[CodePatch],
        language: Language,
        issue_description: str,
    ) -> TestGenerationResult:
        """Generate tests for code patches.

        Args:
            code_patches: Code patches to test
            language: Programming language
            issue_description: Description of what's being tested

        Returns:
            TestGenerationResult with test patches
        """
        logger.info(
            "generating_tests",
            patches_count=len(code_patches),
            language=language.value,
        )

        framework = LANGUAGE_TEST_FRAMEWORKS.get(language, "unittest")

        prompt = self._build_prompt(
            code_patches, language, framework, issue_description
        )

        try:
            response = self.llm.complete_json(prompt)

            tests = []
            for test_data in response.get("tests", []):
                test_patch = CodePatch(
                    file_path=test_data["path"],
                    original_content="",
                    new_content=test_data["content"],
                    description=test_data.get("description", "Test"),
                    language=language.value,
                )
                tests.append(test_patch)

            result = TestGenerationResult(
                test_patches=tests,
                explanation=response.get("explanation", ""),
                tokens_used=response.get("tokens_used", 0),
            )

            logger.info(
                "tests_generated",
                count=len(tests),
                framework=framework,
            )

            return result

        except Exception as e:
            logger.error("test_generation_failed", error=str(e))
            raise

    def _build_prompt(
        self,
        code_patches: list[CodePatch],
        language: Language,
        framework: str,
        issue_description: str,
    ) -> str:
        """Build prompt for test generation.

        Args:
            code_patches: Code patches to test
            language: Programming language
            framework: Testing framework name
            issue_description: What the code does

        Returns:
            Formatted prompt
        """
        # Summarize code changes
        code_summary = "\n\n".join(
            f"File: {p.file_path}\n{p.description}\n```{language.value}\n{p.new_content[:500]}...\n```"
            for p in code_patches[:3]  # Limit to 3 files for context
        )

        prompt = f"""Generate comprehensive tests for the following code changes.

Language: {language.value}
Testing Framework: {framework}

Issue Context:
{issue_description}

Code Changes:
{code_summary}

Generate tests that:
1. Cover the main functionality
2. Include edge cases
3. Test error conditions
4. Follow {framework} best practices

Respond with JSON:
{{
  "explanation": "overview of test strategy",
  "tests": [
    {{
      "path": "path/to/test_file.ext",
      "content": "complete test file content",
      "description": "what these tests cover"
    }}
  ]
}}
"""

        return prompt

    def generate_unit_test(
        self,
        function_name: str,
        function_code: str,
        language: Language,
        test_file_path: str,
    ) -> CodePatch:
        """Generate a unit test for a single function.

        Args:
            function_name: Name of function to test
            function_code: Function code
            language: Programming language
            test_file_path: Where to write the test

        Returns:
            CodePatch with test content
        """
        framework = LANGUAGE_TEST_FRAMEWORKS.get(language, "unittest")

        prompt = f"""Generate a unit test for this function.

Language: {language.value}
Testing Framework: {framework}

Function: {function_name}

```{language.value}
{function_code}
```

Generate a comprehensive unit test that covers:
- Normal operation
- Edge cases
- Error conditions

Respond with JSON:
{{
  "content": "complete test file content",
  "description": "what the test covers"
}}
"""

        try:
            response = self.llm.complete_json(prompt)

            return CodePatch(
                file_path=test_file_path,
                original_content="",
                new_content=response.get("content", ""),
                description=response.get("description", f"Test for {function_name}"),
                language=language.value,
            )

        except Exception as e:
            logger.error(
                "unit_test_generation_failed", function=function_name, error=str(e)
            )
            raise

    def generate_test_for_patch(
        self,
        patch: CodePatch,
        language: Language,
        existing_tests: str | None = None,
    ) -> CodePatch:
        """Generate tests for a specific code patch.

        Args:
            patch: Code patch to generate tests for
            language: Programming language
            existing_tests: Optional existing test content

        Returns:
            CodePatch with test content
        """
        framework = LANGUAGE_TEST_FRAMEWORKS.get(language, "unittest")

        # Derive test file path from patch path
        test_file = self._infer_test_path(patch.file_path, language)

        existing_section = ""
        if existing_tests:
            existing_section = f"\nExisting tests:\n```\n{existing_tests[:1000]}\n```\n"

        prompt = f"""Generate tests for this code change.

Language: {language.value}
Testing Framework: {framework}

Code Change:
File: {patch.file_path}
Description: {patch.description}

```{language.value}
{patch.new_content}
```
{existing_section}

Generate tests that verify the code change works correctly.
If there are existing tests, add new test cases to them.

Respond with JSON:
{{
  "content": "complete test file content (including existing tests if provided)",
  "description": "what the tests verify"
}}
"""

        try:
            response = self.llm.complete_json(prompt)

            return CodePatch(
                file_path=test_file,
                original_content=existing_tests or "",
                new_content=response.get("content", ""),
                description=response.get("description", "Tests for patch"),
                language=language.value,
            )

        except Exception as e:
            logger.error(
                "patch_test_generation_failed", file=patch.file_path, error=str(e)
            )
            raise

    def _infer_test_path(self, source_path: str, language: Language) -> str:
        """Infer test file path from source file path.

        Args:
            source_path: Source file path
            language: Programming language

        Returns:
            Inferred test file path
        """
        # Common test directory patterns
        test_patterns = {
            Language.PYTHON: ["tests/", "test_"],
            Language.JAVASCRIPT: ["__tests__/", ".test.", ".spec."],
            Language.TYPESCRIPT: ["__tests__/", ".test.", ".spec."],
            Language.GO: ["_test.go"],
            Language.RUST: ["tests/", "_test.rs"],
            Language.JAVA: ["src/test/", "Test.java"],
        }

        patterns = test_patterns.get(language, ["tests/"])

        # Try to find existing test pattern
        for pattern in patterns:
            if pattern in source_path:
                return source_path

        # Default: construct test path
        if language == Language.PYTHON:
            # test_<module>.py or tests/<module>/test_<module>.py
            module = source_path.replace(".py", "").replace("/", ".")
            return f"tests/test_{module}.py"
        elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            # <file>.test.js or __tests__/<file>.test.js
            base = source_path.replace(".ts", "").replace(".js", "")
            return f"{base}.test.js"
        elif language == Language.GO:
            # <file>_test.go (same directory)
            return source_path.replace(".go", "_test.go")
        elif language == Language.RUST:
            # tests/<module>_test.rs or integration test
            module = source_path.replace("src/", "").replace(".rs", "")
            return f"tests/{module}_test.rs"
        else:
            return f"tests/{source_path}"

    def get_test_framework(self, language: Language) -> str:
        """Get the testing framework for a language.

        Args:
            language: Programming language

        Returns:
            Framework name
        """
        return LANGUAGE_TEST_FRAMEWORKS.get(language, "unittest")
