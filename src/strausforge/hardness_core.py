"""Shared core APIs for hardness and expanded-case statistics.

This module intentionally has no CLI or GUI dependencies so it can be reused
from both Typer commands and Streamlit UI code.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .factor_meta import (
    is_prime_trial,
    semiprime_kind_from_spf,
    semiprime_window_trigger,
    write_jsonl_record,
)
from .identities import (
    Identity,
    _eval_procedural_identity,
    eval_identity,
    identity_applies,
    identity_from_jsonl,
)

PROC_HEURISTIC_CHOICES = {
    "off",
    "prime-window",
    "prime-or-square-window",
    "prime-or-square-or-semiprime-window",
    "semiprime-window",
}
HARDNESS_COLUMNS = [
    "bin_start",
    "bin_end",
    "total",
    "fast",
    "escalated",
    "expanded_exported",
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
ProgressCallback = Callable[[int, int], None]


def load_identities(path: Path) -> list[Identity]:
    """Load identities from JSONL.

    Examples:
        >>> ids = load_identities(Path("data/identities.jsonl"))
        >>> len(ids) >= 0
        True
    """
    identities: list[Identity] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            identities.append(identity_from_jsonl(stripped))
    return identities


def is_square_value(n_value: int) -> bool:
    """Return whether ``n_value`` is a perfect square."""
    if n_value < 0:
        return False
    root = math.isqrt(n_value)
    return root * root == n_value


def percentile_95(values: list[int]) -> int:
    """Return deterministic ceil-index p95 for ``values``; return 0 for empty input."""
    if not values:
        return 0
    ordered = sorted(values)
    index = (95 * len(ordered) + 99) // 100 - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def first_matching_identity(
    identities: list[Identity],
    n_value: int,
    proc_heuristic: str,
    semiprime_factor_bound: int = 5000,
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
                semiprime_factor_bound=semiprime_factor_bound,
            )
            return identity, triple, path, window_used, t_used

        triple = eval_identity(identity, n_value, proc_heuristic=proc_heuristic)
        if triple is None:
            continue
        return identity, triple, "fast", 0, 0

    return None


def run_hardness(
    *,
    identities: list[Identity],
    n_min: int,
    n_max: int,
    bin_size: int,
    proc_heuristic: str,
    only_proc: bool = False,
    export_expanded: Path | None = None,
    export_expanded_meta: Path | None = None,
    expanded_factor_bound: int = 5000,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict[str, float | int]], dict[str, float | int]]:
    """Run deterministic hardness profiling and optional expanded-case export.

    Examples:
        >>> ids = load_identities(Path("data/identities.jsonl"))
        >>> rows, summary = run_hardness(
        ...     identities=ids,
        ...     n_min=2,
        ...     n_max=20,
        ...     bin_size=10,
        ...     proc_heuristic="off",
        ... )
        >>> isinstance(rows, list) and "bins" in summary
        True
    """
    if n_min > n_max:
        raise ValueError("Expected n_min <= n_max.")
    if bin_size <= 0:
        raise ValueError("Expected bin_size > 0.")
    if proc_heuristic not in PROC_HEURISTIC_CHOICES:
        raise ValueError(
            "Expected proc_heuristic to be one of off, prime-window, "
            "prime-or-square-window, prime-or-square-or-semiprime-window, semiprime-window."
        )
    if expanded_factor_bound <= 0:
        raise ValueError("Expected expanded_factor_bound > 0.")

    selected_identities = identities
    if only_proc:
        selected_identities = [
            identity
            for identity in identities
            if identity.kind == "procedural" and identity.name.startswith("fit_proc_")
        ]

    bins: dict[int, dict[str, object]] = {}
    total_steps = n_max - n_min + 1
    export_handle = None
    export_meta_handle = None
    try:
        if export_expanded is not None:
            export_expanded.parent.mkdir(parents=True, exist_ok=True)
            export_handle = export_expanded.open("w", encoding="utf-8")
        if export_expanded_meta is not None:
            export_expanded_meta.parent.mkdir(parents=True, exist_ok=True)
            export_meta_handle = export_expanded_meta.open("w", encoding="utf-8")

        for step, n_value in enumerate(range(n_min, n_max + 1), start=1):
            if progress_callback is not None:
                progress_callback(step, total_steps)

            bin_start = ((n_value - n_min) // bin_size) * bin_size + n_min
            bin_end = min(bin_start + bin_size - 1, n_max)
            if bin_start not in bins:
                bins[bin_start] = {
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "total": 0,
                    "fast": 0,
                    "escalated": 0,
                    "expanded_exported": 0,
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
            is_prime = is_prime_trial(n_value)
            is_square = is_square_value(n_value)
            if is_prime:
                entry["prime_total"] = int(entry["prime_total"]) + 1
            if is_square:
                entry["square_total"] = int(entry["square_total"]) + 1

            matched = first_matching_identity(
                identities=selected_identities,
                n_value=n_value,
                proc_heuristic=proc_heuristic,
                semiprime_factor_bound=expanded_factor_bound,
            )
            if matched is None:
                continue

            identity, _, path, window_used, t_used = matched
            entry["total"] = int(entry["total"]) + 1
            if path == "fast":
                entry["fast"] = int(entry["fast"]) + 1
            elif path == "expanded":
                entry["escalated"] = int(entry["escalated"]) + 1
                if is_prime:
                    entry["expanded_primes"] = int(entry["expanded_primes"]) + 1
                if is_square:
                    entry["expanded_squares"] = int(entry["expanded_squares"]) + 1
                if export_handle is not None:
                    write_jsonl_record(
                        export_handle,
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
                    )
                    entry["expanded_exported"] = int(entry["expanded_exported"]) + 1
                if export_meta_handle is not None:
                    semiprime_triggered, spf, spf_bound_used = semiprime_window_trigger(
                        n_value,
                        expanded_factor_bound,
                    )
                    cofactor, semiprime_kind = semiprime_kind_from_spf(n_value, spf)
                    proc_stage = "none"
                    if is_prime:
                        proc_stage = "prime"
                    elif is_square:
                        proc_stage = "square"
                    elif semiprime_triggered:
                        proc_stage = "semiprime"
                    write_jsonl_record(
                        export_meta_handle,
                        {
                            "n": n_value,
                            "res48": n_value % 48,
                            "identity": identity.name,
                            "t_used": t_used,
                            "window_used": window_used,
                            "proc_heuristic": proc_heuristic,
                            "proc_stage": proc_stage,
                            "semiprime_triggered": semiprime_triggered,
                            "spf_bound_used": spf_bound_used,
                            "spf": spf,
                            "cofactor": cofactor,
                            "semiprime_kind": semiprime_kind,
                        },
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
        if export_meta_handle is not None:
            export_meta_handle.close()

    rows: list[dict[str, float | int]] = []
    for bin_start in sorted(bins):
        entry = bins[bin_start]
        total = int(entry["total"])
        escalated = int(entry["escalated"])
        t_values = entry["t_values"]
        assert isinstance(t_values, list)
        rows.append(
            {
                "bin_start": int(entry["bin_start"]),
                "bin_end": int(entry["bin_end"]),
                "total": total,
                "fast": int(entry["fast"]),
                "escalated": escalated,
                "expanded_exported": int(entry["expanded_exported"]),
                "solver_fallback": int(entry["solver_fallback"]),
                "expanded_rate": (float(escalated) / float(total)) if total > 0 else 0.0,
                "prime_total": int(entry["prime_total"]),
                "square_total": int(entry["square_total"]),
                "expanded_primes": int(entry["expanded_primes"]),
                "expanded_squares": int(entry["expanded_squares"]),
                "max_t_used": int(entry["max_t_used"]),
                "p95_t_used": percentile_95([int(item) for item in t_values]),
                "max_window_used": int(entry["max_window_used"]),
            }
        )

    expanded_total = sum(int(row["escalated"]) for row in rows)
    expanded_exported_total = sum(int(row["expanded_exported"]) for row in rows)
    matched_total = sum(int(row["total"]) for row in rows)
    summary: dict[str, float | int] = {
        "bins": len(rows),
        "matched_total": matched_total,
        "expanded_total": expanded_total,
        "expanded_exported_total": expanded_exported_total,
        "expanded_rate": (float(expanded_total) / float(matched_total)) if matched_total else 0.0,
    }
    return rows, summary


def summarize_expanded_jsonl(path: Path, mod: int, top: int) -> dict[str, Any]:
    """Summarize expanded-case JSONL records deterministically.

    Examples:
        >>> summary = summarize_expanded_jsonl(Path("tests/fixtures/expanded_small.jsonl"), 48, 2)
        >>> summary["total_expanded_records"]
        4
    """
    if mod <= 0:
        raise ValueError("Expected mod > 0.")
    if top <= 0:
        raise ValueError("Expected top > 0.")

    total = 0
    prime_count = 0
    square_count = 0
    residue_counts: dict[int, int] = defaultdict(int)
    identity_counts: dict[str, int] = defaultdict(int)

    with path.open("r", encoding="utf-8") as handle:
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
            residue_counts[n_value % mod] += 1
            identity_counts[identity_name] += 1

    sorted_residue_hist = [
        {"residue": residue, "count": residue_counts[residue]} for residue in sorted(residue_counts)
    ]
    top_identities = [
        {"identity": identity_name, "count": count}
        for identity_name, count in sorted(
            identity_counts.items(), key=lambda item: (-item[1], item[0])
        )[:top]
    ]

    return {
        "total_expanded_records": total,
        "prime_count": prime_count,
        "square_count": square_count,
        "prime_pct": (100.0 * prime_count / total) if total else 0.0,
        "square_pct": (100.0 * square_count / total) if total else 0.0,
        "modulus": mod,
        "residue_histogram": sorted_residue_hist,
        "top": top,
        "top_identities": top_identities,
    }


def format_expanded_stats_report(summary: dict[str, Any]) -> str:
    """Render text report for :func:`summarize_expanded_jsonl`."""
    lines: list[str] = [
        f"total_expanded_records: {summary['total_expanded_records']}",
        f"is_prime: {summary['prime_count']} ({summary['prime_pct']:.2f}%)",
        f"is_square: {summary['square_count']} ({summary['square_pct']:.2f}%)",
        f"residue_histogram_mod_{summary['modulus']}:",
    ]

    for item in summary["residue_histogram"]:
        lines.append(f"  residue={item['residue']}: count={item['count']}")

    lines.append(f"top_identities (top={summary['top']}):")
    for item in summary["top_identities"]:
        lines.append(f"  identity={item['identity']}: count={item['count']}")

    return "\n".join(lines)


def write_hardness_plot(rows: list[dict[str, float | int]], out_path: Path) -> None:
    """Write hardness rate plot PNG using matplotlib."""
    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as error:
        raise RuntimeError("matplotlib is required for plot export.") from error

    x_values = [int(row["bin_start"]) for row in rows]
    expanded_rate = [float(row["expanded_rate"]) for row in rows]
    expanded_squares_rate = [
        (float(row["expanded_squares"]) / float(row["total"])) if int(row["total"]) > 0 else 0.0
        for row in rows
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x_values, expanded_rate, marker="o", label="escalated/total")
    ax.plot(x_values, expanded_squares_rate, marker="x", label="expanded_squares/total")
    ax.set_xlabel("bin_start")
    ax.set_ylabel("rate")
    ax.set_title("Identity hardness distribution")
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
