"""Database management commands."""

import typer
from rich import print as rprint

from globallm.storage.init_db import get_status, init_database
from globallm.storage.db import Database

app = typer.Typer(help="Database management commands")


@app.command()
def init(
    drop_existing: bool = typer.Option(
        False, "--drop", help="Drop existing tables first"
    ),
) -> None:
    """Initialize the database schema."""
    if drop_existing:
        rprint("[yellow]WARNING: This will delete all existing data![/yellow]")
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            rprint("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    rprint("[cyan]Initializing database...[/cyan]")
    try:
        init_database(drop_existing=drop_existing)
        rprint("[green]Database initialized successfully.[/green]")
    except Exception as e:
        rprint(f"[red]Failed to initialize database: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show database status."""
    try:
        status_info = get_status()

        rprint("\n[bold]Database Status[/bold]")

        # Schema version
        version = status_info.get("schema_version")
        if version:
            rprint(f"  Schema version: [green]{version}[/green]")
        else:
            rprint("  Schema version: [red]Not initialized[/red]")

        # Connection pool
        pool_info = status_info.get("pool", {})
        if pool_info.get("active"):
            rprint("  Connection pool: [green]Active[/green]")
            rprint(f"    Min size: {pool_info.get('min_size', 'N/A')}")
            rprint(f"    Max size: {pool_info.get('max_size', 'N/A')}")
            stats = pool_info.get("stats", {})
            rprint(f"    Pool stats: {stats}")
        else:
            rprint("  Connection pool: [dim]Not connected[/dim]")

        # Data counts
        rprint(f"  Issues: {status_info.get('issues_count', 0)}")
        rprint(f"  Repositories: {status_info.get('repositories_count', 0)}")

        # Error if any
        if "error" in status_info:
            rprint(f"\n[red]Error: {status_info['error']}[/red]")

    except Exception as e:
        rprint(f"[red]Failed to get status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def close() -> None:
    """Close the database connection pool."""
    rprint("[cyan]Closing database connection pool...[/cyan]")
    try:
        Database.close()
        rprint("[green]Connection pool closed.[/green]")
    except Exception as e:
        rprint(f"[red]Failed to close connection pool: {e}[/red]")
        raise typer.Exit(1)
