import json
from pathlib import Path

from typer.testing import CliRunner

from strausforge.cert import from_jsonl
from strausforge.cli import app

runner = CliRunner()


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
    assert "Expected --modulus > 0." in result.output
