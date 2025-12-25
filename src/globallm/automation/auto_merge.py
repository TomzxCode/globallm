"""Auto-merge strategies for PR automation."""

from enum import Enum

from globallm.logging_config import get_logger
from globallm.models.solution import Solution, RiskLevel

logger = get_logger(__name__)


class AutoMergeStrategy(Enum):
    """Auto-merge strategy levels."""

    SAFE = "safe"  # Only auto-merge when all CI passes and risk is low/medium
    CONSERVATIVE = "conservative"  # Require maintainer approval after CI
    MANUAL = "manual"  # No auto-merge, manual review required


def determine_strategy(solution: Solution) -> AutoMergeStrategy:
    """Determine auto-merge strategy based on solution.

    Args:
        solution: Solution to evaluate

    Returns:
        Recommended AutoMergeStrategy
    """
    # CRITICAL risk - never auto-merge
    if solution.risk_level == RiskLevel.CRITICAL:
        logger.info(
            "strategy_manual",
            reason="critical_risk",
            risk_level=solution.risk_level.value,
        )
        return AutoMergeStrategy.MANUAL

    # HIGH risk - manual review
    if solution.risk_level == RiskLevel.HIGH:
        logger.info(
            "strategy_manual",
            reason="high_risk",
            risk_level=solution.risk_level.value,
        )
        return AutoMergeStrategy.MANUAL

    # MEDIUM risk - auto-merge with CI
    if solution.risk_level == RiskLevel.MEDIUM:
        if solution.syntax_valid and solution.tests_generated:
            logger.info(
                "strategy_safe",
                reason="medium_risk_with_tests",
                risk_level=solution.risk_level.value,
            )
            return AutoMergeStrategy.SAFE
        else:
            logger.info(
                "strategy_conservative",
                reason="medium_risk_no_tests",
                risk_level=solution.risk_level.value,
            )
            return AutoMergeStrategy.CONSERVATIVE

    # LOW risk - safe to auto-merge
    if solution.risk_level == RiskLevel.LOW:
        logger.info(
            "strategy_safe",
            reason="low_risk",
            risk_level=solution.risk_level.value,
        )
        return AutoMergeStrategy.SAFE

    # Default to conservative
    logger.warning("strategy_conservative", reason="unknown_risk")
    return AutoMergeStrategy.CONSERVATIVE


def can_enable_auto_merge(solution: Solution) -> bool:
    """Check if auto-merge can be enabled for a solution.

    Args:
        solution: Solution to check

    Returns:
        True if auto-merge is appropriate
    """
    strategy = determine_strategy(solution)

    if strategy == AutoMergeStrategy.MANUAL:
        return False

    if strategy == AutoMergeStrategy.CONSERVATIVE:
        return False

    # SAFE strategy can auto-merge
    return True


def get_auto_merge_requirements(solution: Solution) -> list[str]:
    """Get requirements for auto-merge.

    Args:
        solution: Solution to check

    Returns:
        List of requirements that must be met
    """
    requirements = [
        "- All CI checks must pass",
        "- Code must be syntactically valid",
    ]

    if solution.complexity > 3:
        requirements.append("- Tests must be generated and pass")

    if solution.risk_level == RiskLevel.MEDIUM:
        requirements.append("- No public API changes without documentation")

    if solution.breaking_change:
        return [
            "- Breaking changes require manual review",
            "- Auto-merge disabled for breaking changes",
        ]

    return requirements
