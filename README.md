# GlobalLM

> AI-powered open source contribution orchestration at scale

GlobalLM is a system for identifying the most impactful open source libraries and contributing to their success using autonomous AI agents. It solves the resource allocation problem: with unlimited access to hyper-competent LLMs and finite compute, how do you maximize positive impact on the software ecosystem?

## Vision

The core insight: when AI agents have access to all GitHub repositories and can effectively address all existing open issues, the bottleneck becomes **prioritization**, not capability.

GlobalLM provides:
- **Impact analysis** to identify repositories where contributions matter most
- **Budget controls** (time, tokens, cost) to allocate resources efficiently
- **Monitoring dashboards** to observe agent progress with metrics and KPIs
- **Automated workflows** that bypass human review bottlenecks for trusted changes

### Rules for Agents

- Identify which projects are worth maintaining vs. archiving/deprecating
- Eliminate redundant or unused projects (reconcile features, deprecate duplicates)
- Prioritize high-impact changes over lint/style fixes
- Focus on a targeted set of languages rather than reinventing the wheel
- Replace closed-source standards with open-source equivalents
- Use dependency graphs and stars to determine importance

### Ultimate Goals

Thinking at the highest level, GlobalLM aims to tackle problems that are fundamentally social:

- Reduce the wealth gap
- Reduce homelessness
- Reduce pain caused by diseases
- Find better societal solutions

Better software is a means to these ends.

## Installation

```bash
# Requires Python 3.14+
uv add globallm
```

Or install from source:

```bash
git clone https://github.com/yourorg/globallm.git
cd globallm
uv sync
```

## Configuration

Set your GitHub token for higher rate limits:

```bash
export GITHUB_TOKEN="your_token_here"
```

Create a `.env` file or use the CLI:

```bash
globallm config set github.token your_token_here
```

## Usage

### Configuration Management

```bash
# Show all configuration
globallm config show

# Show specific config key
globallm config show --key filters.min_stars

# Set a configuration value
globallm config set filters.min_stars 5000
globallm config set github.token your_token_here

# Show configuration file path
globallm config path
```

### Budget Management

```bash
# Show current budget status
globallm budget show

# Reset budget tracking
globallm budget reset
```

### Discover Repositories

```bash
# Discover Python AI/ML libraries
globallm discover --domain ai_ml --language python --max-results 20

# Discover with minimum star and dependent filters
globallm discover --domain web_dev --language javascript --min-stars 1000 --min-dependents 50

# Discover only libraries (exclude apps, docs, etc.)
globallm discover --domain data_science --language python --library-only

# Available domains: ai_ml, web_dev, data_science, cloud_devops, mobile, security, games, overall
# Available languages: python, javascript, typescript, rust, go, java, and more
```

### Analyze a Repository

```bash
# Basic repository analysis
globallm analyze octocat/Hello-World

# Include dependent analysis
globallm analyze --include-dependents tensorflow/tensorflow
```

### Detect Redundancy

```bash
# Compare two repositories for redundancy
globallm redundancy requests/urllib3 python/cpython

# Set custom similarity threshold (0-1)
globallm redundancy --threshold 0.8 repo1/project repo2/project

# Compare multiple repositories
globallm redundancy org/repo1 org/repo2 org/repo3
```

### System Status

```bash
# Show system status
globallm status

# Show dashboard view
globallm status --dashboard

# Export status to JSON
globallm status --export json > status.json
```

### Fetch Issues

```bash
# List open issues from a repository
globallm issues octocat/Hello-World

# List closed issues
globallm issues --state closed octocat/Hello-World

# List all issues with limit
globallm issues --state all --limit 100 octocat/Hello-World

# Filter by category and sort
globallm issues --category bug --sort priority octocat/Hello-World

# Sort options: priority, created, updated
```

### Prioritize Issues

```bash
# Show top 20 priority issues across all repositories
globallm prioritize

# Filter by language
globallm prioritize --language python

# Show top 50 issues with minimum priority score
globallm prioritize --top 50 --min-priority 0.5

# Export to file
globallm prioritize --export json > priorities.json
globallm prioritize --export csv > priorities.csv
```

### Fix Issues

```bash
# Analyze an issue and generate a fix (creates PR)
globallm fix https://github.com/owner/repo/issues/123

# Dry run (don't actually create PR)
globallm fix --dry-run https://github.com/owner/repo/issues/123

# Target a specific branch
globallm fix --branch develop https://github.com/owner/repo/issues/123

# Disable auto-merge for safe changes
globallm fix --no-auto-merge https://github.com/owner/repo/issues/123
```

### Analyze User

```bash
# Analyze all repositories owned by a user
globallm analyze-user octocat

# Filter by minimum stars
globallm analyze-user --min-stars 100 octocat

# Include forked repositories
globallm analyze-user --include-forks octocat

# Show keep/archive recommendations
globallm analyze-user --recommend octocat

# Limit number of results
globallm analyze-user --max-results 50 octocat
```

## How It Works

### 1. Discovery
Finds repositories by domain and language using curated search queries. Supports multiple ecosystems (Python, JavaScript, Rust, Go, Java).

### 2. Health Scoring
Evaluates repository maintainability:
- Commit velocity
- Issue resolution rate
- CI/CD status
- Recent activity
- Documentation quality

### 3. Impact Calculation
Uses dependency graph analysis (NetworkX) to compute:
- Downstream impact (number of dependents)
- Centrality metrics
- Usage patterns across package registries

### 4. Filtering
Applies configurable filters to identify high-value targets:
- Minimum stars/forks
- Health thresholds
- Language requirements
- License compatibility

## Architecture

```
src/globallm/
├── scanner.py       # GitHub repository scanner with caching
├── analysis/        # Impact calculation and dependency graph analysis
├── discovery/       # Repository discovery and package registry integration
├── filtering/       # Health scoring and repository filtering
├── models/          # Data models (Repository, Issue, Solution)
└── config/          # Configuration management with Pydantic
```

## Development

```bash
# Run linter
uv run ruff check

# Run tests
uv run pytest

# Format code
uv run ruff format
```

## License

MIT
