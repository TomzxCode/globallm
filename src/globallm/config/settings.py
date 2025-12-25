"""Configuration settings using Pydantic."""

from pydantic import BaseModel, Field, field_validator

from globallm.models.repository import Language


class FilterSettings(BaseModel):
    """Repository filter settings."""

    min_stars: int = Field(default=1000, ge=0, description="Minimum GitHub stars")
    min_dependents: int = Field(
        default=100, ge=0, description="Minimum dependent packages"
    )
    min_health_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum health score"
    )
    max_days_since_last_commit: int = Field(
        default=365, ge=0, description="Maximum days since last commit"
    )
    require_ci: bool = Field(default=True, description="Require CI configuration")
    require_tests: bool = Field(default=True, description="Require test directory")


class LanguageSettings(BaseModel):
    """Language-specific settings."""

    min_test_coverage: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum test coverage"
    )
    require_pyproject_toml: bool = Field(
        default=False, description="Require pyproject.toml (Python)"
    )
    require_package_json: bool = Field(
        default=False, description="Require package.json (JS/TS)"
    )
    require_go_mod: bool = Field(default=False, description="Require go.mod (Go)")
    require_cargo_toml: bool = Field(
        default=False, description="Require Cargo.toml (Rust)"
    )
    require_pom_xml: bool = Field(default=False, description="Require pom.xml (Java)")


class BudgetSettings(BaseModel):
    """Budget and resource limits."""

    max_tokens_per_repo: int = Field(
        default=100_000, ge=0, description="Max tokens per repository"
    )
    max_time_per_repo: int = Field(
        default=3600, ge=0, description="Max seconds per repository"
    )
    max_issues_per_language: int = Field(
        default=50, ge=0, description="Max issues per language"
    )
    max_issues_per_repo: int = Field(
        default=5, ge=0, description="Max issues per repository"
    )
    weekly_token_budget: int = Field(
        default=5_000_000, ge=0, description="Weekly token budget"
    )


class PrioritySettings(BaseModel):
    """Priority scoring weights."""

    health_weight: float = Field(
        default=1.0, ge=0.0, description="Weight for health score"
    )
    impact_weight: float = Field(
        default=2.0, ge=0.0, description="Weight for impact score"
    )
    solvability_weight: float = Field(
        default=1.5, ge=0.0, description="Weight for solvability score"
    )
    urgency_weight: float = Field(
        default=0.5, ge=0.0, description="Weight for urgency score"
    )

    @field_validator(
        "health_weight", "impact_weight", "solvability_weight", "urgency_weight"
    )
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Ensure weights are non-negative."""
        if v < 0:
            raise ValueError("Weights must be non-negative")
        return v


class IssueCategorySettings(BaseModel):
    """Issue category settings."""

    multiplier: float = Field(
        default=1.0, ge=0.0, description="Priority multiplier for this category"
    )
    max_complexity: int = Field(
        default=10, ge=1, le=10, description="Max complexity to process"
    )
    auto_merge_allowed: bool = Field(
        default=True, description="Whether auto-merge is allowed"
    )


class Settings(BaseModel):
    """Global configuration settings."""

    filters: FilterSettings = Field(default_factory=FilterSettings)
    languages: dict[Language, LanguageSettings] = Field(default_factory=dict)
    budget: BudgetSettings = Field(default_factory=BudgetSettings)
    priority: PrioritySettings = Field(default_factory=PrioritySettings)
    issue_categories: dict[str, IssueCategorySettings] = Field(default_factory=dict)

    # LLM settings
    llm_provider: str = Field(
        default="anthropic", description="LLM provider: anthropic or openai"
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514", description="LLM model to use"
    )
    llm_temperature: float = Field(
        default=0.0, ge=0.0, le=2.0, description="LLM temperature"
    )
    llm_max_tokens: int = Field(
        default=8192, ge=1, description="Max tokens per LLM response"
    )

    # GitHub settings
    github_token: str | None = Field(default=None, description="GitHub API token")
    github_base_url: str | None = Field(
        default=None, description="GitHub Enterprise base URL"
    )

    # Data sources
    libraries_io_api_key: str | None = Field(
        default=None, description="libraries.io API key"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_file: str | None = Field(default=None, description="Log file path")

    model_config = {
        "extra": "ignore",  # Ignore extra fields from YAML
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
