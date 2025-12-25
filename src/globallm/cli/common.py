"""Common utilities for CLI commands."""

from rich import print as rprint


def _display_results(results: list) -> None:
    """Display repository results."""

    rprint("\n[bold]Top Results:[/bold]")
    for i, repo in enumerate(results[:10], 1):
        rprint(f"{i}. [bold]{repo.name}[/bold]")
        rprint(
            f"   Stars: {repo.stars:,} | Forks: {repo.forks:,} | Score: {repo.score:.1f}"
        )
        rprint(f"   Language: {repo.language or 'N/A'}")
        rprint()
