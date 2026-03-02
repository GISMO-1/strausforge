from __future__ import annotations

import json
from pathlib import Path

from strausforge.factor_meta import (
    semiprime_kind_from_spf,
    smallest_prime_factor_bounded,
    write_jsonl_record,
)
from strausforge.hardness_core import load_identities, run_hardness


def test_smallest_prime_factor_bounded_cases() -> None:
    assert smallest_prime_factor_bounded(101, 200) == 0
    assert smallest_prime_factor_bounded(221, 200) == 13
    assert smallest_prime_factor_bounded(10403, 100) == 0


def test_semiprime_classification_cases() -> None:
    cofactor_pq, kind_pq = semiprime_kind_from_spf(221, 13)
    assert cofactor_pq == 17
    assert kind_pq == "p*q"

    cofactor_p2, kind_p2 = semiprime_kind_from_spf(169, 13)
    assert cofactor_p2 == 13
    assert kind_p2 == "p^2"

    cofactor_other, kind_other = semiprime_kind_from_spf(144, 2)
    assert cofactor_other == 72
    assert kind_other == ""


def test_write_jsonl_record_outputs_one_object_per_line(tmp_path: Path) -> None:
    out_path = tmp_path / "meta.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        write_jsonl_record(handle, {"n": 1, "spf": 0, "semiprime_kind": ""})
        write_jsonl_record(handle, {"n": 9, "spf": 3, "semiprime_kind": "p^2"})

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(line.startswith("{") and line.endswith("}") for line in lines)
    assert all(not line.startswith("[") and not line.endswith("]") for line in lines)
    assert json.loads(lines[0])["n"] == 1
    assert json.loads(lines[1])["n"] == 9


def test_run_hardness_exports_expanded_meta_jsonl(tmp_path: Path) -> None:
    identities = load_identities(Path("data/identities.jsonl"))
    meta_path = tmp_path / "expanded_meta.jsonl"

    _rows, summary = run_hardness(
        identities=identities,
        n_min=35000,
        n_max=35200,
        bin_size=100,
        proc_heuristic="off",
        only_proc=True,
        export_expanded_meta=meta_path,
        expanded_factor_bound=20000,
    )

    lines = [line for line in meta_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == int(summary["expanded_total"])

    if not lines:
        return

    parsed = [json.loads(line) for line in lines]
    assert [int(item["n"]) for item in parsed] == sorted(int(item["n"]) for item in parsed)

    sample = parsed[0]
    assert set(sample.keys()) == {
        "n",
        "res48",
        "identity",
        "t_used",
        "window_used",
        "proc_heuristic",
        "spf",
        "cofactor",
        "semiprime_kind",
    }
    assert int(sample["res48"]) == int(sample["n"]) % 48
