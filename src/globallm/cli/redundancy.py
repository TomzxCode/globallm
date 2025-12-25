"""Redundancy command."""

import typer
from rich import print as rprint

app = typer.Typer()


@app.command()
def redundancy(
    repos: list[str] = typer.Argument(..., help="Repositories to compare (owner/repo)"),
    threshold: float = typer.Option(0.75, help="Similarity threshold (0-1)"),
) -> None:
    """Detect redundancy between repositories."""
    from globallm.scanner import GitHubScanner
    from globallm.analysis.redundancy import RedundancyDetector
    from globallm.models.repository import Language
    import os

    token = os.getenv("GITHUB_TOKEN")
    scanner = GitHubScanner(token)
    detector = RedundancyDetector()

    rprint("[bold cyan]Analyzing repository redundancy...[/bold cyan]")

    # Fetch repo data and READMEs
    repo_data = []
    for repo_name in repos:
        try:
            metrics = scanner.analyze_repo(repo_name)

            # Try to get README
            readme = ""
            try:
                repo = scanner.github.get_repo(repo_name)
                readme_content = repo.get_readme()
                readme = readme_content.decoded_content.decode()
            except Exception:
                pass

            # Detect language
            language = None
            if metrics.language:
                language = Language.from_string(metrics.language)

            repo_data.append(
                {
                    "name": repo_name,
                    "stars": metrics.stars,
                    "readme": readme,
                    "language": language,
                    "api_signature": None,  # Would need file analysis
                }
            )
        except Exception as e:
            rprint(f"[yellow]Warning: Could not analyze {repo_name}: {e}[/yellow]")

    # Compare all pairs
    rprint("\n[bold]Redundancy Analysis:[/bold]\n")
    found_redundancy = False

    for i in range(len(repo_data)):
        for j in range(i + 1, len(repo_data)):
            repo_a = repo_data[i]
            repo_b = repo_data[j]

            readme_sim = detector.compute_readme_similarity(
                repo_a["readme"], repo_b["readme"]
            )

            if readme_sim > threshold:
                found_redundancy = True
                keep = (
                    repo_a["name"]
                    if repo_a["stars"] >= repo_b["stars"]
                    else repo_b["name"]
                )
                archive = (
                    repo_b["name"]
                    if repo_a["stars"] >= repo_b["stars"]
                    else repo_a["name"]
                )

                rprint("[red]Redundancy detected:[/red]")
                rprint(f"  {repo_a['name']} <-> {repo_b['name']}")
                rprint(f"  README similarity: {readme_sim:.1%}")
                rprint(
                    f"  Recommendation: Keep [green]{keep}[/green], archive {archive}"
                )
                rprint()

    if not found_redundancy:
        rprint("[green]No significant redundancy found[/green]")
        for repo in repo_data:
            rprint(f"  - {repo['name']}: {repo['stars']:,} stars")
