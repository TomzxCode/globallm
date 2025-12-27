"""Assignment status and management commands."""

from datetime import datetime

import typer
from psycopg.rows import dict_row
from rich import print as rprint
from rich.table import Table

from globallm.storage.db import get_connection
from globallm.storage.issue_store import IssueStore

app = typer.Typer(name="assign", help="Manage issue assignments")


@app.command()
def status(
    agent_id: str = typer.Option(None, help="Filter by agent ID"),
    stale_only: bool = typer.Option(
        False, "--stale", help="Show only stale assignments"
    ),
) -> None:
    """Show current issue assignments."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            query = """
                SELECT repository, number,
                       data->>'title' as title,
                       assigned_to, assigned_at, last_heartbeat_at,
                       assignment_status,
                       data->>'priority' as priority
                FROM issues
                WHERE assignment_status = 'assigned'
            """
            params = []

            if agent_id:
                query += " AND assigned_to = %s"
                params.append(agent_id)

            if stale_only:
                query += " AND last_heartbeat_at < NOW() - INTERVAL '30 minutes'"

            query += " ORDER BY (data->>'priority')::numeric DESC"

            cur.execute(query, params)
            assignments = cur.fetchall()

    rprint(f"\n[bold cyan]Active Assignments: {len(assignments)}[/bold cyan]\n")

    if assignments:
        table = Table()
        table.add_column("Repo", style="cyan")
        table.add_column("#", style="bold")
        table.add_column("Title", style="white")
        table.add_column("Agent", style="yellow")
        table.add_column("Assigned", style="dim")
        table.add_column("Last Heartbeat", style="dim")
        table.add_column("Priority", style="green")

        for a in assignments:
            # Calculate heartbeat age
            if a["last_heartbeat_at"]:
                age = (
                    datetime.now(a["last_heartbeat_at"].tzinfo) - a["last_heartbeat_at"]
                ).seconds
                heartbeat_age = f"{age // 60}m ago"
            else:
                heartbeat_age = "Never"

            table.add_row(
                a["repository"],
                str(a["number"]),
                (a["title"] or "")[:40],
                a["assigned_to"] or "",
                a["assigned_at"].strftime("%H:%M") if a["assigned_at"] else "",
                heartbeat_age,
                str(a["priority"] or "N/A"),
            )

        rprint(table)


@app.command()
def release(
    agent_id: str = typer.Argument(..., help="Agent ID to release assignments for"),
) -> None:
    """Release all assignments for an agent."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE issues
                SET assignment_status = 'available',
                    assigned_to = NULL,
                    assigned_at = NULL,
                    last_heartbeat_at = NULL,
                    updated_at = NOW()
                WHERE assigned_to = %s
            """,
                (agent_id,),
            )
            conn.commit()
            count = cur.rowcount

    rprint(f"[green]Released {count} assignments for agent {agent_id}[/green]")


@app.command()
def cleanup(
    timeout_minutes: int = typer.Option(30, help="Timeout in minutes"),
) -> None:
    """Release stale assignments."""
    issue_store = IssueStore()
    timeout_seconds = timeout_minutes * 60

    count = issue_store.release_stale_assignments(timeout_seconds)

    if count > 0:
        rprint(f"[green]Released {count} stale assignments[/green]")
    else:
        rprint("[yellow]No stale assignments found[/yellow]")
