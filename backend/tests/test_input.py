import pytest
from conftest import run_git

from ai_code_review.analysis.language import detect_language
from ai_code_review.core.config import Settings
from ai_code_review.core.exceptions import InputError
from ai_code_review.core.models import ReviewRequest
from ai_code_review.review.engine import ReviewEngine
from ai_code_review.review.input import normalize, parse_diff_ranges


@pytest.mark.parametrize(
    "name,language",
    [
        ("x.py", "python"),
        ("x.JSX", "javascript"),
        ("x.ts", "typescript"),
        ("x.tsx", "tsx"),
        ("x.rs", None),
    ],
)
def test_language(name, language):
    assert detect_language(name) == language


def test_missing_and_unsupported(tmp_path):
    with pytest.raises(InputError):
        normalize(ReviewRequest(path=tmp_path / "absent"), Settings())
    path = tmp_path / "readme.txt"
    path.write_text("hello")
    with pytest.raises(InputError):
        normalize(ReviewRequest(path=path), Settings())
    with pytest.raises(InputError):
        normalize(ReviewRequest(path=tmp_path, staged=True), Settings())


def test_git_scan_ignores_generated_files_and_scopes_subdirectory(repo):
    (repo / ".gitignore").write_text("ignored.py\n")
    for name in ("ok.py", "ignored.py"):
        (repo / name).write_text("x = 1\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.py").write_text("eval(x)\n")
    (repo / "src").mkdir()
    (repo / "src" / "nested.py").write_text("x = 1\n")
    all_files = normalize(ReviewRequest(path=repo), Settings()).files
    assert {f.path for f in all_files} == {"ok.py", "src/nested.py"}
    scoped = normalize(ReviewRequest(path=repo / "src"), Settings()).files
    assert [f.path for f in scoped] == ["src/nested.py"]


def test_limits_binary_encoding_and_empty(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x\0y")
    (tmp_path / "b.py").write_bytes(b"\xff")
    (tmp_path / "c.py").write_bytes(b"x" * 50)
    result = normalize(ReviewRequest(path=tmp_path), Settings(max_file_bytes=20))
    assert not result.files
    assert any("binary" in w for w in result.warnings)
    assert any("UTF8" in w for w in result.warnings)
    assert any("oversized" in w for w in result.warnings)


def test_file_and_byte_budgets(tmp_path):
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text("x = 1\n")
    result = normalize(ReviewRequest(path=tmp_path), Settings(max_files=1))
    assert len(result.files) == 1
    assert any("count limit" in w for w in result.warnings)
    result = normalize(ReviewRequest(path=tmp_path), Settings(max_total_bytes=7))
    assert len(result.files) == 1
    assert any("byte limit" in w for w in result.warnings)


def test_staged_uses_index_and_excludes_unchanged_lines(repo):
    path = repo / "space name.py"
    path.write_text("eval(old)\nx = 1\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "initial")
    path.write_text("eval(old)\neval(new)\n")
    run_git(repo, "add", ".")
    path.write_text("x = 0\nx = 2\n")
    report = ReviewEngine().review(ReviewRequest(path=repo, staged=True))
    assert len(report.findings) == 1
    assert report.findings[0].lines.start == 2
    assert report.findings[0].code_snippet == "eval(new)"
    assert report.rejected_findings[0].lines.start == 1


def test_unborn_staged_and_deleted_worktree_file(repo):
    path = repo / "new.py"
    path.write_text("eval(value)\n")
    run_git(repo, "add", ".")
    path.unlink()
    report = ReviewEngine().review(ReviewRequest(path=repo, staged=True))
    assert report.summary.findings_count == 1


def test_diff_base_and_rename_and_deletion(repo):
    path = repo / "old.py"
    path.write_text("x = 1\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "initial")
    run_git(repo, "mv", "old.py", "new.py")
    (repo / "new.py").write_text("eval(value)\n")
    report = ReviewEngine().review(ReviewRequest(path=repo, diff="HEAD"))
    assert report.findings[0].file == "new.py"
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "rename")
    (repo / "new.py").unlink()
    assert not ReviewEngine().review(ReviewRequest(path=repo, diff="HEAD")).findings
    with pytest.raises(InputError):
        normalize(ReviewRequest(path=repo, diff="--output=bad"), Settings())


def test_hunk_parsing():
    result = parse_diff_ranges("@@ -1 +2 @@\n+x\n@@ -5,3 +6,0 @@\n-x\n@@ -10 +11,2 @@\n")
    assert [(r.start, r.end) for r in result] == [(2, 2), (11, 12)]


def test_symlinks_are_not_followed(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("eval(value)\n")
    root = tmp_path / "project"
    root.mkdir()
    link = root / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("OS does not grant symlink privileges")
    assert not normalize(ReviewRequest(path=root), Settings()).files
    with pytest.raises(InputError):
        normalize(ReviewRequest(path=link), Settings())


def test_pathspec_metacharacters_are_literal(repo):
    path = repo / "[one].py"
    path.write_text("x = 1\n")
    (repo / "o.py").write_text("x = 1\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "base")
    path.write_text("eval(value)\n")
    result = normalize(ReviewRequest(path=path, diff="HEAD"), Settings())
    assert [f.path for f in result.files] == ["[one].py"]


def test_review_never_runs_git_filters_or_fsmonitor(repo):
    path = repo / "main.py"
    path.write_text("x = 1\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "base")
    (repo / ".gitattributes").write_text("*.py filter=tripwire diff=tripwire\n")
    run_git(repo, "config", "filter.tripwire.clean", "echo executed > filter-marker; cat")
    run_git(repo, "config", "diff.tripwire.textconv", "echo executed > diff-marker")
    hook = repo / ".git" / "hooks" / "monitor"
    hook.write_bytes(b"#!/bin/sh\necho executed > monitor-marker\nexit 1\n")
    hook.chmod(0o755)
    run_git(repo, "config", "core.fsmonitor", str(hook))
    path.write_text("eval(value)\n")
    report = ReviewEngine().review(ReviewRequest(path=repo, diff="HEAD"))
    assert report.findings[0].rule_id == "dynamic-eval"
    for name in ("filter-marker", "diff-marker", "monitor-marker"):
        assert not (repo / name).exists()


def test_unmerged_index_refused(repo):
    import subprocess

    path = repo / "main.py"
    path.write_text("x = 1\n")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "base")
    run_git(repo, "checkout", "-b", "other")
    path.write_text("x = 2\n")
    run_git(repo, "commit", "-am", "other")
    run_git(repo, "checkout", "main")
    path.write_text("x = 3\n")
    run_git(repo, "commit", "-am", "main")
    with pytest.raises(subprocess.CalledProcessError):
        run_git(repo, "merge", "other")
    with pytest.raises(InputError, match="conflicts"):
        normalize(ReviewRequest(path=repo, staged=True), Settings())
