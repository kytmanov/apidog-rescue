"""CLI entry point for apidog-rescue."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .finder import find_apidog_dir
from .extractor import extract_all
from .exporters import export_postman, export_bruno


console = Console()


def _print_summary(collections: dict[str, list[dict]]) -> None:
    table = Table(title="Discovered collections", show_lines=True)
    table.add_column("Collection", style="cyan")
    table.add_column("Endpoints", justify="right", style="green")
    for name, items in collections.items():
        table.add_row(name, str(len(items)))
    console.print(table)


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

    if not collections:
        console.print("[yellow]No API data found. The directory may be empty or unsupported.[/yellow]")
        return 0

    _print_summary(collections)

    if args.list:
        return 0

    # 3. Export
    output_dir = Path(args.output).resolve()
    postman_dir = output_dir / "postman"
    bruno_dir = output_dir / "bruno"

    exported: list[str] = []

    for coll_name, items in collections.items():
        if args.format in ("all", "postman"):
            with console.status(f"Exporting [cyan]{coll_name}[/cyan] → Postman…"):
                out = export_postman(coll_name, items, postman_dir)
            console.print(f"  [green]✓[/green] Postman: {out.relative_to(output_dir)}")
            exported.append(str(out))

        if args.format in ("all", "bruno"):
            with console.status(f"Exporting [cyan]{coll_name}[/cyan] → Bruno…"):
                out = export_bruno(coll_name, items, bruno_dir)
            console.print(f"  [green]✓[/green] Bruno:   {out.relative_to(output_dir)}")
            exported.append(str(out))

    console.rule()
    total = sum(len(v) for v in collections.values())
    console.print(
        f"[bold green]Done.[/bold green] "
        f"Recovered [cyan]{total}[/cyan] endpoints across "
        f"[cyan]{len(collections)}[/cyan] collection(s).\n"
        f"Output: [underline]{output_dir}[/underline]"
    )

    console.print("\n[bold]How to import:[/bold]")
    if args.format in ("all", "postman"):
        console.print("  Postman : Import → Upload files → select any *.postman_collection.json")
        console.print("  Bruno   : Open collection → select the bruno/ sub-folder")
    if args.format == "bruno":
        console.print("  Bruno   : Open collection → select the bruno/ sub-folder")

    return 0


if __name__ == "__main__":
    sys.exit(main())
