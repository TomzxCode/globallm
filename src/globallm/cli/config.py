"""Config subcommands."""

import typer
from rich import print as rprint

app = typer.Typer(help="Configuration management")


@app.command()
def show(
    key: str = typer.Option(None, help="Show specific config key"),
) -> None:
    """Show current configuration."""
    from globallm.config.loader import load_config, get_config_path  # noqa: PLC0415

    config = load_config()

    if key:
        # Navigate nested keys with dot notation
        keys = key.split(".")
        value = config
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                rprint(f"[red]Key not found: {key}[/red]")
                raise typer.Exit(1)
        rprint(f"{key}: {value}")
    else:
        rprint("[bold]Configuration file:[/bold]")
        rprint(f"  {get_config_path()}")

        rprint("\n[bold]Current settings:[/bold]")
        rprint(f"  filters.min_stars = {config.filters.min_stars}")
        rprint(f"  filters.min_dependents = {config.filters.min_dependents}")
        rprint(f"  budget.weekly_token_budget = {config.budget.weekly_token_budget}")
        rprint(f"  priority.impact_weight = {config.priority.impact_weight}")


@app.command()
def set(
    key: str = typer.Argument(..., help="Config key (e.g., filters.min_stars)"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Set a configuration value."""
    from globallm.config.loader import load_config, save_config  # noqa: PLC0415

    config = load_config()
    keys = key.split(".")

    # Parse value based on type
    try:
        # Try int first
        parsed_value = int(value)
    except ValueError:
        try:
            # Try float
            parsed_value = float(value)
        except ValueError:
            # Try bool
            if value.lower() in ("true", "yes", "1"):
                parsed_value = True
            elif value.lower() in ("false", "no", "0"):
                parsed_value = False
            else:
                parsed_value = value

    # Set the value
    obj = config
    for k in keys[:-1]:
        if hasattr(obj, k):
            obj = getattr(obj, k)
        elif isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            rprint(f"[red]Key not found: {key}[/red]")
            raise typer.Exit(1)

    final_key = keys[-1]
    if hasattr(obj, final_key):
        setattr(obj, final_key, parsed_value)
    elif isinstance(obj, dict):
        obj[final_key] = parsed_value
    else:
        rprint(f"[red]Key not found: {key}[/red]")
        raise typer.Exit(1)

    save_config(config)
    rprint(f"[green]Set {key} = {parsed_value}[/green]")


@app.command()
def path() -> None:
    """Show the configuration file path."""
    from globallm.config.loader import get_config_path  # noqa: PLC0415

    rprint(f"{get_config_path()}")
