from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from strausforge import cli

runner = CliRunner()


def test_gui_command_registered() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "gui" in result.stdout


def test_gui_command_launches_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    class DummyResult:
        returncode = 0

    def fake_run(command: list[str], check: bool) -> DummyResult:
        captured["command"] = command
        assert check is False
        return DummyResult()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    identity_path = Path("data/identities.jsonl")
    result = runner.invoke(cli.app, ["gui", "--identity", str(identity_path)])

    assert result.exit_code == 0
    command = captured["command"]
    assert command[0].endswith("python") or "python" in Path(command[0]).name.lower()
    assert command[1:4] == ["-m", "streamlit", "run"]
    assert command[-3:] == ["--", "--identity", str(identity_path)]


def test_gui_module_imports_when_streamlit_installed() -> None:
    pytest.importorskip("streamlit")
    module = __import__("strausforge.gui_app", fromlist=["main"])
    assert hasattr(module, "main")
