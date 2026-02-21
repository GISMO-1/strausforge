"""Command-line interface for strausforge."""

from __future__ import annotations

import json
from fractions import Fraction

import typer
from rich.console import Console

from .erdos_straus import check_identity, find_solution

app = typer.Typer(help="Baseline search/verification tool for the Erdős–Straus conjecture.")
console = Console()


@app.command()
def check(
    n: int = typer.Option(..., "--n", help="Positive integer n in 4/n."),
    x: int = typer.Option(..., "--x", help="Denominator x in 1/x."),
    y: int = typer.Option(..., "--y", help="Denominator y in 1/y."),
    z: int = typer.Option(..., "--z", help="Denominator z in 1/z."),
) -> None:
    """Check whether a specific identity instance is exact.

    Examples:
        strausforge check --n 5 --x 2 --y 4 --z 20
        strausforge check --n 7 --x 2 --y 6 --z 42
    """
    ok = check_identity(n=n, x=x, y=y, z=z)
    if ok:
        console.print("[bold green]PASS[/bold green]")
        return

    difference = Fraction(4, n) - (Fraction(1, x) + Fraction(1, y) + Fraction(1, z))
    console.print("[bold red]FAIL[/bold red]")
    console.print(f"Difference: {difference}")
    raise typer.Exit(code=1)


@app.command()
def search(
    n: int | None = typer.Option(None, "--n", help="Single n to search."),
    start: int | None = typer.Option(None, "--start", help="Range start (inclusive)."),
    end: int | None = typer.Option(None, "--end", help="Range end (inclusive)."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON lines."),
) -> None:
    """Search for decompositions over one n or a range.

    Examples:
        strausforge search --n 17
        strausforge search --start 2 --end 25
        strausforge search --start 2 --end 25 --json
    """
    if n is not None and (start is not None or end is not None):
        raise typer.BadParameter("Use --n for a single value OR --start/--end for a range.")

    if n is not None:
        _print_single(n=n, json_output=json_output)
        return

    if start is None or end is None:
        raise typer.BadParameter("Provide either --n N or both --start A and --end B.")
    if start > end:
        raise typer.BadParameter("Expected start <= end.")

    for value in range(start, end + 1):
        _print_single(n=value, json_output=json_output)


def _print_single(n: int, json_output: bool) -> None:
    solution = find_solution(n)
    found = solution is not None

    if json_output:
        payload: dict[str, int | bool | None] = {"n": n, "found": found}
        if solution is not None:
            payload["x"], payload["y"], payload["z"] = solution
        console.print(json.dumps(payload, sort_keys=True))
        return

    if solution is None:
        console.print(f"n={n}: no solution found")
        return

    x, y, z = solution
    console.print(f"n={n}: found x={x}, y={y}, z={z}")


if __name__ == "__main__":
    app()
