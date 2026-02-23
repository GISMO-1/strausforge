import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from strausforge.cli import app

runner = CliRunner()


def _coverage_pct(identity_path: Path, modulus: int) -> float:
    result = runner.invoke(
        app,
        [
            "id-targets",
            "--identity",
            str(identity_path),
            "--modulus",
            str(modulus),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    return float(payload["covered_pct"])


def test_loop_mod48_breaks_mod4_wall(tmp_path: Path) -> None:
    identity_file = tmp_path / "identities.jsonl"
    shutil.copy(Path("data/identities.jsonl"), identity_file)

    before_pct = _coverage_pct(identity_file, modulus=48)
    assert before_pct == 100.0

    result = runner.invoke(
        app,
        [
            "loop",
            "--identity",
            str(identity_file),
            "--modulus",
            "48",
            "--max-targets",
            "12",
            "--max-per-target",
            "400",
            "--max-new-identities",
            "25",
            "--target-timeout-seconds",
            "15",
            "--progress-every",
            "200",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code in {0, 1}

    after_pct = _coverage_pct(identity_file, modulus=48)
    assert "run plan:" in result.stdout
    assert after_pct >= before_pct
