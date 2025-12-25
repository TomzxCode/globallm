"""Default configuration values."""

from globallm.config.settings import (
    Settings,
    FilterSettings,
    LanguageSettings,
    BudgetSettings,
    PrioritySettings,
    IssueCategorySettings,
)
from globallm.models.repository import Language

DEFAULT_CONFIG: Settings = Settings(
    filters=FilterSettings(
        min_stars=1000,
        min_dependents=100,
        min_health_score=0.5,
        max_days_since_last_commit=365,
        require_ci=True,
        require_tests=True,
    ),
    languages={
        Language.PYTHON: LanguageSettings(
            min_test_coverage=0.6,
            require_pyproject_toml=True,
        ),
        Language.JAVASCRIPT: LanguageSettings(
            min_test_coverage=0.5,
            require_package_json=True,
        ),
        Language.TYPESCRIPT: LanguageSettings(
            min_test_coverage=0.5,
            require_package_json=True,
        ),
        Language.GO: LanguageSettings(
            min_test_coverage=0.5,
            require_go_mod=True,
        ),
        Language.RUST: LanguageSettings(
            min_test_coverage=0.6,
            require_cargo_toml=True,
        ),
        Language.JAVA: LanguageSettings(
            min_test_coverage=0.5,
            require_pom_xml=True,
        ),
    },
    budget=BudgetSettings(
        max_tokens_per_repo=100_000,
        max_time_per_repo=3600,
        max_issues_per_language=50,
        max_issues_per_repo=5,
        weekly_token_budget=5_000_000,
    ),
    priority=PrioritySettings(
        health_weight=1.0,
        impact_weight=2.0,
        solvability_weight=1.5,
        urgency_weight=0.5,
    ),
    issue_categories={
        "critical_security": IssueCategorySettings(multiplier=10.0),
        "bug_critical": IssueCategorySettings(multiplier=5.0),
        "feature": IssueCategorySettings(multiplier=2.0),
        "documentation": IssueCategorySettings(multiplier=1.0),
        "style": IssueCategorySettings(multiplier=0.1),
    },
)

# Export as dict for YAML serialization
DEFAULT_CONFIG_DICT: dict = DEFAULT_CONFIG.model_dump(mode="json")
