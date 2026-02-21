import json
from pathlib import Path

from typer.testing import CliRunner

from strausforge.cert import from_jsonl
from strausforge.cli import app
from strausforge.loop import run_loop

runner = CliRunner()


def _write_seed_identity(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "conditions": [],
                "modulus": 4,
                "name": "seed_mod4_0",
                "notes": "seed",
                "residues": [0],
                "x_form": "n/2",
                "y_form": "n",
                "z_form": "n",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_loop_returns_structured_report(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    _write_seed_identity(identity_file)

    result = run_loop(
        identity_path=identity_file,
        modulus=12,
        max_targets=2,
        max_per_target=3,
        max_new_identities=5,
    )

    assert set(result) == {
        "before",
        "after",
        "targets_used",
        "n_tested",
        "certs_written",
        "identities_added",
        "added_identity_names",
    }
    assert result["targets_used"] <= 2
    assert result["n_tested"] <= 6

    certs_written = Path(result["certs_written"])
    assert certs_written == Path("data") / "certs_targets_m12.jsonl"
    assert certs_written.exists()
    cert_lines = [
        line for line in certs_written.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert cert_lines
    certs = [from_jsonl(line) for line in cert_lines]
    assert all(cert.verified for cert in certs)

    identities_after = [
        line for line in identity_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(identities_after) >= 1


def test_loop_cli_runs_and_reports(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    _write_seed_identity(identity_file)

    result = runner.invoke(
        app,
        [
            "loop",
            "--identity",
            str(identity_file),
            "--modulus",
            "12",
            "--max-targets",
            "2",
            "--max-per-target",
            "3",
            "--max-new-identities",
            "5",
        ],
    )

    assert result.exit_code in {0, 1}
    assert "before: covered=" in result.stdout
    assert "run plan:" in result.stdout
    assert "after: covered=" in result.stdout
    assert "delta:" in result.stdout
    assert "identities_added=" in result.stdout

    certs_path = Path("data") / "certs_targets_m12.jsonl"
    assert certs_path.exists()
    lines = [line for line in certs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    certs = [from_jsonl(line) for line in lines]
    assert all(cert.verified for cert in certs)
