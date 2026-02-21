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
