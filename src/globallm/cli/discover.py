"""Discover command."""

import time

import typer
from rich import print as rprint

from globallm.cli.common import _display_results
from globallm.config.loader import load_config

app = typer.Typer(help="Discover repositories by domain and language")


@app.command()
def discover(
    domain: str = typer.Option("overall", help="Domain to search"),
    language: str = typer.Option(None, help="Filter by programming language"),
    min_stars: int = typer.Option(None, help="Minimum stars"),
    min_dependents: int = typer.Option(None, help="Minimum dependents"),
    max_results: int = typer.Option(20, help="Max results to return"),
    use_cache: bool = typer.Option(True, help="Use cache"),
) -> None:
    """Discover repositories by domain and language."""
    from globallm.scanner import GitHubScanner, Domain
    import os

    config = load_config()
    token = os.getenv("GITHUB_TOKEN")

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
    duration = time.time() - start_time

    rprint(f"\n[green]Found {len(results)} repositories in {duration:.1f}s[/green]")
    _display_results(results)
