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

### Discover Repositories

```bash
# Search by domain
globallm discover --domain ai_ml --language python --max-results 10

# Available domains: ai_ml, web_dev, data_science, cloud_devops, mobile, security, games
```

### Analyze a Repository

```bash
globallm analyze octocat/Hello-World
```

### System Status

```bash
globallm status --dashboard
```

### Configuration Management

```bash
globallm config set filters.min_stars 5000
globallm config show filters
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
