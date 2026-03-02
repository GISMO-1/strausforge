from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path("tools/sample_semiprime_rate.py")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_uses_default_residues() -> None:
    result = _run("--n-min", "1", "--n-max", "1000", "--step", "97")
    assert result.returncode == 0
    assert "sampled_candidates:" in result.stdout
    assert "semiprime_rate:" in result.stdout


def test_cli_accepts_residue_override() -> None:
    default_result = _run("--n-min", "1", "--n-max", "500", "--step", "1")
    override_result = _run(
        "--n-min",
        "1",
        "--n-max",
        "500",
        "--step",
        "1",
        "--residues",
        "1",
    )

    assert default_result.returncode == 0
    assert override_result.returncode == 0
    assert default_result.stdout != override_result.stdout


def test_cli_rejects_empty_residue_list() -> None:
    result = _run(
        "--n-min",
        "1",
        "--n-max",
        "100",
        "--step",
        "1",
        "--residues",
        ",",
    )
    assert result.returncode != 0
    assert "At least one residue is required" in result.stderr
