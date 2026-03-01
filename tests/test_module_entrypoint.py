from __future__ import annotations

import subprocess
import sys


def test_python_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "strausforge", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Usage:" in completed.stdout


def test_python_module_preserves_nonzero_exit_codes() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "strausforge",
            "check",
            "--n",
            "5",
            "--x",
            "2",
            "--y",
            "5",
            "--z",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "FAIL" in completed.stdout
