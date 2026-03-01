from __future__ import annotations

from pathlib import Path

import pytest

from strausforge.hardness_core import (
    HARDNESS_COLUMNS,
    format_expanded_stats_report,
    load_identities,
    run_hardness,
    summarize_expanded_jsonl,
)


def test_run_hardness_matches_cli_like_expectations(tmp_path: Path) -> None:
    identities = load_identities(Path("data/identities.jsonl"))
    expanded_path = tmp_path / "expanded.jsonl"
    progress_events: list[tuple[int, int]] = []

    rows, summary = run_hardness(
        identities=identities,
        n_min=35000,
        n_max=35500,
        bin_size=250,
        proc_heuristic="off",
        only_proc=True,
        export_expanded=expanded_path,
        progress_callback=lambda completed, total: progress_events.append((completed, total)),
    )

    assert rows
    assert set(rows[0].keys()) == set(HARDNESS_COLUMNS)
    assert int(summary["bins"]) == len(rows)
    assert progress_events[-1] == (501, 501)
    expanded_lines = [
        line for line in expanded_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(expanded_lines) == int(summary["expanded_total"])


def test_run_hardness_is_deterministic_for_csv_and_jsonl(tmp_path: Path) -> None:
    identities = load_identities(Path("data/identities.jsonl"))
    expanded_a = tmp_path / "expanded_a.jsonl"
    expanded_b = tmp_path / "expanded_b.jsonl"

    rows_a, summary_a = run_hardness(
        identities=identities,
        n_min=35000,
        n_max=35200,
        bin_size=100,
        proc_heuristic="off",
        only_proc=True,
        export_expanded=expanded_a,
    )
    rows_b, summary_b = run_hardness(
        identities=identities,
        n_min=35000,
        n_max=35200,
        bin_size=100,
        proc_heuristic="off",
        only_proc=True,
        export_expanded=expanded_b,
    )

    assert rows_a == rows_b
    assert summary_a == summary_b
    assert expanded_a.read_text(encoding="utf-8") == expanded_b.read_text(encoding="utf-8")


def test_summarize_expanded_jsonl_and_format_report() -> None:
    fixture_path = Path("tests/fixtures/expanded_small.jsonl")
    summary = summarize_expanded_jsonl(fixture_path, mod=48, top=2)

    assert summary["total_expanded_records"] == 4
    assert summary["prime_count"] == 1
    assert summary["square_count"] == 1
    assert summary["residue_histogram"] == [
        {"residue": 1, "count": 2},
        {"residue": 2, "count": 1},
        {"residue": 16, "count": 1},
    ]
    assert summary["top_identities"] == [
        {"identity": "fit_proc_m48_r1", "count": 2},
        {"identity": "fit_proc_m48_r25", "count": 2},
    ]

    report = format_expanded_stats_report(summary)
    assert "total_expanded_records: 4" in report
    assert "residue=16: count=1" in report
    assert "identity=fit_proc_m48_r25: count=2" in report


def test_summarize_expanded_jsonl_rejects_invalid_parameters() -> None:
    fixture_path = Path("tests/fixtures/expanded_small.jsonl")

    with pytest.raises(ValueError, match="Expected mod > 0"):
        summarize_expanded_jsonl(fixture_path, mod=0, top=20)
    with pytest.raises(ValueError, match="Expected top > 0"):
        summarize_expanded_jsonl(fixture_path, mod=48, top=0)
