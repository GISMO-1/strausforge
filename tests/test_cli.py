import json
import re
from csv import DictReader
from pathlib import Path

from typer.testing import CliRunner

from strausforge.cert import from_jsonl
from strausforge.cli import app

runner = CliRunner()

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _count_residue_hits(n_min: int, n_max: int, modulus: int, residue: int) -> int:
    values = [n for n in range(n_min, n_max + 1) if n % modulus == residue]
    return len(values)


def test_check_command_pass() -> None:
    result = runner.invoke(app, ["check", "--n", "5", "--x", "2", "--y", "4", "--z", "20"])
    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_check_command_fail() -> None:
    result = runner.invoke(app, ["check", "--n", "5", "--x", "2", "--y", "5", "--z", "20"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout
    assert "Difference:" in result.stdout


def test_search_single_json() -> None:
    result = runner.invoke(app, ["search", "--n", "5", "--json"])
    assert result.exit_code == 0
    assert '"n": 5' in result.stdout
    assert '"found": true' in result.stdout


def test_search_range_text() -> None:
    result = runner.invoke(app, ["search", "--start", "2", "--end", "4"])
    assert result.exit_code == 0
    assert "n=2:" in result.stdout
    assert "n=3:" in result.stdout
    assert "n=4:" in result.stdout


def test_certify_generates_parseable_jsonl(tmp_path: Path) -> None:
    out_file = tmp_path / "certs.jsonl"
    result = runner.invoke(
        app,
        ["certify", "--start", "2", "--end", "30", "--out", str(out_file)],
    )
    assert result.exit_code == 0
    assert "summary:" in result.stdout

    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 29

    certs = [from_jsonl(line) for line in lines]
    assert all(cert.n >= 2 for cert in certs)
    assert all("n_mod_24" in cert.residue for cert in certs)


def test_stats_reads_certificates(tmp_path: Path) -> None:
    out_file = tmp_path / "certs.jsonl"
    runner.invoke(
        app,
        ["certify", "--start", "2", "--end", "12", "--out", str(out_file)],
        catch_exceptions=False,
    )

    result = runner.invoke(app, ["stats", "--in", str(out_file)])
    assert result.exit_code == 0
    assert "coverage n_mod_4:" in result.stdout
    assert "top 10 slowest n values:" in result.stdout


def test_mine_and_identity_commands(tmp_path: Path) -> None:
    certs_file = tmp_path / "certs.jsonl"
    identities_file = tmp_path / "identities.jsonl"

    certify_result = runner.invoke(
        app,
        ["certify", "--start", "2", "--end", "120", "--out", str(certs_file)],
    )
    assert certify_result.exit_code == 0

    mine_result = runner.invoke(
        app,
        [
            "mine",
            "--in",
            str(certs_file),
            "--out",
            str(identities_file),
            "--max-identities",
            "10",
        ],
    )
    assert mine_result.exit_code == 0
    assert "identities_found=" in mine_result.stdout

    id_check_result = runner.invoke(
        app,
        ["id-check", "--identity", str(identities_file), "--n", "8"],
    )
    assert id_check_result.exit_code == 0
    assert "identity=" in id_check_result.stdout

    id_verify_result = runner.invoke(
        app,
        [
            "id-verify",
            "--identity",
            str(identities_file),
            "--n-min",
            "2",
            "--n-max",
            "100",
        ],
    )
    assert id_verify_result.exit_code == 0
    assert "tested=" in id_verify_result.stdout


def test_id_targets_command_text_and_json(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    identity_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "conditions": [],
                        "modulus": 2,
                        "name": "seed_even",
                        "notes": "",
                        "residues": [0],
                        "x_form": "n/2",
                        "y_form": "n",
                        "z_form": "n",
                    }
                ),
                json.dumps(
                    {
                        "conditions": [],
                        "modulus": 4,
                        "name": "seed_mod4_3",
                        "notes": "",
                        "residues": [3],
                        "x_form": "(n+1)/4",
                        "y_form": "n*(n+1)/2",
                        "z_form": "n*(n+1)/2",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    text_result = runner.invoke(
        app,
        ["id-targets", "--identity", str(identity_file), "--modulus", "8"],
    )
    assert text_result.exit_code == 0
    assert "covered=6/8 (75.00%)" in text_result.stdout
    assert "uncovered residues: [1, 5]" in text_result.stdout

    json_result = runner.invoke(
        app,
        ["id-targets", "--identity", str(identity_file), "--modulus", "8", "--json"],
    )
    assert json_result.exit_code == 0
    assert '"covered_count": 6' in json_result.stdout
    assert '"uncovered_residues": [1, 5]' in json_result.stdout


def test_id_targets_rejects_non_positive_modulus(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    identity_file.write_text("", encoding="utf-8")

    result = runner.invoke(
        app,
        ["id-targets", "--identity", str(identity_file), "--modulus", "0"],
    )
    assert result.exit_code != 0
    assert "Expected --modulus > 0." in _strip_ansi(result.output)


def test_id_check_regression_values_for_procedural_identities() -> None:
    regression_values = [18481, 35809, 58921, 87481, 99961]
    for n_value in regression_values:
        result = runner.invoke(
            app,
            ["id-check", "--identity", "data/identities.jsonl", "--n", str(n_value)],
        )
        assert result.exit_code == 0
        assert f"n={n_value}" in result.stdout


def test_profile_command_reports_deterministic_hardest_order() -> None:
    result = runner.invoke(
        app,
        [
            "profile",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "2",
            "--n-max",
            "50000",
            "--top",
            "25",
        ],
    )
    assert result.exit_code == 0
    assert "identity profile summary:" in result.stdout
    assert "identity=fit_proc_m48_r1" in result.stdout
    assert "identity=fit_proc_m48_r25" in result.stdout

    cleaned = _strip_ansi(result.stdout)
    r1_line = next(line for line in cleaned.splitlines() if "identity=fit_proc_m48_r1," in line)
    r25_line = next(line for line in cleaned.splitlines() if "identity=fit_proc_m48_r25," in line)

    expected_r1_total = _count_residue_hits(2, 50000, 48, 1)
    expected_r25_total = _count_residue_hits(2, 50000, 48, 25)
    assert f"total={expected_r1_total}" in r1_line
    assert f"total={expected_r25_total}" in r25_line
    assert "fast=" in r1_line and "fast=0" not in r1_line
    assert "fast=" in r25_line and "fast=0" not in r25_line

    hardest_lines = [
        line
        for line in cleaned.splitlines()
        if line.startswith("identity=") and "path=" in line and "window_used=" in line
    ]
    sorted_hardest = sorted(
        hardest_lines,
        key=lambda line: (
            0 if "path=expanded" in line else 1,
            int(line.split("window_used=")[1].split(",")[0]),
            int(line.split("t_used=")[1]),
            int(line.split("n=")[1].split(",")[0]),
        ),
    )
    assert hardest_lines == sorted_hardest


def test_id_check_proc_heuristic_off_matches_default_output() -> None:
    args = ["id-check", "--identity", "data/identities.jsonl", "--n", "35809"]
    baseline = runner.invoke(app, args)
    explicit_off = runner.invoke(app, args + ["--proc-heuristic", "off"])

    assert baseline.exit_code == 0
    assert explicit_off.exit_code == 0
    assert baseline.stdout == explicit_off.stdout


def test_hardness_exports_csv_with_expected_columns(tmp_path: Path) -> None:
    out_file = tmp_path / "hardness.csv"
    result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "35000",
            "--n-max",
            "36000",
            "--bin-size",
            "500",
            "--only-proc",
            "--out",
            str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert out_file.exists()

    with out_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(DictReader(handle))

    assert rows
    expected_columns = {
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
    }
    assert set(rows[0].keys()) == expected_columns

    for row in rows:
        total = int(row["total"])
        fast = int(row["fast"])
        escalated = int(row["escalated"])
        expanded_exported = int(row["expanded_exported"])
        solver_fallback = int(row["solver_fallback"])
        assert total == fast + escalated + solver_fallback
        assert expanded_exported <= escalated


def test_hardness_prime_or_square_heuristic_reduces_expanded_rate(tmp_path: Path) -> None:
    off_file = tmp_path / "hardness_off.csv"
    posw_file = tmp_path / "hardness_posw.csv"

    off_result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "35000",
            "--n-max",
            "36000",
            "--bin-size",
            "500",
            "--only-proc",
            "--proc-heuristic",
            "off",
            "--out",
            str(off_file),
        ],
    )
    posw_result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "35000",
            "--n-max",
            "36000",
            "--bin-size",
            "500",
            "--only-proc",
            "--proc-heuristic",
            "prime-or-square-window",
            "--out",
            str(posw_file),
        ],
    )

    assert off_result.exit_code == 0
    assert posw_result.exit_code == 0

    with off_file.open("r", encoding="utf-8", newline="") as handle:
        off_rows = list(DictReader(handle))
    with posw_file.open("r", encoding="utf-8", newline="") as handle:
        posw_rows = list(DictReader(handle))

    assert len(off_rows) == len(posw_rows)
    off_escalated = sum(int(row["escalated"]) for row in off_rows)
    posw_escalated = sum(int(row["escalated"]) for row in posw_rows)
    assert off_escalated > 0
    assert posw_escalated <= off_escalated

    off_total = sum(int(row["total"]) for row in off_rows)
    posw_total = sum(int(row["total"]) for row in posw_rows)
    off_rate = off_escalated / off_total
    posw_rate = posw_escalated / posw_total
    assert posw_rate <= off_rate


