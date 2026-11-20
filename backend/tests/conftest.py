import os
import subprocess
from pathlib import Path

import pytest


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    for key in os.environ:
        if key.startswith("AICR_") or key in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"}:
            monkeypatch.delenv(key)


@pytest.fixture
def repo(tmp_path):
    run_git(tmp_path, "init", "-b", "main")
    run_git(tmp_path, "config", "user.email", "test@example.invalid")
    run_git(tmp_path, "config", "user.name", "Test")
    run_git(tmp_path, "config", "core.autocrlf", "false")
    return tmp_path
