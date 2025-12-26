"""Discover command."""

import time
from datetime import datetime
from typing import TYPE_CHECKING, Callable

import typer
from rich import print as rprint

from globallm.cli.common import _display_results

if TYPE_CHECKING:
    from globallm.scanner import RepoMetrics
    from globallm.storage.repository_store import RepositoryStore

app = typer.Typer(help="Discover repositories by domain and language")


@app.command()
def discover(
    domain: str = typer.Option("overall", help="Domain to search"),
    language: str = typer.Option(None, help="Filter by programming language"),
    min_stars: int = typer.Option(None, help="Minimum stars"),
    min_dependents: int = typer.Option(None, help="Minimum dependents"),
    max_results: int = typer.Option(20, help="Max results to return"),
    use_cache: bool = typer.Option(True, help="Use cache"),
    library_only: bool = typer.Option(True, help="Only include libraries (filter out apps, docs, etc.)"),
) -> None:
    """Discover repositories by domain and language.

    Results are automatically saved to the repository store for later analysis.
    """
    from globallm.scanner import GitHubScanner, Domain
    from globallm.config.loader import load_config
    from globallm.storage.repository_store import RepositoryStore
    import os

    config = load_config()
    token = os.getenv("GITHUB_TOKEN")
    store = RepositoryStore()

    # Apply config filters if CLI args not specified
    if min_stars is None:
        min_stars = config.filters.min_stars
    if min_dependents is None:
        min_dependents = config.filters.min_dependents

    rprint("[bold cyan]Discovering repositories...[/bold cyan]")
    rprint(f"  Domain: {domain}")
    rprint(f"  Language: {language or 'All'}")
    rprint(f"  Min stars: {min_stars:,}")
    rprint(f"  Min dependents: {min_dependents:,}")
    rprint(f"  Library only: {library_only}")

    scanner = GitHubScanner(token, use_cache=use_cache)

    try:
        domain_enum = Domain(domain)
    except ValueError:
        rprint(f"[red]Invalid domain: {domain}[/red]")
        available = [d.value for d in Domain]
        rprint(f"Available domains: {', '.join(available)}")
        raise typer.Exit(1)

    start_time = time.time()
    results = scanner.search_by_domain(
        domain_enum,
        language=language,
        max_results=max_results,
    )

    # Apply library filtering if requested
    if library_only:
        results = scanner.filter_libraries(results)

    duration = time.time() - start_time

    rprint(f"\n[green]Found {len(results)} repositories in {duration:.1f}s[/green]")
    _display_results(results)

    # Auto-save to repository store
    _save_to_store(store, results, rprint)


def _save_to_store(store: RepositoryStore, results: list[RepoMetrics], rprint: Callable) -> None:
    """Save discovered repositories to store, merging with existing.

    Existing repos that have been analyzed (worth_working_on is set) are preserved.
    """
    existing_repos = store.load_repositories()

    # Convert RepoMetrics to dict and merge with existing data
    to_save = list(existing_repos)  # Start with existing
    new_count = 0

    for repo in results:
        repo_dict = repo.to_dict()
        name = repo_dict["name"]

        # Check if already exists
        existing = next((r for r in to_save if r.get("name") == name), None)

        if existing:
            # Preserve analysis fields if they exist
            if existing.get("worth_working_on") is not None:
                # Keep analyzed repo as-is
                continue
            else:
                # Update unanalyzed repo with new data
                existing.update(repo_dict)
        else:
            # Add new repo
            repo_dict["worth_working_on"] = None  # Not yet analyzed
            to_save.append(repo_dict)
            new_count += 1

    store.save_repositories(to_save, discovered_at=datetime.now())

    rprint(f"[dim]→ Saved {len(to_save)} repositories to store ({new_count} new)[/dim]")
