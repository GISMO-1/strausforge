from pathlib import Path

from typer.testing import CliRunner

from strausforge.cli import app
from strausforge.coverage import coverage_report
from strausforge.fit import fit_identities
from strausforge.identities import identity_from_jsonl

runner = CliRunner()


def test_fit_cli_runs_on_fixture(tmp_path: Path) -> None:
    out_file = tmp_path / "identities_fit.jsonl"
    result = runner.invoke(
        app,
        [
            "fit",
            "--in",
            "tests/fixtures/hard_48_r1_r25_small.jsonl",
            "--modulus",
            "48",
            "--residue",
            "1",
            "--out",
            str(out_file),
            "--max-identities",
            "10",
        ],
    )
    assert result.exit_code in {0, 1}
    assert "summary: identities_found=" in result.stdout
    assert out_file.exists()


def test_fit_identities_deterministic_for_fixture(tmp_path: Path) -> None:
    out_a = tmp_path / "fit_a.jsonl"
    out_b = tmp_path / "fit_b.jsonl"
    ids_a = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_a,
        modulus=48,
        residue=25,
        max_identities=5,
    )
    ids_b = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_b,
        modulus=48,
        residue=25,
        max_identities=5,
    )
    assert [identity.name for identity in ids_a] == [identity.name for identity in ids_b]
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")


def test_fit_regression_targets_shrink_when_identities_found(tmp_path: Path) -> None:
    base_lines = Path("data/identities.jsonl").read_text(encoding="utf-8").splitlines()
    baseline = [identity_from_jsonl(line) for line in base_lines if line.strip()]
    before = coverage_report(baseline, modulus=48)
    assert before["uncovered_residues"] == [1, 25]

    out_file = tmp_path / "fit.jsonl"
    fitted = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_file,
        modulus=48,
        residue=1,
        max_identities=10,
    )

    if not fitted:
        return

    after = coverage_report(baseline + fitted, modulus=48)
    assert len(after["uncovered_residues"]) < len(before["uncovered_residues"])
