from conftest import run_git
from test_domain import make_finding

from ai_code_review.analysis.ast import parse
from ai_code_review.core.models import (
    AgentFinding,
    FileChange,
    LineRange,
    SuggestedFix,
    ValidationState,
)
from ai_code_review.review.patching import generate_patch
from ai_code_review.review.validation import validate


def fixture():
    file = FileChange(path="main.py", language="python", content="def run():\n    eval(value)\n")
    context, _ = parse(file)
    finding = AgentFinding(
        **{
            **make_finding().model_dump(),
            "source": "ai",
            "lines": {"start": 2, "end": 2},
            "symbol": "run",
            "code_snippet": "eval(value)",
        }
    )
    return file, context, finding


def test_grounding_not_semantic_verification():
    file, context, item = fixture()
    result = validate(item, {file.path: file}, {file.path: context})
    assert result.validation == ValidationState.GROUNDED
    assert result.confidence == 0.85
    assert result.evidence[1] == "    eval(value)"
    assert item.validation == ValidationState.UNVERIFIED


def test_fabricated_file_line_symbol_and_snippet():
    file, context, item = fixture()
    for update, state in [
        ({"file": "../secret.py"}, ValidationState.REJECTED),
        ({"lines": LineRange(start=99, end=99)}, ValidationState.REJECTED),
        ({"symbol": "invented"}, ValidationState.UNVERIFIED),
        ({"code_snippet": "invented code"}, ValidationState.UNVERIFIED),
    ]:
        candidate = item.model_copy(update=update)
        result = validate(candidate, {file.path: file}, {file.path: context})
        assert result.validation == state


def test_ai_cannot_self_assert_verified_or_inject_evidence():
    file, context, item = fixture()
    item.validation = ValidationState.VERIFIED
    item.evidence = ["fabricated proof"]
    result = validate(item, {file.path: file}, {file.path: context})
    assert result.validation == ValidationState.GROUNDED
    assert "fabricated proof" not in result.evidence


def test_patch_exact_preimage_and_path():
    fix = SuggestedFix(
        lines=LineRange(start=1, end=1),
        original="debugger;\n",
        replacement="",
        explanation="Remove debug statement",
    )
    assert generate_patch("main.js", "debugger;\n", fix).startswith("--- a/main.js\n")
    assert generate_patch("main.js", "changed\n", fix) is None
    for path in ("../bad.js", "/bad.js", "C:\\bad.js", "bad\n.js"):
        assert generate_patch(path, "debugger;\n", fix) is None


def test_patch_can_be_applied_by_git_without_mutating_on_generation(repo):
    path = repo / "main.js"
    path.write_bytes(b"debugger;\nconst x = 1;\n")
    fix = SuggestedFix(
        lines=LineRange(start=1, end=1),
        original="debugger;\n",
        replacement="",
        explanation="Remove debug statement",
    )
    patch = generate_patch("main.js", path.read_text(), fix)
    assert path.read_text().startswith("debugger;")
    patchfile = repo / "fix.patch"
    patchfile.write_bytes(patch.encode())
    run_git(repo, "apply", "--check", str(patchfile))
    run_git(repo, "apply", str(patchfile))
    assert path.read_text() == "const x = 1;\n"


def test_no_newline_patch(repo):
    path = repo / "main.js"
    path.write_bytes(b"debugger;")
    fix = SuggestedFix(
        lines=LineRange(start=1, end=1), original="debugger;", replacement="", explanation="Remove"
    )
    patchfile = repo / "fix.patch"
    patchfile.write_bytes(generate_patch("main.js", "debugger;", fix).encode())
    run_git(repo, "apply", "--check", str(patchfile))


def test_fix_removed_if_model_fabricates_preimage():
    file, context, item = fixture()
    item.suggested_fix = SuggestedFix(
        lines=item.lines, original="fake", replacement="", explanation="fake"
    )
    result = validate(item, {file.path: file}, {file.path: context})
    assert result.suggested_fix is None


def test_fix_cannot_edit_outside_cited_finding():
    file, context, item = fixture()
    item.suggested_fix = SuggestedFix(
        lines=LineRange(start=1, end=2),
        original=file.content,
        replacement="",
        explanation="Remove everything",
    )
    result = validate(item, {file.path: file}, {file.path: context})
    assert result.suggested_fix is None
    assert any("out-of-scope" in note for note in result.validation_notes)
