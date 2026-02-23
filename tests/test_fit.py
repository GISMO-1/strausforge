from pathlib import Path

from typer.testing import CliRunner

from strausforge.cli import app
from strausforge.coverage import coverage_report
from strausforge.fit import fit_identities
from strausforge.identities import Identity, eval_identity, identity_from_jsonl

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
            "--strategy",
            "procedural",
            "--max-identities",
            "10",
        ],
    )
    assert result.exit_code == 0
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
        strategy="procedural",
    )
    ids_b = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_b,
        modulus=48,
        residue=25,
        max_identities=5,
        strategy="procedural",
    )
    assert [identity.name for identity in ids_a] == [identity.name for identity in ids_b]
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")


def _procedural_identity(residue: int) -> Identity:
    return Identity(
        name=f"fit_proc_m48_r{residue}",
        modulus=48,
        residues=[residue],
        x_form="proc_x",
        y_form="proc_y",
        z_form="proc_z",
        conditions=[],
        kind="procedural",
        procedural_params={"anchor": "(n+5)//4", "window": 8, "t_max": 256},
        notes="fit; procedural; empirical",
    )


def test_procedural_identity_residue_1_examples() -> None:
    identity = _procedural_identity(1)
    for n_value in [49, 97, 145, 193, 241]:
        triple = eval_identity(identity, n_value)
        assert triple is not None


def test_procedural_identity_residue_25_examples() -> None:
    identity = _procedural_identity(25)
    for n_value in [25, 73, 121, 169, 217]:
        triple = eval_identity(identity, n_value)
        assert triple is not None


def test_fit_regression_targets_shrink_when_identities_found(tmp_path: Path) -> None:
    base_lines = Path("data/identities.jsonl").read_text(encoding="utf-8").splitlines()
    baseline = [identity_from_jsonl(line) for line in base_lines if line.strip()]
    before = coverage_report(baseline, modulus=48)

    out_r1 = tmp_path / "fit_r1.jsonl"
    out_r25 = tmp_path / "fit_r25.jsonl"
    fitted_r1 = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_r1,
        modulus=48,
        residue=1,
        max_identities=10,
        strategy="procedural",
    )
    fitted_r25 = fit_identities(
        in_file=Path("tests/fixtures/hard_48_r1_r25_small.jsonl"),
        out_file=out_r25,
        modulus=48,
        residue=25,
        max_identities=10,
        strategy="procedural",
    )

    assert fitted_r1 and fitted_r25
    after = coverage_report(baseline + fitted_r1 + fitted_r25, modulus=48)
    assert len(after["uncovered_residues"]) <= len(before["uncovered_residues"])
    assert 1 not in after["uncovered_residues"]
    assert 25 not in after["uncovered_residues"]
