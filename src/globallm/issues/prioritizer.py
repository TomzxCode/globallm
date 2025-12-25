"""Multi-factor issue prioritization."""

from globallm.analysis.impact_calculator import ImpactCalculator
from globallm.filtering.health_scorer import HealthScorer
from globallm.issues.analyzer import IssueAnalyzer, IssueAnalysis
from globallm.logging_config import get_logger
from globallm.models.issue import Issue
from globallm.models.priority import PriorityScore, PriorityContext
from globallm.models.repository import Language, RepoCandidate

logger = get_logger(__name__)


class IssuePrioritizer:
    """Prioritize issues using multiple factors.

    Factors:
    - Health: Repository health score
    - Impact: Dependency graph impact
    - Solvability: Likelihood of successful automated fix
    - Urgency: Issue category, age, engagement
    """

    def __init__(
        self,
        analyzer: IssueAnalyzer,
        impact_calculator: ImpactCalculator | None = None,
        health_scorer: HealthScorer | None = None,
        context: PriorityContext | None = None,
    ) -> None:
        """Initialize prioritizer.

        Args:
            analyzer: IssueAnalyzer for categorization
            impact_calculator: Optional ImpactCalculator for graph metrics
            health_scorer: Optional HealthScorer for repo health
            context: PriorityContext for weights and budget
        """
        self.analyzer = analyzer
        self.impact_calculator = impact_calculator
        self.health_scorer = health_scorer
        self.context = context or PriorityContext()

    def calculate_priority(
        self,
        issue: Issue,
        repo: RepoCandidate | None = None,
        analysis: IssueAnalysis | None = None,
    ) -> PriorityScore:
        """Calculate priority score for an issue.

        Args:
            issue: Issue to score
            repo: Repository candidate (optional)
            analysis: Pre-computed analysis (optional)

        Returns:
            PriorityScore with all components
        """
        logger.debug(
            "calculating_priority",
            repo=issue.repository,
            number=issue.number,
        )

        # Run analysis if not provided
        if analysis is None:
            analysis = self.analyzer.categorize_issue(issue)

        # Calculate health score
        health_score = self._calculate_health(issue, repo, analysis)

        # Calculate impact score
        impact_score = self._calculate_impact(issue, repo)

        # Solvability from analysis
        solvability_score = analysis.solvability

        # Calculate urgency score
        urgency_score = self._calculate_urgency(issue, analysis)

        # Build component dicts for debugging
        health_components = {
            "repo_health": health_score,
            "complexity_factor": 1.0 - (analysis.complexity / 10),
        }

        impact_components = {
            "base_impact": impact_score,
        }

        solvability_components = {
            "llm_solvability": solvability_score,
            "category_factor": analysis.category.multiplier / 10,
        }

        urgency_components = {
            "category_multiplier": analysis.category.multiplier,
            "age_days": issue.age_days,
            "engagement": issue.engagement_score,
        }

        # Calculate overall score
        priority = PriorityScore.calculate(
            health=health_score,
            impact=impact_score,
            solvability=solvability_score,
            urgency=urgency_score,
            context=self.context,
        )

        # Update components
        priority.health_components = health_components
        priority.impact_components = impact_components
        priority.solvability_components = solvability_components
        priority.urgency_components = urgency_components

        # Update issue's priority score
        issue.priority_score = priority.overall

        logger.info(
            "priority_calculated",
            repo=issue.repository,
            number=issue.number,
            overall=f"{priority.overall:.2f}",
            category=analysis.category.value,
        )

        return priority

    def _calculate_health(
        self, issue: Issue, repo: RepoCandidate | None, analysis: IssueAnalysis
    ) -> float:
        """Calculate health factor.

        Combines repository health with complexity-adjusted factor.
        """
        if repo and repo.health_score:
            repo_health = repo.health_score.overall
        else:
            repo_health = 0.5  # Neutral

        # Adjust for complexity - simpler issues get higher health factor
        complexity_factor = 1.0 - (analysis.complexity / 20)  # 0.5 to 1.0 range

        return (repo_health * 0.7) + (complexity_factor * 0.3)

    def _calculate_impact(self, issue: Issue, repo: RepoCandidate | None) -> float:
        """Calculate impact factor.

        Based on repository stars, dependents, and potential impact.
        """
        if not repo:
            return 0.5  # Neutral

        # Normalize impact (rough approximation)
        # Stars: log scale, max around 500k
        stars_impact = min(repo.stars / 50000, 1.0)

        # Dependents: max around 10k
        dep_impact = min(repo.dependents / 5000, 1.0)

        # Watchers/subscribers
        watchers_impact = min(repo.watchers / 5000, 1.0)

        return (stars_impact * 0.4) + (dep_impact * 0.4) + (watchers_impact * 0.2)

    def _calculate_urgency(self, issue: Issue, analysis: IssueAnalysis) -> float:
        """Calculate urgency factor.

        Combines category multiplier, age, and engagement.
        """
        # Base from category
        category_urgency = analysis.category.multiplier / 10  # 0-1 range

        # Age factor (older = more urgent, up to a point)
        age_factor = min(issue.age_days / 365, 1.0)  # Max at 1 year

        # Engagement factor
        engagement_factor = min(issue.engagement_score / 50, 1.0)

        return category_urgency * 0.5 + age_factor * 0.3 + engagement_factor * 0.2

    def rank_issues(
        self,
        issues: list[Issue],
        repos: dict[str, RepoCandidate] | None = None,
    ) -> list[tuple[Issue, PriorityScore]]:
        """Rank a list of issues by priority.

        Args:
            issues: List of issues to rank
            repos: Optional dict of repo_name -> RepoCandidate

        Returns:
            List of (issue, priority_score) tuples sorted by priority
        """
        logger.info("ranking_issues", count=len(issues))

        results: list[tuple[Issue, PriorityScore]] = []

        for issue in issues:
            repo = repos.get(issue.repository) if repos else None
            priority = self.calculate_priority(issue, repo)
            results.append((issue, priority))

        # Sort by overall priority (descending)
        results.sort(key=lambda x: x[1].overall, reverse=True)

        logger.info("issues_ranked", count=len(results))
        return results

    def filter_by_budget(
        self,
        ranked_issues: list[tuple[Issue, PriorityScore]],
        language: Language,
    ) -> list[tuple[Issue, PriorityScore]]:
        """Filter issues by budget constraints.

        Args:
            ranked_issues: Pre-ranked list of (issue, priority_score)
            language: Language for budget tracking

        Returns:
            Filtered list within budget
        """
        results = []
        total_tokens = 0

        for issue, priority in ranked_issues:
            # Estimate tokens for this issue
            estimated_tokens = self._estimate_tokens(issue, priority)

            # Check budget
            if not self.context.can_process_issue(issue.repository, language):
                logger.info(
                    "budget_limit_reached",
                    repo=issue.repository,
                    language=language.value,
                )
                break

            if (
                total_tokens + estimated_tokens
                > self.context.budget.weekly_token_budget
            ):
                logger.info("weekly_budget_limit_reached")
                break

            results.append((issue, priority))
            total_tokens += estimated_tokens

            # Record usage
            self.context.record_usage(
                issue.repository, language.value, estimated_tokens
            )

        logger.info(
            "filtered_by_budget",
            input_count=len(ranked_issues),
            output_count=len(results),
            estimated_tokens=total_tokens,
        )

        return results

    def _estimate_tokens(self, issue: Issue, priority: PriorityScore) -> int:
        """Estimate tokens needed to address an issue.

        Rough estimate based on complexity.
        """
        # Base: categorization cost
        base_tokens = 500

        # Solution generation: scales with complexity
        complexity = priority.solvability_components.get("complexity", 5)
        solution_tokens = complexity * 1000  # 1k tokens per complexity point

        # Review/validation
        review_tokens = 500

        return base_tokens + solution_tokens + review_tokens
