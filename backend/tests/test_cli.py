import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_code_review.cli.app import app

runner = CliRunner()
FIXTURE = str(Path(__file__).parent / "fixtures" / "unsafe.py")


@pytest.mark.parametrize(
    "args,expected",
    [
        (["version"], "0.1.0"),
        (["doctor"], "Tree-Sitter python: ready"),
        (["config", "show"], '"provider": "none"'),
        (["--help"], "review"),
    ],
)
def test_basic_commands(args, expected):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_json_stdout_clean_and_gate():
    result = runner.invoke(app, ["review", FIXTURE, "--no-ai", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["summary"]["findings_count"] >= 5
    assert not result.stderr
    gated = runner.invoke(app, ["review", FIXTURE, "--format", "json", "--fail-on", "high"])
    assert gated.exit_code == 1
    json.loads(gated.stdout)


def test_text_markdown_severity_filter():
    result = runner.invoke(app, ["review", FIXTURE, "--severity", "high"])
    assert result.exit_code == 0, result.output
    assert "Dynamic code evaluation" in result.output
    assert "Mutable default argument" not in result.output
    result = runner.invoke(app, ["review", FIXTURE, "--format", "markdown"])
    assert result.exit_code == 0
    assert "## Scoring" in result.output
    assert "Evidence:" in result.output


def test_saved_report_explain_and_no_overwrite(tmp_path):
    report = tmp_path / "report.json"
    result = runner.invoke(app, ["review", FIXTURE, "--format", "json", "--output", str(report)])
    assert result.exit_code == 0, result.output
    assert not result.stdout
    saved = report.read_text()
    finding_id = json.loads(saved)["findings"][0]["id"]
    explained = runner.invoke(app, ["explain", finding_id, "--report", str(report)])
    assert explained.exit_code == 0
    assert json.loads(explained.stdout)["scoring"]["points"] > 0
    result = runner.invoke(app, ["review", FIXTURE, "--output", str(report)])
    assert result.exit_code == 2
    assert report.read_text() == saved
    assert runner.invoke(app, ["explain", "missing", "--report", str(report)]).exit_code == 2


@pytest.mark.parametrize(
    "args",
    [
        ["review", "not-existing.py"],
        ["review", FIXTURE, "--staged", "--diff", "HEAD"],
        ["review", FIXTURE, "--severity", "urgent"],
        ["review", FIXTURE, "--severity", "high", "--format", "json"],
    ],
)
def test_cli_errors(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 2


def test_source_cannot_be_overwritten_by_report(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("eval(value)\n")
    result = runner.invoke(app, ["review", str(path), "--output", str(path)])
    assert result.exit_code == 2
    assert path.read_text() == "eval(value)\n"


def test_no_ai_overrides_incomplete_provider_settings(monkeypatch):
    monkeypatch.setenv("AICR_PROVIDER", "ollama")
    monkeypatch.setenv("AICR_MODEL", "")
    result = runner.invoke(app, ["review", FIXTURE, "--no-ai", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ai_status"] == "disabled"
