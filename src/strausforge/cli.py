"""Command-line interface for strausforge."""

from __future__ import annotations

import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console

from .cert import Certificate, from_jsonl, make_certificate, to_jsonl
from .coverage import coverage_report
from .erdos_straus import check_identity, find_solution, find_solution_fast
from .identities import Identity, eval_identity, identity_from_jsonl, verify_identity
from .loop import run_loop
from .mine import mine_identities

app = typer.Typer(help="Search/verification tool for the Erdős–Straus conjecture.")
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


@app.command()
def certify(
    start: int = typer.Option(..., "--start", help="Range start (inclusive)."),
    end: int = typer.Option(..., "--end", help="Range end (inclusive)."),
    out: Path = typer.Option(..., "--out", help="Output JSONL certificate file."),
) -> None:
    """Generate machine-checkable certificates for a range.

    Examples:
        strausforge certify --start 2 --end 100 --out certs.jsonl
    """
    if start > end:
        raise typer.BadParameter("Expected start <= end.")

    certs: list[Certificate] = []
    for n in range(start, end + 1):
        started = perf_counter()
        solution = find_solution_fast(n)
        elapsed_ms = (perf_counter() - started) * 1000.0

        if solution is None:
            cert = make_certificate(
                n=n,
                x=0,
                y=0,
                z=0,
                method="search_v1",
                elapsed_ms=elapsed_ms,
            )
        else:
            x, y, z = solution
            cert = make_certificate(
                n=n,
                x=x,
                y=y,
                z=z,
                method="search_v1",
                elapsed_ms=elapsed_ms,
            )
        certs.append(cert)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for cert in certs:
            handle.write(to_jsonl(cert) + "\n")

    solved = sum(1 for cert in certs if cert.verified)
    unsolved = len(certs) - solved
    fastest = min(cert.elapsed_ms for cert in certs)
    slowest = max(cert.elapsed_ms for cert in certs)

    console.print(
        f"summary: solved={solved}, unsolved={unsolved}, "
        f"fastest_ms={fastest:.3f}, slowest_ms={slowest:.3f}"
    )


@app.command(name="stats")
def stats_cmd(
    in_file: Path = typer.Option(..., "--in", help="Input JSONL certificate file."),
) -> None:
    """Print coverage and timing statistics from certificate JSONL.

    Examples:
        strausforge stats --in certs.jsonl
    """
    certs = _load_certs(in_file)
    if not certs:
        raise typer.BadParameter("No certificate lines found in input file.")

    for mod_key in ("n_mod_4", "n_mod_12", "n_mod_24"):
        totals: dict[int, int] = defaultdict(int)
        solved: dict[int, int] = defaultdict(int)
        for cert in certs:
            cls = cert.residue[mod_key]
            totals[cls] += 1
            if cert.verified:
                solved[cls] += 1

        console.print(f"coverage {mod_key}:")
        for cls in sorted(totals):
            console.print(f"  class={cls:>2}: solved={solved[cls]}, total={totals[cls]}")

    console.print("top 10 slowest n values:")
    for cert in sorted(certs, key=lambda item: item.elapsed_ms, reverse=True)[:10]:
        console.print(
            f"  n={cert.n}, elapsed_ms={cert.elapsed_ms:.3f}, verified={str(cert.verified).lower()}"
        )


@app.command("mine")
def mine_cmd(
    in_file: Path = typer.Option(..., "--in", help="Input certificate JSONL."),
    out_file: Path = typer.Option(..., "--out", help="Output identities JSONL."),
    max_identities: int = typer.Option(50, "--max-identities", help="Maximum identities."),
) -> None:
    """Mine deterministic residue-class identities from certificates.

    Examples:
        strausforge mine --in certs.jsonl --out data/identities.jsonl
        strausforge mine --in certs.jsonl --out data/identities.jsonl --max-identities 25
    """
    identities = mine_identities(in_file, out_file, max_identities=max_identities)
    symbolic = sum(1 for identity in identities if "symbolic" in identity.notes)
    empirical_only = sum(1 for identity in identities if "empirical-only" in identity.notes)
    console.print(
        f"summary: identities_found={len(identities)}, "
        f"symbolic_verified={symbolic}, empirical_only={empirical_only}"
    )


@app.command("id-check")
def id_check_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    n: int = typer.Option(..., "--n", help="Target n."),
) -> None:
    """Find the first identity that applies to ``n`` and print ``(x, y, z)``.

    Examples:
        strausforge id-check --identity data/identities.jsonl --n 35
    """
    for identity in _load_identities(identity_file):
        triple = eval_identity(identity, n)
        if triple is None:
            continue
        x, y, z = triple
        console.print(f"identity={identity.name}, n={n}, x={x}, y={y}, z={z}")
        return

    console.print(f"no identity applies at n={n}")
    raise typer.Exit(code=1)


