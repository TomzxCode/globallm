# GlobaLLM

> AI-powered open source contribution orchestration at scale

GlobaLLM is a system for identifying the most impactful open source libraries and contributing to their success using autonomous AI agents. It solves the resource allocation problem: with unlimited access to hyper-competent LLMs and finite compute, how do you maximize positive impact on the software ecosystem?

## Vision

The core insight: when AI agents have access to all GitHub repositories and can effectively address all existing open issues, the bottleneck becomes **prioritization**, not capability.

GlobaLLM provides:
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

Thinking at the highest level, GlobaLLM aims to tackle problems that are fundamentally social:

- Reduce the wealth gap
- Reduce homelessness
- Reduce pain caused by diseases
- Find better societal solutions

Better software is a means to these ends.

## Installation

### Prerequisites

- **Python 3.14+**
- **Docker** (for PostgreSQL database)
- **GitHub token** (for higher API rate limits)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourorg/globallm.git
cd globallm

# Install dependencies
uv sync

# Start PostgreSQL
docker-compose up -d

# Initialize the database
uv run globallm database init
```

### Database Setup

GlobaLLM uses PostgreSQL for data persistence. The `docker-compose.yml` file includes a PostgreSQL service:

```bash
# Start PostgreSQL
docker-compose up -d

# Stop PostgreSQL
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Custom Database Connection

By default, GlobaLLM connects to `postgresql://globallm:globallm@localhost:5432/globallm`. To use a different database:

```bash
export GLOBALLM_DATABASE_URL="postgresql://user:pass@host:5432/dbname"
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

## Database Management

Manage the GlobaLLM database:

```bash
# Initialize database schema
globallm database init

# Show database status
globallm database status

# Run pending migrations (upgrades schema without data loss)
globallm database migrate

# Close connection pool (cleanup)
globallm database close
```

**Migrations:** When you upgrade to a new version of GlobaLLM, run `globallm database migrate` to apply any schema changes. Migrations are non-destructive and preserve your existing data.

## Usage

### Command Workflow

```mermaid
flowchart TD
    Start([Start]) --> Config[Configuration]
    Start --> Budget[Budget Check]

    subgraph Setup ["Initial Setup"]
        Config --> ConfigShow["globallm config show"]
        Config --> ConfigSet["globallm config set <key> <value>"]
        Budget --> BudgetShow["globallm budget show"]
    end

    ConfigSet --> Discover[Discovery]
    BudgetShow --> Discover

    subgraph Discovery ["Find Repositories"]
        Discover --> DiscoverCmd["globallm discover<br/>--domain <domain><br/>--language <lang>"]
        DiscoverCmd --> Store["Repos saved to store"]
        Store --> Analyze[Analyze]
    end

    subgraph Analysis ["Analyze Repositories"]
        Analyze --> AnalyzeCmd["globallm analyze <repo>"]
        AnalyzeCmd --> Calculate["Auto-calculate<br/>worth_working_on"]
        Calculate --> StoreUpdate["Update store"]
        StoreUpdate --> ShowRepos{Show repos?}
        ShowRepos -->|Yes| ReposCmd["globallm repos list<br/>--filter approved"]
        ShowRepos -->|No| Redundancy
        ReposCmd --> Redundancy[Redundancy Check]
    end

    subgraph Redundancy ["Detect Duplicates"]
        Redundancy --> RedundancyCmd["globallm redundancy <repo1> <repo2><br/>--threshold <0-1>"]
        RedundancyCmd --> Issues[Issue Discovery]
    end

    subgraph Issues ["Fetch Issues"]
        Issues --> IssuesCmd["globallm issues <repo><br/>--state <open|closed|all><br/>--sort <priority|created>"]
        IssuesCmd --> Prioritize[Prioritization]
    end

    subgraph Prioritize ["Prioritize Issues"]
        Prioritize --> PrioritizeCmd["globallm prioritize<br/>--reads approved repos<br/>from store"]
        PrioritizeCmd --> Fix{Fix Issue?}
    end

    subgraph Fix ["Generate Fix"]
        Fix -->|Yes| FixCmd["globallm fix <issue_url><br/>--dry-run<br/>--auto-merge"]
        Fix -->|No| Status
        FixCmd --> Status[Check Status]
    end

    subgraph Status ["Monitor Progress"]
        Status --> StatusCmd["globallm status<br/>--dashboard<br/>--export json"]
        StatusCmd --> End([End])
    end

    classDef setup fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef primary fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef action fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef monitor fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px

    class ConfigShow,ConfigSet,BudgetShow setup
    class DiscoverCmd,AnalyzeCmd,ReposCmd,RedundancyCmd primary
    class IssuesCmd,PrioritizeCmd,FixCmd action
    class StatusCmd monitor
```

> **Note**: Discovered repositories and prioritized issues are stored in a PostgreSQL database. The `analyze` command calculates `worth_working_on` based on health and impact scores (health > 0.5 AND impact > 0.5). The `prioritize` command reads only approved repos from the database.

### Configuration Management

Manage GlobaLLM settings including filters, API tokens, and thresholds. Use this to customize how the tool discovers and evaluates repositories.

```bash
# Show all configuration
globallm config show

# Set a configuration value
globallm config set filters.min_stars 5000
globallm config set github.token your_token_here

# Show configuration file path
globallm config path
```

### Budget Management

Track and control resource usage including tokens, time, and per-repository limits. Essential for managing costs when running at scale.

```bash
# Show current budget status
globallm budget show

