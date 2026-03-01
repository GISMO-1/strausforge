"""Command-line interface for strausforge."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import defaultdict
from csv import DictWriter
from fractions import Fraction
from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console

from .cert import Certificate, from_jsonl, make_certificate, to_jsonl
from .coverage import coverage_report
from .erdos_straus import check_identity, find_solution, find_solution_fast
from .fit import fit_identities
from .identities import (
    Identity,
    _eval_procedural_identity,
    eval_identity,
    identity_applies,
    identity_from_jsonl,
    profile_identities,
    verify_identity,
)
from .loop import run_loop
from .mine import mine_identities

app = typer.Typer(help="Search/verification tool for the Erdős–Straus conjecture.")
console = Console()
_PROC_HEURISTIC_CHOICES = {"off", "prime-window", "prime-or-square-window"}


class _ProgressPrinter:
    """Low-noise single-line progress printer for long-running CLI loops."""

    def __init__(self, *, enabled: bool, total: int, label: str) -> None:
        self.enabled = enabled
        self.total = max(total, 1)
        self.label = label
        self._started = perf_counter()
        self._last_render = 0.0

    def update(self, completed: int) -> None:
        """Render in-place progress output with percent and ETA."""
        if not self.enabled:
            return

        now = perf_counter()
        capped = max(0, min(completed, self.total))
        should_render = capped == self.total or (now - self._last_render) >= 0.25
        if not should_render:
            return

        elapsed = max(now - self._started, 1e-9)
        pct = (100.0 * capped) / self.total
        eta_seconds = int((self.total - capped) * (elapsed / capped)) if capped > 0 else 0
        eta_text = _format_eta(eta_seconds)
        message = f"\r{self.label}: {pct:6.2f}% ({capped}/{self.total}) ETA {eta_text}"
        sys.stderr.write(message)
        sys.stderr.flush()
        self._last_render = now

        if capped == self.total:
            sys.stderr.write("\n")
            sys.stderr.flush()


def _format_eta(seconds: int) -> str:
    """Format ETA seconds as ``HH:MM:SS``."""
    hours, rem = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@app.command("gui")
def gui_cmd(
    identity_file: Path = typer.Option(
        Path("data/identities.jsonl"),
        "--identity",
        help="Identity JSONL path to preload in the GUI.",
    ),
) -> None:
    """Launch the Streamlit GUI.

    Examples:
        strausforge gui
        strausforge gui --identity data/identities.jsonl
    """
    app_path = Path(__file__).with_name("gui_app.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--",
        "--identity",
        str(identity_file),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)


def _is_prime_deterministic(n_value: int) -> bool:
    """Return whether ``n_value`` is prime via deterministic trial division."""
    if n_value <= 1:
        return False
    if n_value <= 3:
        return True
    if n_value % 2 == 0 or n_value % 3 == 0:
        return False

    divisor = 5
    while divisor * divisor <= n_value:
        if n_value % divisor == 0 or n_value % (divisor + 2) == 0:
            return False
        divisor += 6
    return True


def _is_square_value(n_value: int) -> bool:
    """Return whether ``n_value`` is a perfect square."""
    if n_value < 0:
        return False
    root = math.isqrt(n_value)
    return root * root == n_value


def _percentile_95(values: list[int]) -> int:
    """Return deterministic ceil-index p95 for ``values``; return 0 for empty input."""
    if not values:
        return 0
    ordered = sorted(values)
    index = (95 * len(ordered) + 99) // 100 - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _first_matching_identity(
    identities: list[Identity],
    n_value: int,
    proc_heuristic: str,
) -> tuple[Identity, tuple[int, int, int], str, int, int] | None:
    """Return first successful identity evaluation for ``n_value`` with diagnostics."""
    for identity in identities:
        if not identity_applies(identity, n_value):
            continue
        if identity.kind == "procedural":
            triple, path, window_used, t_used = _eval_procedural_identity(
                identity,
                n_value,
                proc_heuristic=proc_heuristic,
            )
            return identity, triple, path, window_used, t_used

        triple = eval_identity(identity, n_value, proc_heuristic=proc_heuristic)
        if triple is None:
            continue
        return identity, triple, "fast", 0, 0

    return None


def _write_hardness_plot(rows: list[dict[str, float | int]], out_path: Path) -> None:
    """Write hardness rate plot PNG using matplotlib."""
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as error:
        raise typer.BadParameter(
            "matplotlib is required for --plot; install it and rerun."
        ) from error

    x_values = [int(row["bin_start"]) for row in rows]
    expanded_rate = [float(row["expanded_rate"]) for row in rows]
    expanded_squares_rate = [
        (float(row["expanded_squares"]) / float(row["total"])) if int(row["total"]) > 0 else 0.0
        for row in rows
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x_values, expanded_rate, marker="o", label="expanded/total")
    ax.plot(x_values, expanded_squares_rate, marker="x", label="expanded_squares/total")
    ax.set_xlabel("bin_start")
    ax.set_ylabel("rate")
    ax.set_title("Identity hardness distribution")
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


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
    proc_heuristic: str = typer.Option(
        "off",
        "--proc-heuristic",
        help="Procedural heuristic: off, prime-window, or prime-or-square-window.",
    ),
) -> None:
    """Find the first identity that applies to ``n`` and print ``(x, y, z)``.

    Examples:
        strausforge id-check --identity data/identities.jsonl --n 35
        strausforge id-check --identity data/identities.jsonl --n 35809 \
            --proc-heuristic prime-window
        strausforge id-check --identity data/identities.jsonl --n 994009 \
            --proc-heuristic prime-or-square-window
    """
    if proc_heuristic not in _PROC_HEURISTIC_CHOICES:
        raise typer.BadParameter(
            "Expected --proc-heuristic to be one of off, prime-window, prime-or-square-window."
        )

    for identity in _load_identities(identity_file):
        applies = identity_applies(identity, n)
        if not applies:
            continue

        triple = eval_identity(identity, n, proc_heuristic=proc_heuristic)
        if triple is None:
            console.print(
                "identity applies but did not produce a valid decomposition: "
                f"identity={identity.name}, n={n}"
            )
            raise typer.Exit(code=1)

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
    proc_heuristic: str = typer.Option(
        "off",
        "--proc-heuristic",
        help="Procedural heuristic: off, prime-window, or prime-or-square-window.",
    ),
) -> None:
    """Empirically verify each stored identity over a range.

    Examples:
        strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500
        strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500 \
            --proc-heuristic prime-window
        strausforge id-verify --identity data/identities.jsonl --n-min 2 --n-max 500 \
            --proc-heuristic prime-or-square-window
    """
    if n_min > n_max:
        raise typer.BadParameter("Expected --n-min <= --n-max.")
    if proc_heuristic not in _PROC_HEURISTIC_CHOICES:
        raise typer.BadParameter(
            "Expected --proc-heuristic to be one of off, prime-window, prime-or-square-window."
        )

    for identity in _load_identities(identity_file):
        stats = verify_identity(identity, n_min=n_min, n_max=n_max, proc_heuristic=proc_heuristic)
        console.print(
            f"identity={identity.name}, tested={stats['tested']}, "
            f"passed={stats['passed']}, failed={stats['failed']}"
        )


@app.command("profile")
def profile_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    n_min: int = typer.Option(..., "--n-min", help="Minimum n."),
    n_max: int = typer.Option(..., "--n-max", help="Maximum n."),
    top: int = typer.Option(25, "--top", help="Number of hardest cases to print."),
    proc_heuristic: str = typer.Option(
        "off",
        "--proc-heuristic",
        help="Procedural heuristic: off, prime-window, or prime-or-square-window.",
    ),
    progress: bool = typer.Option(
        False,
        "--progress/--no-progress",
        help="Show in-place progress with percent and ETA.",
    ),
) -> None:
    """Profile procedural hardness and fallback rates over a range.

    Examples:
        strausforge profile --identity data/identities.jsonl --n-min 2 --n-max 2000000
        strausforge profile --identity data/identities.jsonl --n-min 2 --n-max 50000 --top 10
        strausforge profile --identity data/identities.jsonl --n-min 2 --n-max 50000 \
            --proc-heuristic prime-window
        strausforge profile --identity data/identities.jsonl --n-min 994009 --n-max 994009 \
            --proc-heuristic prime-or-square-window
    """
    if n_min > n_max:
        raise typer.BadParameter("Expected --n-min <= --n-max.")
    if top <= 0:
        raise typer.BadParameter("Expected --top > 0.")
    if proc_heuristic not in _PROC_HEURISTIC_CHOICES:
        raise typer.BadParameter(
            "Expected --proc-heuristic to be one of off, prime-window, prime-or-square-window."
        )

    identities = _load_identities(identity_file)
    progress_printer = _ProgressPrinter(
        enabled=progress,
        total=len(identities) * (n_max - n_min + 1),
        label="profile",
    )

    def _on_progress(completed: int, total: int) -> None:
        # ``total`` is provided by the core callback contract for clarity.
        del total
        progress_printer.update(completed)

    profile = profile_identities(
        identities=identities,
        n_min=n_min,
        n_max=n_max,
        top_k=top,
        proc_heuristic=proc_heuristic,
        progress_callback=_on_progress if progress else None,
    )

    console.print("identity profile summary:")
    for identity in identities:
        stats = profile.per_identity[identity.name]
        total = stats.total_applications
        fast_pct = (100.0 * stats.fast_success / total) if total else 0.0
        expanded_pct = (100.0 * stats.expanded_success / total) if total else 0.0
        solver_pct = (100.0 * stats.solver_fallback_success / total) if total else 0.0
        line = (
            f"identity={identity.name}, total={total}, "
            f"fast={stats.fast_success} ({fast_pct:.2f}%), "
            f"expanded={stats.expanded_success} ({expanded_pct:.2f}%), "
            f"solver_fallback={stats.solver_fallback_success} ({solver_pct:.2f}%)"
        )
        if identity.kind == "procedural":
            line += (
                f", expanded_primes={stats.expanded_prime_count}/{stats.expanded_success}, "
                f"expanded_squares={stats.expanded_square_count}/{stats.expanded_success}, "
                f"max_window_used={stats.max_window_used}, max_t_used={stats.max_t_used}"
            )
        console.print(line)

    console.print(f"top {len(profile.hardest_records)} hardest n records:")
    for record in profile.hardest_records:
        console.print(
            f"identity={record.identity}, n={record.n}, path={record.path}, "
            f"window_used={record.window_used}, t_used={record.t_used}"
        )


@app.command("hardness")
def hardness_cmd(
    identity_file: Path = typer.Option(..., "--identity", help="Identity JSONL file."),
    n_min: int = typer.Option(..., "--n-min", help="Minimum n (inclusive)."),
    n_max: int = typer.Option(..., "--n-max", help="Maximum n (inclusive)."),
    bin_size: int = typer.Option(10000, "--bin-size", help="Bin width."),
    out: Path = typer.Option(Path("hardness.csv"), "--out", help="Output CSV path."),
    proc_heuristic: str = typer.Option(
        "prime-or-square-window",
        "--proc-heuristic",
        help="Procedural heuristic: off, prime-window, or prime-or-square-window.",
    ),
    only_proc: bool = typer.Option(
        False,
        "--only-proc",
        help="Analyze only procedural identities (fit_proc_*).",
    ),
    plot: Path | None = typer.Option(None, "--plot", help="Optional PNG plot path."),
    export_expanded: Path | None = typer.Option(
        None,
        "--export-expanded",
        help="Optional JSONL path to stream expanded-case records.",
    ),
    progress: bool = typer.Option(
        False,
        "--progress/--no-progress",
        help="Show in-place progress with percent and ETA.",
    ),
) -> None:
    """Export binned hardness distribution for identity evaluation.

    Examples:
        strausforge hardness --identity data/identities.jsonl --n-min 2 --n-max 50000
        strausforge hardness --identity data/identities.jsonl --n-min 2 --n-max 50000 \
            --only-proc --out hardness_proc.csv
        strausforge hardness --identity data/identities.jsonl --n-min 2 --n-max 50000 \
            --plot hardness.png
        strausforge hardness --identity data/identities.jsonl --n-min 2 --n-max 50000 \
            --export-expanded expanded.jsonl
    """
    if n_min > n_max:
        raise typer.BadParameter("Expected --n-min <= --n-max.")
    if bin_size <= 0:
        raise typer.BadParameter("Expected --bin-size > 0.")
    if proc_heuristic not in _PROC_HEURISTIC_CHOICES:
        raise typer.BadParameter(
            "Expected --proc-heuristic to be one of off, prime-window, prime-or-square-window."
        )

    identities = _load_identities(identity_file)
    if only_proc:
        identities = [
            identity
            for identity in identities
            if identity.kind == "procedural" and identity.name.startswith("fit_proc_")
        ]

    columns = [
        "bin_start",
        "bin_end",
        "total",
        "fast",
        "expanded",
        "solver_fallback",
        "expanded_rate",
        "prime_total",
        "square_total",
        "expanded_primes",
        "expanded_squares",
        "max_t_used",
        "p95_t_used",
        "max_window_used",
    ]

    bins: dict[int, dict[str, object]] = {}
    progress_printer = _ProgressPrinter(
        enabled=progress,
        total=n_max - n_min + 1,
        label="hardness",
    )
    export_handle = None
    try:
        if export_expanded is not None:
            export_expanded.parent.mkdir(parents=True, exist_ok=True)
            export_handle = export_expanded.open("w", encoding="utf-8")

        for n_value in range(n_min, n_max + 1):
            progress_printer.update(n_value - n_min + 1)
            bin_start = ((n_value - n_min) // bin_size) * bin_size + n_min
            bin_end = min(bin_start + bin_size - 1, n_max)
            if bin_start not in bins:
                bins[bin_start] = {
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "total": 0,
                    "fast": 0,
                    "expanded": 0,
                    "solver_fallback": 0,
                    "prime_total": 0,
                    "square_total": 0,
                    "expanded_primes": 0,
                    "expanded_squares": 0,
                    "max_t_used": 0,
                    "max_window_used": 0,
                    "t_values": [],
                }

            entry = bins[bin_start]
            is_prime = _is_prime_deterministic(n_value)
            is_square = _is_square_value(n_value)
            if is_prime:
                entry["prime_total"] = int(entry["prime_total"]) + 1
            if is_square:
                entry["square_total"] = int(entry["square_total"]) + 1

            matched = _first_matching_identity(
                identities=identities,
                n_value=n_value,
                proc_heuristic=proc_heuristic,
            )
            if matched is None:
                continue

            identity, _, path, window_used, t_used = matched
            entry["total"] = int(entry["total"]) + 1
            if path == "fast":
                entry["fast"] = int(entry["fast"]) + 1
            elif path == "expanded":
                entry["expanded"] = int(entry["expanded"]) + 1
                if is_prime:
                    entry["expanded_primes"] = int(entry["expanded_primes"]) + 1
                if is_square:
                    entry["expanded_squares"] = int(entry["expanded_squares"]) + 1
                if export_handle is not None:
                    export_handle.write(
                        json.dumps(
                            {
                                "n": n_value,
                                "identity": identity.name,
                                "path": path,
                                "t_used": t_used,
                                "window_used": window_used,
                                "is_prime": is_prime,
                                "is_square": is_square,
                                "proc_heuristic": proc_heuristic,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
            else:
                entry["solver_fallback"] = int(entry["solver_fallback"]) + 1

            entry["max_t_used"] = max(int(entry["max_t_used"]), t_used)
            entry["max_window_used"] = max(int(entry["max_window_used"]), window_used)
            cast_values = entry["t_values"]
            assert isinstance(cast_values, list)
            cast_values.append(t_used)
    finally:
        if export_handle is not None:
            export_handle.close()

    rows: list[dict[str, float | int]] = []
    for bin_start in sorted(bins):
        entry = bins[bin_start]
        total = int(entry["total"])
        expanded = int(entry["expanded"])
        t_values = entry["t_values"]
        assert isinstance(t_values, list)
        row: dict[str, float | int] = {
            "bin_start": int(entry["bin_start"]),
            "bin_end": int(entry["bin_end"]),
            "total": total,
            "fast": int(entry["fast"]),
            "expanded": expanded,
            "solver_fallback": int(entry["solver_fallback"]),
            "expanded_rate": (float(expanded) / float(total)) if total > 0 else 0.0,
            "prime_total": int(entry["prime_total"]),
            "square_total": int(entry["square_total"]),
            "expanded_primes": int(entry["expanded_primes"]),
            "expanded_squares": int(entry["expanded_squares"]),
            "max_t_used": int(entry["max_t_used"]),
            "p95_t_used": _percentile_95([int(item) for item in t_values]),
            "max_window_used": int(entry["max_window_used"]),
        }
        rows.append(row)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    if plot is not None:
        _write_hardness_plot(rows, plot)

    console.print(f"summary: bins={len(rows)}, out={out}")


@app.command("expanded-stats")
def expanded_stats_cmd(
    in_file: Path = typer.Option(..., "--in", help="Expanded JSONL input path."),
    out_file: Path | None = typer.Option(None, "--out", help="Optional report output path."),
    modulus: int = typer.Option(48, "--mod", help="Residue histogram modulus."),
    top: int = typer.Option(20, "--top", help="Maximum identities to report."),
) -> None:
    """Summarize exported expanded-case JSONL from ``hardness --export-expanded``.

    Examples:
        strausforge expanded-stats --in expanded.jsonl
        strausforge expanded-stats --in expanded.jsonl --out expanded_stats.txt --mod 96 --top 15
    """
    if modulus <= 0:
        raise typer.BadParameter("Expected --mod > 0.")
    if top <= 0:
        raise typer.BadParameter("Expected --top > 0.")

    total = 0
    prime_count = 0
    square_count = 0
    residue_counts: dict[int, int] = defaultdict(int)
    identity_counts: dict[str, int] = defaultdict(int)

    with in_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            n_value = int(payload["n"])
            identity_name = str(payload["identity"])
            is_prime = bool(payload["is_prime"])
            is_square = bool(payload["is_square"])

            total += 1
            if is_prime:
                prime_count += 1
            if is_square:
                square_count += 1
            residue_counts[n_value % modulus] += 1
            identity_counts[identity_name] += 1

    lines: list[str] = [
        f"total_expanded_records: {total}",
        (f"is_prime: {prime_count} ({((100.0 * prime_count / total) if total else 0.0):.2f}%)"),
        (f"is_square: {square_count} ({((100.0 * square_count / total) if total else 0.0):.2f}%)"),
        f"residue_histogram_mod_{modulus}:",
    ]

    for residue in sorted(residue_counts):
        lines.append(f"  residue={residue}: count={residue_counts[residue]}")

    lines.append(f"top_identities (top={top}):")
    sorted_identities = sorted(identity_counts.items(), key=lambda item: (-item[1], item[0]))[:top]
    for identity_name, count in sorted_identities:
        lines.append(f"  identity={identity_name}: count={count}")

    report_text = "\n".join(lines)
    if out_file is None:
        console.print(report_text)
        return

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_text + "\n", encoding="utf-8")
    console.print(f"summary: out={out_file}")


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


@app.command("fit")
def fit_cmd(
    in_file: Path = typer.Option(..., "--in", help="Input solution JSONL file."),
    modulus: int = typer.Option(
        ...,
        "--modulus",
        help="Target modulus for residue filtering.",
        callback=_validate_positive_modulus,
    ),
    residue: int = typer.Option(..., "--residue", help="Target residue class."),
    out_file: Path = typer.Option(..., "--out", help="Output fitted identity JSONL."),
    max_identities: int = typer.Option(10, "--max-identities", help="Maximum fitted identities."),
    strategy: str = typer.Option(
        "auto",
        "--strategy",
        help="Fit strategy: affine, procedural, or auto (affine then procedural).",
    ),
    window: int = typer.Option(
        8,
        "--window",
        help="x-neighborhood half-window for procedural fitting.",
    ),
    t_max: int = typer.Option(
        256,
        "--t-max",
        help="Maximum y increment attempts in 2-term completion.",
    ),
) -> None:
    """Fit deterministic residue-class identities from solved samples.

    Examples:
        strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 1 \
            --out data/identities_fit.jsonl
        strausforge fit --in hard_48_r1_r25.jsonl --modulus 48 --residue 25 \
            --out data/identities_fit.jsonl --strategy procedural --window 8 --t-max 256
    """
    if max_identities <= 0:
        raise typer.BadParameter("Expected --max-identities > 0.")
    if strategy not in {"auto", "affine", "procedural"}:
        raise typer.BadParameter("Expected --strategy to be one of auto, affine, procedural.")
    if window < 0:
        raise typer.BadParameter("Expected --window >= 0.")
    if t_max < 0:
        raise typer.BadParameter("Expected --t-max >= 0.")

    fitted = fit_identities(
        in_file=in_file,
        out_file=out_file,
        modulus=modulus,
        residue=residue,
        max_identities=max_identities,
        strategy=strategy,
        window=window,
        t_max=t_max,
    )
    symbolic = sum(1 for identity in fitted if "symbolic" in identity.notes)
    empirical_only = sum(1 for identity in fitted if "empirical-only" in identity.notes)
    console.print(
        f"summary: identities_found={len(fitted)}, "
        f"symbolic_verified={symbolic}, empirical_only={empirical_only}"
    )
    if not fitted:
        raise typer.Exit(code=1)


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
    target_timeout_seconds: float = typer.Option(
        30.0,
        "--target-timeout-seconds",
        help="Per-target generation timeout in seconds.",
    ),
    progress_every: int = typer.Option(
        200,
        "--progress-every",
        help="Print per-target progress every N generated examples.",
    ),
    enable_fit_fallback: bool = typer.Option(
        False,
        "--enable-fit-fallback",
        help="Run data-driven fit mining when template mining adds no identities.",
    ),
    fit_max_identities: int = typer.Option(
        10,
        "--fit-max-identities",
        help="Maximum identities per residue for fit fallback.",
    ),
) -> None:
    """Run one end-to-end deterministic loop for mining and coverage updates.

    Examples:
        strausforge loop --identity data/identities.jsonl --modulus 24
        strausforge loop --identity data/identities.jsonl --modulus 24 \
            --max-targets 4 --max-per-target 3
        strausforge loop --identity data/identities.jsonl --modulus 48 \
            --max-targets 12 --max-per-target 400 --target-timeout-seconds 15
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

    def _progress(message: str) -> None:
        console.print(f"progress: {message}")

    result = run_loop(
        identity_path=identity_file,
        modulus=modulus,
        max_targets=max_targets,
        max_per_target=max_per_target,
        max_new_identities=max_new_identities,
        target_timeout_seconds=target_timeout_seconds,
        progress_every=progress_every,
        progress_callback=_progress,
        enable_fit_fallback=enable_fit_fallback,
        fit_max_identities=fit_max_identities,
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
    if result["timed_out_targets"]:
        console.print(f"timed out targets: {result['timed_out_targets']}")

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