@app.command("id-verify")
def id_verify_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    n_min: int = typer.Option(..., "--n-min", help="Minimum n."),
    n_max: int = typer.Option(..., "--n-max", help="Maximum n."),
) -> None:
    """Empirically verify each stored identity over a range.

    Examples:
        strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500
    """
    if n_min > n_max:
        raise typer.BadParameter("Expected --n-min <= --n-max.")

    for identity in _load_identities(identity_file):
        stats = verify_identity(identity, n_min=n_min, n_max=n_max)
        console.print(
            f"identity={identity.name}, tested={stats['tested']}, "
            f"passed={stats['passed']}, failed={stats['failed']}"
        )


def _validate_positive_modulus(value: int) -> int:
    """Validate modulus option values for identity coverage commands."""
    if value <= 0:
        raise typer.BadParameter("Expected --modulus > 0.")
    return value


@app.command("id-targets")
def id_targets_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    modulus: int = typer.Option(
        ...,
        "--modulus",
        help="Coverage modulus to analyze.",
        callback=_validate_positive_modulus,
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON summary."),
) -> None:
    """Report covered and uncovered residue classes for mining targets.

    Examples:
        strausforge id-targets --identity data/identities.jsonl --modulus 24
        strausforge id-targets --identity data/identities.jsonl --modulus 24 --json
    """
    report = coverage_report(_load_identities(identity_file), modulus=modulus)
    if json_output:
        console.print(json.dumps(report, sort_keys=True))
        return

    console.print(
        f"coverage modulus={report['modulus']}: "
        f"covered={report['covered_count']}/{report['total_residues']} "
        f"({report['covered_pct']:.2f}%)"
    )
    console.print(f"uncovered residues: {report['uncovered_residues']}")


@app.command("loop")
def loop_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    modulus: int = typer.Option(
        ...,
        "--modulus",
        help="Coverage modulus to analyze.",
        callback=_validate_positive_modulus,
    ),
    max_targets: int = typer.Option(
        5, "--max-targets", help="Maximum uncovered residues to target."
    ),
    max_per_target: int = typer.Option(
        5,
        "--max-per-target",
        help="Maximum n examples generated per target residue.",
    ),
    max_new_identities: int = typer.Option(
        10,
        "--max-new-identities",
        help="Maximum identities to mine in this loop.",
    ),
) -> None:
    """Run one end-to-end deterministic loop for mining and coverage updates.

    Examples:
        strausforge loop --identity data/identities.jsonl --modulus 24
        strausforge loop --identity data/identities.jsonl --modulus 24 \
            --max-targets 4 --max-per-target 3
    """
    existing = _load_identities(identity_file)
    before = coverage_report(existing, modulus=modulus)
    console.print(
        f"before: covered={before['covered_count']}/{before['total_residues']} "
        f"({before['covered_pct']:.2f}%), uncovered={before['uncovered_count']}"
    )

    uncovered = before["uncovered_residues"]
    planned_targets = min(len(uncovered), max_targets)
    console.print(
        "run plan: "
        f"uncovered_residues={len(uncovered)}, targets={planned_targets}, "
        f"max_per_target={max_per_target}, max_new_identities={max_new_identities}"
    )

    result = run_loop(
        identity_path=identity_file,
        modulus=modulus,
        max_targets=max_targets,
        max_per_target=max_per_target,
        max_new_identities=max_new_identities,
    )

    after = result["after"]
    before_count = before["covered_count"]
    after_count = after["covered_count"]
    delta_count = int(after_count) - int(before_count)
    new_covered = sorted(set(after["covered_residues"]) - set(before["covered_residues"]))
    console.print(
        f"after: covered={after['covered_count']}/{after['total_residues']} "
        f"({after['covered_pct']:.2f}%), uncovered={after['uncovered_count']}"
    )
    console.print(
        "delta: "
        f"covered {before['covered_count']} -> {after['covered_count']} ({delta_count:+d}), "
        f"uncovered {before['uncovered_count']} -> {after['uncovered_count']}, "
        f"covered_pct {before['covered_pct']:.2f}% -> {after['covered_pct']:.2f}%"
    )
    if new_covered:
        console.print(f"newly covered residues: {new_covered}")

    console.print(
        f"loop result: targets_used={result['targets_used']}, n_tested={result['n_tested']}, "
        f"certs={result['certs_written']}, identities_added={result['identities_added']}"
    )

    if result["identities_added"] == 0:
        raise typer.Exit(code=1)


def _load_certs(path: Path) -> list[Certificate]:
    certs: list[Certificate] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            certs.append(from_jsonl(stripped))
    return certs


def _load_identities(path: Path) -> list[Identity]:
    identities: list[Identity] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            identities.append(identity_from_jsonl(stripped))
    return identities


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
