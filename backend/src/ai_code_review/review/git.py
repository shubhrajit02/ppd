"""Read Git metadata and blobs; never invoke worktree filters or diff drivers."""

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryFile

from ai_code_review.core.exceptions import InputError


def git(root: Path, *args: str) -> bytes:
    """Bound process time and captured output; disable fsmonitor and lazy network fetch."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Preserve only ownership exceptions explicitly supplied by the caller/host.
    # Repository/worktree redirection and executable config overrides remain stripped.
    trusted = [
        value
        for key, value in os.environ.items()
        if key.startswith("GIT_CONFIG_KEY_") and value == "safe.directory"
    ]
    if trusted:
        values = [
            os.environ.get(key.replace("KEY_", "VALUE_"), "")
            for key, value in os.environ.items()
            if key.startswith("GIT_CONFIG_KEY_") and value == "safe.directory"
        ]
        env["GIT_CONFIG_COUNT"] = str(len(values))
        for number, value in enumerate(values):
            env[f"GIT_CONFIG_KEY_{number}"] = "safe.directory"
            env[f"GIT_CONFIG_VALUE_{number}"] = value
    env.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_TERMINAL_PROMPT="0",
        GIT_LITERAL_PATHSPECS="1",
        GIT_NO_LAZY_FETCH="1",
        GIT_NO_REPLACE_OBJECTS="1",
    )
    try:
        with TemporaryFile() as output:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "core.quotePath=false",
                    "-c",
                    "core.fsmonitor=false",
                    *args,
                ],
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout=30,
                env=env,
                check=False,
            )
            if result.returncode:
                raise InputError("Git operation failed; check repository, revision and index state")
            if output.tell() > 32_000_000:
                raise InputError("Git metadata/output exceeds 32 MB safety limit")
            output.seek(0)
            return output.read()
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError("Git unavailable or operation timed out") from exc


def index_entries(root: Path) -> dict[str, str]:
    """Only stage-zero regular files; refuse unresolved conflicts."""
    entries = {}
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, blob, stage = metadata.split(b" ")
        if stage != b"0":
            raise InputError("Resolve Git index conflicts before diff review")
        if mode in {b"100644", b"100755"}:
            entries[name.decode("utf-8")] = blob.decode("ascii")
    return entries


def base_entries(root: Path, revision: str | None) -> dict[str, str]:
    """A missing HEAD is valid only for an unborn branch in staged mode."""
    try:
        commit = (
            git(
                root,
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{revision or 'HEAD'}^{{commit}}",
            )
            .decode()
            .strip()
        )
    except InputError:
        if revision is None:
            ref = git(root, "symbolic-ref", "-q", "HEAD").decode().strip()
            refs = git(root, "for-each-ref", "--format=%(refname)", "--", ref).decode().splitlines()
            if ref not in refs:
                return {}
        raise
    entries = {}
    for entry in git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, blob = metadata.split(b" ")
        if kind == b"blob" and mode in {b"100644", b"100755"}:
            entries[name.decode("utf-8")] = blob.decode("ascii")
    return entries


def read_blob(root: Path, blob: str, limit: int) -> bytes | None:
    if int(git(root, "cat-file", "-s", blob)) > limit:
        return None
    return git(root, "cat-file", "blob", blob)
