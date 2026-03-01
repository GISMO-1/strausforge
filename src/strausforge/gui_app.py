"""Streamlit GUI for interactive Erdős–Straus exploration.

This module is intentionally isolated from core modules so Streamlit remains
an optional dependency (`pip install -e ".[gui]"`).
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from io import StringIO
from pathlib import Path

import streamlit as st

from strausforge.cli import (
    _first_matching_identity,
    _is_prime_deterministic,
    _is_square_value,
    _load_identities,
    _percentile_95,
)
from strausforge.coverage import coverage_report
from strausforge.erdos_straus import check_identity, find_solution
from strausforge.identities import Identity

_PROC_HEURISTICS = ["off", "prime-window", "prime-or-square-window"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--identity", default="data/identities.jsonl")
    return parser.parse_known_args()[0]


def _load_identities_safe(path: Path) -> list[Identity]:
    if not path.exists():
        return []
    try:
        return _load_identities(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def _run_hardness_rows(
    identities: list[Identity],
    n_min: int,
    n_max: int,
    bin_size: int,
    proc_heuristic: str,
) -> list[dict[str, float | int]]:
    bins: dict[int, dict[str, object]] = {}

    for n_value in range(n_min, n_max + 1):
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

        _, _, path, window_used, t_used = matched
        entry["total"] = int(entry["total"]) + 1
        if path == "fast":
            entry["fast"] = int(entry["fast"]) + 1
        elif path == "expanded":
            entry["expanded"] = int(entry["expanded"]) + 1
            if is_prime:
                entry["expanded_primes"] = int(entry["expanded_primes"]) + 1
            if is_square:
                entry["expanded_squares"] = int(entry["expanded_squares"]) + 1
        else:
            entry["solver_fallback"] = int(entry["solver_fallback"]) + 1

        entry["max_t_used"] = max(int(entry["max_t_used"]), t_used)
        entry["max_window_used"] = max(int(entry["max_window_used"]), window_used)
        t_values = entry["t_values"]
        assert isinstance(t_values, list)
        t_values.append(t_used)

    rows: list[dict[str, float | int]] = []
    for bin_start in sorted(bins):
        entry = bins[bin_start]
        total = int(entry["total"])
        expanded = int(entry["expanded"])
        t_values = entry["t_values"]
        assert isinstance(t_values, list)
        rows.append(
            {
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
        )

    return rows


def _rows_to_csv(rows: list[dict[str, float | int]]) -> str:
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
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def main() -> None:
    args = _parse_args()
    default_identity_path = Path(args.identity)

    st.set_page_config(page_title="Strausforge", layout="wide")
    st.title("Strausforge GUI")
    st.caption("Interactive tooling for Erdős–Straus identities (non-developer workflow).")

    identity_path_text = st.sidebar.text_input(
        "Identity JSONL path",
        value=str(default_identity_path),
        help="Path to identities.jsonl used by ID-check, coverage, and hardness tabs.",
    )
    identity_path = Path(identity_path_text)
    identities = _load_identities_safe(identity_path)

    tabs = st.tabs(["Playground", "Identity Explorer", "Coverage", "Hardness"])

    with tabs[0]:
        st.subheader("Playground")
        n_value = st.number_input("n", min_value=2, value=35, step=1)
        col_search, col_id = st.columns(2)

        if col_search.button("Search", use_container_width=True):
            solution = find_solution(int(n_value))
            if solution is None:
                st.error("No solution found.")
            else:
                x_value, y_value, z_value = solution
                verified = check_identity(int(n_value), x_value, y_value, z_value)
                st.success(f"(x, y, z) = ({x_value}, {y_value}, {z_value})")
                st.write(f"Exact verification: {'PASS' if verified else 'FAIL'}")

        if col_id.button("ID-check", use_container_width=True):
            if not identities:
                st.warning("No identities loaded. Check the JSONL path.")
            else:
                match = _first_matching_identity(identities, int(n_value), proc_heuristic="off")
                if match is None:
                    st.warning(f"No identity applies at n={int(n_value)}.")
                else:
                    identity, triple, path, window_used, t_used = match
                    x_value, y_value, z_value = triple
                    verified = check_identity(int(n_value), x_value, y_value, z_value)
                    st.success(
                        f"identity={identity.name} -> (x, y, z)=({x_value}, {y_value}, {z_value})"
                    )
                    st.write(f"Path: {path}, window_used={window_used}, t_used={t_used}")
                    st.write(f"Exact verification: {'PASS' if verified else 'FAIL'}")

    with tabs[1]:
        st.subheader("Identity Explorer")
        st.write(f"Loaded identities: {len(identities)}")
        if not identities:
            st.info("No identities found at the selected path.")
        else:
            moduli = sorted({item.modulus for item in identities})
            selected_modulus = st.selectbox("Filter by modulus", options=["All", *moduli], index=0)

            residues = sorted({residue for item in identities for residue in item.residues})
            selected_residue = st.selectbox(
                "Filter by residue",
                options=["All", *residues],
                index=0,
            )

            filtered: list[Identity] = []
            for item in identities:
                if selected_modulus != "All" and item.modulus != selected_modulus:
                    continue
                if selected_residue != "All" and selected_residue not in item.residues:
                    continue
                filtered.append(item)

            st.dataframe(
                [
                    {
                        "name": item.name,
                        "kind": item.kind,
                        "modulus": item.modulus,
                        "residues": item.residues,
                        "notes": item.notes,
                    }
                    for item in filtered
                ],
                use_container_width=True,
            )

            if filtered:
                selected_name = st.selectbox(
                    "Select identity for details",
                    options=[item.name for item in filtered],
                )
                selected = next(item for item in filtered if item.name == selected_name)
                st.json(asdict(selected))

    with tabs[2]:
        st.subheader("Coverage")
        modulus = st.number_input("Modulus", min_value=1, value=48, step=1)
        if st.button("Run coverage report"):
            report = coverage_report(identities, int(modulus))
            st.metric(
                "Covered residues",
                f"{report['covered_count']}/{report['total_residues']}",
                f"{report['covered_pct']:.2f}%",
            )
            col_a, col_b = st.columns(2)
            col_a.write("Covered residues")
            col_a.write(report["covered_residues"])
            col_b.write("Uncovered residues")
            col_b.write(report["uncovered_residues"])

    with tabs[3]:
        st.subheader("Hardness")
        col_n1, col_n2 = st.columns(2)
        n_min = col_n1.number_input("n-min", min_value=2, value=35000, step=1)
        n_max = col_n2.number_input("n-max", min_value=2, value=36000, step=1)
        bin_size = st.number_input("bin-size", min_value=1, value=500, step=1)
        proc_heuristic = st.selectbox("proc-heuristic", options=_PROC_HEURISTICS, index=0)

        if st.button("Run hardness"):
            if int(n_min) > int(n_max):
                st.error("Expected n-min <= n-max.")
            elif not identities:
                st.error("No identities loaded for hardness run.")
            else:
                rows = _run_hardness_rows(
                    identities=identities,
                    n_min=int(n_min),
                    n_max=int(n_max),
                    bin_size=int(bin_size),
                    proc_heuristic=proc_heuristic,
                )
                st.dataframe(rows, use_container_width=True)

                if rows:
                    st.line_chart(
                        {
                            "expanded_rate": [float(row["expanded_rate"]) for row in rows],
                        }
                    )

                csv_text = _rows_to_csv(rows)
                st.download_button(
                    "Download CSV",
                    data=csv_text,
                    file_name="hardness.csv",
                    mime="text/csv",
                )

                save_to_experiments = st.checkbox("Save outputs to experiments/")
                if save_to_experiments and st.button("Save now"):
                    experiments_dir = Path("experiments")
                    experiments_dir.mkdir(parents=True, exist_ok=True)
                    csv_path = experiments_dir / "hardness_gui.csv"
                    csv_path.write_text(csv_text, encoding="utf-8")
                    st.success(f"Saved CSV to {csv_path}")


if __name__ == "__main__":
    main()
