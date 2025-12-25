"""Solution generation orchestration engine."""

from dataclasses import dataclass, field

from globallm.issues.analyzer import IssueAnalyzer
from globallm.logging_config import get_logger
from globallm.models.issue import Issue
from globallm.models.repository import Language, RepoCandidate
from globallm.models.solution import Solution, RiskLevel, SolutionStatus
from globallm.solution.code_generator import CodeGenerator
from globallm.solution.test_generator import TestGenerator
from globallm.solution.validator import SolutionValidator

logger = get_logger(__name__)


@dataclass
class GenerationOptions:
    """Options for solution generation."""

    generate_tests: bool = True
    run_validation: bool = True
    require_type_hints: bool = True
    max_complexity: int = 7
    auto_merge_enabled: bool = True


@dataclass
class GenerationResult:
    """Result from solution generation."""

    solution: Solution | None
    success: bool
    error: str | None = None
    tokens_used: int = 0
    warnings: list[str] = field(default_factory=list)


class SolutionEngine:
    """Orchestrate multi-step solution generation."""

    def __init__(
        self,
        analyzer: IssueAnalyzer,
        code_generator: CodeGenerator,
        test_generator: TestGenerator | None = None,
        validator: SolutionValidator | None = None,
    ) -> None:
        """Initialize solution engine.

        Args:
            analyzer: Issue analyzer
            code_generator: Code generator
            test_generator: Optional test generator
            validator: Optional solution validator
        """
        self.analyzer = analyzer
        self.code_generator = code_generator
        self.test_generator = test_generator
        self.validator = validator

    def generate_solution(
        self,
        issue: Issue,
        repo: RepoCandidate | None = None,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        """Generate a complete solution for an issue.

        Pipeline:
        1. Analyze issue (category, complexity, solvability)
        2. Check feasibility
        3. Generate code patches
        4. Generate tests (if enabled)
        5. Validate solution (if enabled)
        6. Create Solution object

        Args:
            issue: Issue to solve
            repo: Repository candidate (optional)
            options: Generation options

        Returns:
            GenerationResult with solution or error
        """
        options = options or GenerationOptions()

        logger.info(
            "generating_solution_start",
            repo=issue.repository,
            number=issue.number,
        )

        tokens_used = 0
        warnings = []

        try:
            # Step 1: Analyze issue
            logger.info("step_1_analyze", issue_number=issue.number)
            analysis = self.analyzer.categorize_issue(issue)
            tokens_used += analysis.tokens_used

            # Check complexity threshold
            if analysis.complexity > options.max_complexity:
                return GenerationResult(
                    solution=None,
                    success=False,
                    error=f"Complexity {analysis.complexity} exceeds max {options.max_complexity}",
                    tokens_used=tokens_used,
                )

            # Check solvability
            if analysis.solvability < 0.3:
                return GenerationResult(
                    solution=None,
                    success=False,
                    error=f"Low solvability: {analysis.solvability:.2f}",
                    tokens_used=tokens_used,
                )

            # Step 2: Check feasibility
            logger.info("step_2_feasibility", issue_number=issue.number)
            if self.validator:
                feasibility = self.validator.estimate_feasibility(
                    issue_description=issue.body or issue.title,
                    language=repo.language if repo else Language.PYTHON,
                    complexity=analysis.complexity,
                )
                tokens_used += feasibility.estimated_tokens

                if not feasibility.is_feasible:
                    return GenerationResult(
                        solution=None,
                        success=False,
                        error=f"Not feasible: {', '.join(feasibility.blockers)}",
                        tokens_used=tokens_used,
                    )

                warnings.extend(feasibility.reasons)

            # Step 3: Generate code
            logger.info("step_3_generate_code", issue_number=issue.number)
            language = repo.language if repo else Language.PYTHON
            if language is None:
                language = Language.PYTHON

            code_result = self.code_generator.generate_solution(
                issue, language, repo_context=None
            )
            tokens_used += code_result.tokens_used

            # Step 4: Generate tests
            test_patches = []
            if options.generate_tests and self.test_generator:
                logger.info("step_4_generate_tests", issue_number=issue.number)
                test_result = self.test_generator.generate_tests(
                    code_result.files,
                    language,
                    issue.body or issue.title,
                )
                test_patches = test_result.test_patches
                tokens_used += test_result.tokens_used

            # Step 5: Validate
            syntax_valid = True
            if options.run_validation and self.validator:
                logger.info("step_5_validate", issue_number=issue.number)

                # Create temporary solution for validation
                temp_solution = Solution(
                    issue_url=issue.url,
                    repository=issue.repository,
                    issue_number=issue.number,
                    issue_title=issue.title,
                    description=code_result.explanation,
                    patches=code_result.files,
                    test_patches=test_patches,
                    complexity=analysis.complexity,
                    risk_level=RiskLevel.from_complexity(analysis.complexity),
                    status=SolutionStatus.DRAFT,
                    tokens_used=tokens_used,
                    breaking_change=analysis.breaking_change,
                )

                validation = self.validator.validate_solution(temp_solution)
                tokens_used += 500  # Approximate validation cost

                syntax_valid = validation.syntax_valid

                if not validation.is_valid:
                    warnings.extend(validation.issues)

                if not validation.syntax_valid:
                    return GenerationResult(
                        solution=None,
                        success=False,
                        error=f"Validation failed: {', '.join(validation.issues)}",
                        tokens_used=tokens_used,
                        warnings=warnings,
                    )

            # Step 6: Create solution object
            logger.info("step_6_create_solution", issue_number=issue.number)

            risk_level = RiskLevel.from_complexity(analysis.complexity)
            if analysis.breaking_change:
                risk_level = RiskLevel.CRITICAL

            solution = Solution(
                issue_url=issue.url,
                repository=issue.repository,
                issue_number=issue.number,
                issue_title=issue.title,
                description=code_result.explanation,
                patches=code_result.files,
                test_patches=test_patches,
                complexity=analysis.complexity,
                risk_level=risk_level,
                status=SolutionStatus.READY,
                tokens_used=tokens_used,
                llm_model=self.code_generator.llm.model,
                syntax_valid=syntax_valid,
                tests_generated=len(test_patches) > 0,
                breaking_change=analysis.breaking_change,
            )

            logger.info(
                "solution_generated_success",
                repo=issue.repository,
                number=issue.number,
                patches=len(solution.patches),
                tests=len(solution.test_patches),
                tokens=tokens_used,
            )

            return GenerationResult(
                solution=solution,
                success=True,
                tokens_used=tokens_used,
                warnings=warnings,
            )

        except Exception as e:
            logger.error(
                "solution_generation_failed",
                repo=issue.repository,
                number=issue.number,
                error=str(e),
            )
            return GenerationResult(
                solution=None,
                success=False,
                error=str(e),
                tokens_used=tokens_used,
                warnings=warnings,
            )

    def estimate_cost(self, issue: Issue, complexity: int = 5) -> int:
        """Estimate token cost to generate solution for an issue.

        Args:
            issue: Issue to solve
            complexity: Estimated complexity

        Returns:
            Estimated token count
        """
        # Categorization
        tokens = 500

        # Feasibility check
        tokens += 300

        # Code generation (scales with complexity)
        tokens += 1000 + (complexity * 500)

        # Test generation
        tokens += 800

        # Validation
        tokens += 500

        return tokens

    def can_generate(
        self, issue: Issue, repo: RepoCandidate | None, max_tokens: int
    ) -> bool:
        """Check if solution can be generated within budget.

        Args:
            issue: Issue to check
            repo: Repository (optional)
            max_tokens: Maximum tokens allowed

        Returns:
            True if within budget
        """
        # Quick complexity estimate
        complexity = self.analyzer.estimate_complexity(issue)
        estimated = self.estimate_cost(issue, complexity)

        return estimated <= max_tokens
