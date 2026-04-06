"""CLI entry point for apidog-rescue."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .finder import find_apidog_dir
from .extractor import extract_all, extract_environments
from .exporters import export_postman, export_bruno, export_environment_postman, export_environment_bruno


console = Console()


def _print_summary(collections: dict[str, list[dict]], environments: list[dict]) -> None:
    table = Table(title="Discovered collections", show_lines=True)
    table.add_column("Collection", style="cyan")
    table.add_column("Endpoints", justify="right", style="green")
    for name, items in collections.items():
        table.add_row(name, str(len(items)))
    console.print(table)

    if environments:
        env_table = Table(title="Discovered environments", show_lines=True)
        env_table.add_column("ID", style="cyan")
        env_table.add_column("Project ID", style="cyan")
        env_table.add_column("Variables", justify="right", style="green")
        for env in environments:
            env_table.add_row(
                str(env.get("id", "?")),
                str(env.get("projectId", "?")),
                str(len(env.get("variables") or [])),
            )
        console.print(env_table)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apidog-rescue",
        description="Recover lost API collections from ApiDog's local data.",
    )
    parser.add_argument(
        "--path",
        metavar="DIR",
        help="Path to ApiDog data directory (auto-detected if omitted).",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default="recovered",
        help="Output directory (default: ./recovered).",
    )
    parser.add_argument(
        "--format",
        choices=["all", "postman", "bruno"],
        default="all",
        help="Export format (default: all).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Only list what was found; do not write files.",
    )
    args = parser.parse_args(argv)

    # 1. Locate ApiDog directory
    console.rule("[bold blue]apidog-rescue[/bold blue]")
    with console.status("Locating ApiDog data directory…"):
        try:
            apidog_dir = find_apidog_dir(args.path)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            return 1

    if apidog_dir is None:
        console.print(
            "[red]Could not find ApiDog data directory.[/red]\n"
            "Try passing it explicitly with --path <DIR>\n\n"
            "Common locations:\n"
            "  macOS:   ~/Library/Application Support/apidog\n"
            "  Windows: %APPDATA%\\apidog\n"
            "  Linux:   ~/.config/apidog"
        )
        return 1

    console.print(f"[green]Found:[/green] {apidog_dir}")

    # 2. Extract
    with console.status("Extracting data from all sources…"):
        collections = extract_all(apidog_dir)
        environments = extract_environments(apidog_dir)

    if not collections and not environments:
        console.print("[yellow]No API data found. The directory may be empty or unsupported.[/yellow]")
        return 0

    _print_summary(collections, environments)

    if args.list:
        return 0

    # 3. Export
    output_dir = Path(args.output).resolve()
    postman_dir = output_dir / "postman"
    bruno_dir = output_dir / "bruno"

    # Collections
    for coll_name, items in collections.items():
        if args.format in ("all", "postman"):
            with console.status(f"Exporting [cyan]{coll_name}[/cyan] → Postman…"):
                out = export_postman(coll_name, items, postman_dir)
            console.print(f"  [green]✓[/green] Postman: {out.relative_to(output_dir)}")

        if args.format in ("all", "bruno"):
            with console.status(f"Exporting [cyan]{coll_name}[/cyan] → Bruno…"):
                bruno_coll_dir = export_bruno(coll_name, items, bruno_dir)
            console.print(f"  [green]✓[/green] Bruno:   {bruno_coll_dir.relative_to(output_dir)}")

            # Attach environments to every Bruno collection
            for env in environments:
                export_environment_bruno(env, bruno_coll_dir)

    # Environments (Postman — standalone files)
    if environments and args.format in ("all", "postman"):
        for env in environments:
            with console.status(f"Exporting environment {env.get('id')} → Postman…"):
                out = export_environment_postman(env, postman_dir)
            console.print(f"  [green]✓[/green] Postman env: {out.relative_to(output_dir)}")

    console.rule()
    total = sum(len(v) for v in collections.values())
    console.print(
        f"[bold green]Done.[/bold green] "
        f"Recovered [cyan]{total}[/cyan] endpoints across "
        f"[cyan]{len(collections)}[/cyan] collection(s) "
        f"and [cyan]{len(environments)}[/cyan] environment(s).\n"
        f"Output: [underline]{output_dir}[/underline]"
    )

    console.print("\n[bold]How to import:[/bold]")
    if args.format in ("all", "postman"):
        console.print("  Postman : Import → Upload files → select *.postman_collection.json and *.postman_environment.json")
    if args.format in ("all", "bruno"):
        console.print("  Bruno   : Open collection → select the bruno/<name>/ folder (environments are included)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