def test_hardness_export_expanded_stream_contains_only_expanded_rows(tmp_path: Path) -> None:
    out_file = tmp_path / "hardness.csv"
    expanded_file = tmp_path / "expanded.jsonl"
    result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "35000",
            "--n-max",
            "36000",
            "--bin-size",
            "500",
            "--only-proc",
            "--proc-heuristic",
            "off",
            "--out",
            str(out_file),
            "--export-expanded",
            str(expanded_file),
        ],
    )

    assert result.exit_code == 0
    assert expanded_file.exists()

    rows = [
        json.loads(line)
        for line in expanded_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    required_keys = {
        "n",
        "identity",
        "path",
        "t_used",
        "window_used",
        "is_prime",
        "is_square",
        "proc_heuristic",
    }

    for row in rows:
        assert set(row.keys()) == required_keys
        assert row["path"] == "expanded"
        assert row["proc_heuristic"] == "off"


def test_hardness_export_expanded_count_matches_bin_totals(tmp_path: Path) -> None:
    out_file = tmp_path / "hardness.csv"
    expanded_file = tmp_path / "expanded.jsonl"
    result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "35000",
            "--n-max",
            "36000",
            "--bin-size",
            "500",
            "--only-proc",
            "--proc-heuristic",
            "off",
            "--out",
            str(out_file),
            "--export-expanded",
            str(expanded_file),
        ],
    )

    assert result.exit_code == 0

    with out_file.open("r", encoding="utf-8", newline="") as handle:
        hardness_rows = list(DictReader(handle))
    expanded_lines = [
        line for line in expanded_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    expanded_exported_total = sum(int(row["expanded_exported"]) for row in hardness_rows)
    assert len(expanded_lines) == expanded_exported_total




def test_hardness_export_expanded_reports_empty_file_when_no_records(tmp_path: Path) -> None:
    out_file = tmp_path / "hardness.csv"
    expanded_file = tmp_path / "expanded.jsonl"
    result = runner.invoke(
        app,
        [
            "hardness",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "2",
            "--n-max",
            "5000",
            "--bin-size",
            "500",
            "--only-proc",
            "--proc-heuristic",
            "prime-or-square-window",
            "--out",
            str(out_file),
            "--export-expanded",
            str(expanded_file),
        ],
    )

    assert result.exit_code == 0
    assert expanded_file.exists()
    assert expanded_file.stat().st_size == 0
    assert "export-expanded: 0 records emitted (file empty)" in result.stdout

    with out_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(DictReader(handle))

    assert rows
    assert sum(int(row["expanded_exported"]) for row in rows) == 0

def test_hardness_export_expanded_is_deterministic_across_runs(tmp_path: Path) -> None:
    out_file_a = tmp_path / "hardness_a.csv"
    out_file_b = tmp_path / "hardness_b.csv"
    expanded_file_a = tmp_path / "expanded_a.jsonl"
    expanded_file_b = tmp_path / "expanded_b.jsonl"

    args = [
        "hardness",
        "--identity",
        "data/identities.jsonl",
        "--n-min",
        "35000",
        "--n-max",
        "36000",
        "--bin-size",
        "500",
        "--only-proc",
        "--proc-heuristic",
        "off",
    ]
    result_a = runner.invoke(
        app,
        args + ["--out", str(out_file_a), "--export-expanded", str(expanded_file_a)],
    )
    result_b = runner.invoke(
        app,
        args + ["--out", str(out_file_b), "--export-expanded", str(expanded_file_b)],
    )

    assert result_a.exit_code == 0
    assert result_b.exit_code == 0
    assert expanded_file_a.read_text(encoding="utf-8") == expanded_file_b.read_text(
        encoding="utf-8"
    )


def test_profile_proc_heuristic_prime_window_reduces_expanded_count() -> None:
    common = [
        "profile",
        "--identity",
        "data/identities.jsonl",
        "--n-min",
        "35700",
        "--n-max",
        "35900",
        "--top",
        "10",
    ]
    off_result = runner.invoke(app, common + ["--proc-heuristic", "off"])
    prime_result = runner.invoke(app, common + ["--proc-heuristic", "prime-window"])

    assert off_result.exit_code == 0
    assert prime_result.exit_code == 0

    off_clean = _strip_ansi(off_result.stdout)
    prime_clean = _strip_ansi(prime_result.stdout)

    off_line = next(line for line in off_clean.splitlines() if "identity=fit_proc_m48_r1," in line)
    prime_line = next(
        line for line in prime_clean.splitlines() if "identity=fit_proc_m48_r1," in line
    )

    off_expanded = int(off_line.split("expanded=")[1].split(" ")[0])
    prime_expanded = int(prime_line.split("expanded=")[1].split(" ")[0])

    assert "expanded_primes=" in off_clean
    assert "expanded_primes=" in prime_clean
    assert "expanded_squares=" in off_clean
    assert "expanded_squares=" in prime_clean
    assert prime_expanded < off_expanded


def test_profile_proc_heuristic_prime_or_square_window_handles_prime_square_case() -> None:
    common = [
        "profile",
        "--identity",
        "data/identities.jsonl",
        "--n-min",
        "994009",
        "--n-max",
        "994009",
        "--top",
        "10",
    ]

    off_result = runner.invoke(app, common + ["--proc-heuristic", "off"])
    heuristic_result = runner.invoke(app, common + ["--proc-heuristic", "prime-or-square-window"])

    assert off_result.exit_code == 0
    assert heuristic_result.exit_code == 0

    off_clean = _strip_ansi(off_result.stdout)
    heuristic_clean = _strip_ansi(heuristic_result.stdout)

    off_line = next(line for line in off_clean.splitlines() if "identity=fit_proc_m48_r25," in line)
    heuristic_line = next(
        line for line in heuristic_clean.splitlines() if "identity=fit_proc_m48_r25," in line
    )

    assert "fast=0" in off_line
    assert "expanded=1" in off_line
    assert "expanded_squares=1/1" in off_clean

    assert "fast=1" in heuristic_line
    assert "expanded=0" in heuristic_line
    assert "expanded_squares=0/0" in heuristic_clean


def test_hardness_progress_flag_preserves_csv_and_expanded_outputs(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "hardness_baseline.csv"
    baseline_expanded = tmp_path / "expanded_baseline.jsonl"
    progress_csv = tmp_path / "hardness_progress.csv"
    progress_expanded = tmp_path / "expanded_progress.jsonl"

    common_args = [
        "hardness",
        "--identity",
        "data/identities.jsonl",
        "--n-min",
        "35000",
        "--n-max",
        "35500",
        "--bin-size",
        "250",
        "--only-proc",
        "--proc-heuristic",
        "off",
    ]

    baseline_result = runner.invoke(
        app,
        common_args + ["--out", str(baseline_csv), "--export-expanded", str(baseline_expanded)],
    )
    progress_result = runner.invoke(
        app,
        common_args
        + [
            "--out",
            str(progress_csv),
            "--export-expanded",
            str(progress_expanded),
            "--progress",
        ],
    )

    assert baseline_result.exit_code == 0
    assert progress_result.exit_code == 0
    assert baseline_csv.read_text(encoding="utf-8") == progress_csv.read_text(encoding="utf-8")
    assert baseline_expanded.read_text(encoding="utf-8") == progress_expanded.read_text(
        encoding="utf-8"
    )


def test_profile_progress_flag_succeeds() -> None:
    result = runner.invoke(
        app,
        [
            "profile",
            "--identity",
            "data/identities.jsonl",
            "--n-min",
            "2",
            "--n-max",
            "500",
            "--top",
            "5",
            "--progress",
        ],
    )
    assert result.exit_code == 0
    assert "identity profile summary:" in result.stdout


def test_expanded_stats_reports_expected_counts(tmp_path: Path) -> None:
    fixture_path = Path("tests/fixtures/expanded_small.jsonl")
    out_path = tmp_path / "expanded_stats.txt"

    result = runner.invoke(
        app,
        [
            "expanded-stats",
            "--in",
            str(fixture_path),
            "--out",
            str(out_path),
            "--mod",
            "48",
            "--top",
            "2",
        ],
    )

    assert result.exit_code == 0
    report = out_path.read_text(encoding="utf-8")
    assert "total_expanded_records: 4" in report
    assert "is_prime: 1 (25.00%)" in report
    assert "is_square: 1 (25.00%)" in report
    assert "residue=1: count=2" in report
    assert "residue=2: count=1" in report
    assert "residue=16: count=1" in report
    assert "residue=49: count=1" not in report
    assert "identity=fit_proc_m48_r1: count=2" in report
    assert "identity=fit_proc_m48_r25: count=2" in report


def test_expanded_stats_stdout_is_deterministic() -> None:
    fixture_path = Path("tests/fixtures/expanded_small.jsonl")
    args = ["expanded-stats", "--in", str(fixture_path), "--mod", "48", "--top", "20"]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.stdout == second.stdout


def test_expanded_stats_rejects_invalid_parameters() -> None:
    fixture_path = Path("tests/fixtures/expanded_small.jsonl")

    bad_mod = runner.invoke(app, ["expanded-stats", "--in", str(fixture_path), "--mod", "0"])
    bad_top = runner.invoke(app, ["expanded-stats", "--in", str(fixture_path), "--top", "0"])

    assert bad_mod.exit_code != 0
    assert "Expected --mod > 0." in _strip_ansi(bad_mod.output)
    assert bad_top.exit_code != 0
    assert "Expected --top > 0." in _strip_ansi(bad_top.output)
