"""Streamlit GUI for interactive Erdős–Straus exploration.

This module is intentionally isolated from core modules so Streamlit remains
an optional dependency (`pip install -e "[gui]"`).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from time import perf_counter

import streamlit as st

from strausforge.coverage import coverage_report
from strausforge.erdos_straus import check_identity, find_solution
from strausforge.hardness_core import (
    HARDNESS_COLUMNS,
    PROC_HEURISTIC_CHOICES,
    first_matching_identity,
    format_expanded_stats_report,
    load_identities,
    run_hardness,
    summarize_expanded_jsonl,
    write_hardness_plot,
)
from strausforge.identities import Identity

_PROC_HEURISTICS = sorted(PROC_HEURISTIC_CHOICES)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--identity", default="data/identities.jsonl")
    return parser.parse_known_args()[0]


def _load_identities_safe(path: Path) -> list[Identity]:
    if not path.exists():
        return []
    try:
        return load_identities(path)
    except (OSError, ValueError):
        return []


def _rows_to_csv(rows: list[dict[str, float | int]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HARDNESS_COLUMNS)
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
                match = first_matching_identity(identities, int(n_value), proc_heuristic="off")
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
        st.caption("Uses the same deterministic v0.2 core pipeline as the CLI hardness command.")
        identity_override = st.text_input("identity path", value=str(identity_path))
        col_n1, col_n2 = st.columns(2)
        n_min = col_n1.number_input("n-min", min_value=2, value=35000, step=1)
        n_max = col_n2.number_input("n-max", min_value=2, value=36000, step=1)
        bin_size = st.number_input("bin-size", min_value=1, value=500, step=1)
        proc_heuristic = st.selectbox("proc-heuristic", options=_PROC_HEURISTICS, index=0)
        only_proc = st.checkbox("only-proc", value=True)

        col_export_toggle, col_export_path = st.columns([1, 2])
        export_enabled = col_export_toggle.checkbox("export-expanded")
        export_path_text = col_export_path.text_input(
            "export-expanded path",
            value="expanded_gui.jsonl",
            disabled=not export_enabled,
        )

        col_plot_toggle, col_plot_path = st.columns([1, 2])
        plot_enabled = col_plot_toggle.checkbox("plot")
        plot_path_text = col_plot_path.text_input(
            "plot path",
            value="hardness_gui.png",
            disabled=not plot_enabled,
        )

        out_path_text = st.text_input("out CSV path", value="hardness_gui.csv")

        progress_bar = st.progress(0)
        progress_text = st.empty()

        if st.button("Run hardness", use_container_width=True):
            if int(n_min) > int(n_max):
                st.error("Expected n-min <= n-max.")
            else:
                selected_identities = _load_identities_safe(Path(identity_override))
                if not selected_identities:
                    st.error("No identities loaded for hardness run.")
                else:
                    start = perf_counter()

                    def on_progress(completed: int, total: int) -> None:
                        elapsed = max(perf_counter() - start, 1e-9)
                        pct = int((100 * completed) / max(total, 1))
                        eta_seconds = (
                            int((total - completed) * (elapsed / completed)) if completed else 0
                        )
                        progress_bar.progress(min(max(pct, 0), 100))
                        progress_text.text(
                            f"Progress: {pct}% ({completed}/{total}) ETA {eta_seconds}s"
                        )

                    export_path = Path(export_path_text) if export_enabled else None
                    out_path = Path(out_path_text)
                    plot_path = Path(plot_path_text) if plot_enabled else None

                    try:
                        rows, summary = run_hardness(
                            identities=selected_identities,
                            n_min=int(n_min),
                            n_max=int(n_max),
                            bin_size=int(bin_size),
                            proc_heuristic=proc_heuristic,
                            only_proc=only_proc,
                            export_expanded=export_path,
                            progress_callback=on_progress,
                        )
                    except ValueError as error:
                        st.error(str(error))
                        rows = []
                        summary = {}

                    if rows:
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text(_rows_to_csv(rows), encoding="utf-8")
                        if plot_path is not None:
                            write_hardness_plot(rows, plot_path)

                        progress_text.text("Progress: 100% (complete)")
                        st.success(f"Saved hardness CSV to {out_path}")
                        if export_path is not None:
                            st.success(f"Saved expanded JSONL to {export_path}")
                        if plot_path is not None:
                            st.success(f"Saved hardness plot to {plot_path}")

                        st.dataframe(rows, use_container_width=True)
                        st.metric("bins", int(summary["bins"]))
                        st.metric("expanded total", int(summary["expanded_total"]))
                        st.metric(
                            "expanded rate",
                            f"{100.0 * float(summary['expanded_rate']):.2f}%",
                        )

                        if rows:
                            st.line_chart(
                                {
                                    "expanded_rate": [float(row["expanded_rate"]) for row in rows],
                                }
                            )

                        st.download_button(
                            "Download CSV",
                            data=_rows_to_csv(rows),
                            file_name=out_path.name,
                            mime="text/csv",
                        )

        st.divider()
        st.subheader("Expanded Stats")
        stats_jsonl = st.text_input("expanded jsonl path", value="expanded_gui.jsonl")
        col_mod, col_top = st.columns(2)
        stats_mod = col_mod.number_input("mod", min_value=1, value=48, step=1)
        stats_top = col_top.number_input("top", min_value=1, value=20, step=1)

        if st.button("Run expanded-stats"):
            try:
                summary = summarize_expanded_jsonl(
                    Path(stats_jsonl), int(stats_mod), int(stats_top)
                )
            except (ValueError, OSError) as error:
                st.error(str(error))
            else:
                st.metric("total expanded records", int(summary["total_expanded_records"]))
                st.metric("is_prime", f"{summary['prime_count']} ({summary['prime_pct']:.2f}%)")
                st.metric("is_square", f"{summary['square_count']} ({summary['square_pct']:.2f}%)")
                st.write("Residue histogram")
                st.dataframe(summary["residue_histogram"], use_container_width=True)
                st.write("Top identities")
                st.dataframe(summary["top_identities"], use_container_width=True)
                st.code(format_expanded_stats_report(summary))


if __name__ == "__main__":
    main()
