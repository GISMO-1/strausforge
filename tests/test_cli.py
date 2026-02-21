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
