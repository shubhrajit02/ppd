from pathlib import Path

import pytest

from ai_code_review.analysis.ast import parse
from ai_code_review.core.models import FileChange, ReviewReport, ReviewRequest
from ai_code_review.review.engine import ReviewEngine

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_python_rules_and_serialization():
    report = ReviewEngine().review(ReviewRequest(path=FIXTURES / "unsafe.py"))
    rules = {f.rule_id for f in report.findings}
    assert {
        "shell-true",
        "dynamic-eval",
        "mutable-default",
        "division-by-zero",
        "nested-loop",
        "missing-docstring",
    } <= rules
    assert all(f.evidence and f.id for f in report.findings)
    docstring_finding = next(f for f in report.findings if f.rule_id == "missing-docstring")
    assert docstring_finding.title == "Add a description to this public function"
    assert "what it does" in docstring_finding.description
    assert ReviewReport.model_validate_json(report.model_dump_json()) == report
    assert report.ai_status == "disabled"


@pytest.mark.parametrize(
    "language,source",
    [
        ("python", "def f():\n    return 1\n"),
        ("javascript", "function f() { return 1; }"),
        ("typescript", "function f(): number { return 1; }"),
        ("tsx", "function f() { return <div/>; }"),
    ],
)
def test_real_grammars(language, source):
    context, tree = parse(FileChange(path="file", language=language, content=source))
    assert not tree.root_node.has_error
    assert not context.error_lines
    assert context.symbols[0].name == "f"


def test_js_ts_rules_ignore_comments_and_strings(tmp_path):
    path = tmp_path / "test.ts"
    path.write_text('// eval(value)\nconst s = "eval(value)";\n')
    assert not ReviewEngine().review(ReviewRequest(path=path)).findings
    report = ReviewEngine().review(ReviewRequest(path=FIXTURES / "unsafe.ts"))
    assert {f.rule_id for f in report.findings} == {"dynamic-eval", "debugger-statement"}
    assert next(f for f in report.findings if f.rule_id == "debugger-statement").suggested_fix


def test_safe_patterns_and_import_aliases(tmp_path):
    path = tmp_path / "test.py"
    path.write_text(
        'import subprocess as sp\nsp.run(["echo", "hi"], shell=False)\n'
        'cursor.execute("SELECT * FROM t WHERE id = ?", (value,))\n'
    )
    assert not ReviewEngine().review(ReviewRequest(path=path)).findings
    path.write_text("from subprocess import run as launch\nlaunch(command, shell=True)\n")
    assert ReviewEngine().review(ReviewRequest(path=path)).findings[0].rule_id == "shell-true"


def test_invalid_syntax_reports_without_crash(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n")
    report = ReviewEngine().review(ReviewRequest(path=path))
    assert any(f.rule_id == "syntax-error" for f in report.findings)


def test_python_type_mismatch_reports_runtime_type_error(tmp_path):
    path = tmp_path / "circle.py"
    path.write_text(
        'import turtle\n'
        'radius = "banana"\n'
        'pi = True\n'
        'circle_area = pi - radius\n'
        'print("The area of the circle is:", circle_area)\n'
    )

    report = ReviewEngine().review(ReviewRequest(path=path))

    finding = next(item for item in report.findings if item.rule_id == "incompatible-operands")
    assert finding.severity.value == "HIGH"
    assert finding.lines.start == 4
    assert "bool" in finding.description and "str" in finding.description


def test_review_does_not_execute_source(tmp_path):
    path = tmp_path / "danger.py"
    marker = tmp_path / "executed"
    path.write_text(f'open({str(marker)!r}, "w").write("bad")\nraise RuntimeError("do not run")\n')
    ReviewEngine().review(ReviewRequest(path=path))
    assert not marker.exists()