# Reset budget tracking
globallm budget reset
```

### Discover Repositories

Search GitHub for high-impact repositories by domain and language. Uses curated queries to find libraries where contributions will have the most downstream impact. Results are automatically saved to the repository store.

```bash
# Discover Python AI/ML libraries (auto-saves to store)
globallm discover --domain ai_ml --language python --max-results 20

# Discover with minimum star and dependent filters
globallm discover --domain web_dev --language javascript --min-stars 1000 --min-dependents 50

# Discover only libraries (exclude apps, docs, etc.)
globallm discover --domain data_science --language python --library-only

# Available domains: ai_ml, web_dev, data_science, cloud_devops, mobile, security, games, overall
# Available languages: python, javascript, typescript, rust, go, java, and more
```

### Analyze a Repository

Deep-dive into a specific repository's health and impact metrics. Automatically calculates whether the repository is worth working on and updates the repository store.

```bash
# Analyze a repository (auto-calculates worth_working_on)
globallm analyze django/django

# The analysis will show:
# - Health Score (0-100%)
# - Impact Score (0-100%)
# - Whether it's worth working on (✓ or ✗)
# - Analysis reason
```

### Manage Stored Repositories

List and manage repositories in the store. Filter by analysis status.

```bash
# List all stored repositories
globallm repos list

# Show only approved repositories (worth_working_on=true)
globallm repos list --filter approved

# Show rejected repositories
globallm repos list --filter rejected

# Show unanalyzed repositories
globallm repos list --filter unanalyzed

# Show detailed information about a specific repository
globallm repos show django/django

# Remove a repository from the store
globallm repos remove some/repo
```

### Detect Redundancy

Identify duplicate or overlapping projects by comparing README similarity. Use this to consolidate efforts and deprecate redundant libraries.

```bash
# Compare two repositories for redundancy
globallm redundancy requests/urllib3 python/cpython

# Set custom similarity threshold (0-1)
globallm redundancy --threshold 0.8 repo1/project repo2/project

# Compare multiple repositories
globallm redundancy org/repo1 org/repo2 org/repo3
```

### System Status

View overall system health, budget utilization, and recent activity. Use the dashboard mode for a live overview of operations.

```bash
# Show system status
globallm status

# Show dashboard view
globallm status --dashboard

# Export status to JSON
globallm status --export json > status.json
```

### Fetch Issues

List and filter issues from a repository. Issues are automatically categorized (bug, feature, documentation, etc.) and can be sorted by priority.

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

Rank issues across all repositories using a multi-factor scoring algorithm that considers health, impact, solvability, urgency, and redundancy. This identifies the highest-value work.

> Reads from the repository store (approved repos only). Run `discover` and `analyze` first to populate the store.

```bash
# Show top 20 priority issues across approved repositories
globallm prioritize

# Filter by language
globallm prioritize --language python

# Show top 50 issues with minimum priority score
globallm prioritize --top 50 --min-priority 0.5

# Export to file
globallm prioritize --export json > priorities.json
```

### Fix Issues

Automatically analyze an issue, generate a solution with tests, and create a pull request. Safe changes can auto-merge based on complexity scoring.

```bash
# Work on the highest-priority available issue (no URL required)
globallm fix

# Work on a specific issue URL
globallm fix --issue-url https://github.com/owner/repo/issues/123

# Dry run (don't actually create PR)
globallm fix --dry-run

# Target a specific branch
globallm fix --branch develop

# Disable auto-merge for safe changes
globallm fix --no-auto-merge
```

When running without an issue URL, `globallm fix` automatically claims the highest-priority available issue from the database. Multiple agents can run in parallel without conflicts - each agent gets assigned a unique issue.

### Issue Assignment

Manage distributed issue assignments when running multiple agents in parallel. Issues are automatically assigned to agents with heartbeat tracking for crash recovery.

```bash
# Show current issue assignments
globallm assign status

# Show assignments for a specific agent
globallm assign status --agent-id hostname-1234-abc12345

# Show only stale assignments (no heartbeat for 30+ minutes)
globallm assign status --stale

# Release all assignments for a specific agent
globallm assign release hostname-1234-abc12345

# Clean up stale assignments (timeout in minutes)
globallm assign cleanup --timeout-minutes 30
```

**Assignment States:**
- `available` - Issue is available to be claimed
- `assigned` - Issue is currently assigned to an agent
- `completed` - Issue was successfully completed (removed from pool)
- `failed` - Issue processing failed (released back to available)

**Heartbeat Timeout:** Assignments are automatically released if no heartbeat is received for 30 minutes (configurable via `GLOBALLM_HEARTBEAT_TIMEOUT`).

### Analyze User

Evaluate all repositories owned by a user or organization. Provides keep/archive recommendations to help maintain focus on high-impact projects.

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
├── storage/         # PostgreSQL database persistence (repositories, issues)
├── models/          # Data models (Repository, Issue, Solution)
├── agent/           # Agent identification and heartbeat management
├── cli/             # Command-line interface commands
└── config/          # Configuration management with Pydantic
```

### Database Schema

GlobaLLM uses PostgreSQL with JSONB columns for flexible schema evolution:

| Table       | Columns                          | Description                       |
|-------------|----------------------------------|-----------------------------------|
| `issues`    | repository, number, data (JSONB), assigned_to, assigned_at, last_heartbeat_at, assignment_status | Prioritized issues with assignment tracking  |
| `repositories` | name, data (JSONB), worth_working_on | Discovered repos with analysis  |
| `schema_migrations` | version, applied_at        | Database schema version tracking  |

Indexes on `repository`, `name`, `assignment_status`, `assigned_to`, and JSONB data fields enable efficient querying across 20-100 concurrent processes.

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
