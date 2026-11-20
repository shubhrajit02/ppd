# Phase 1 validation record

Validated locally on Windows with Python 3.11 on 2026-09-10.

| Check | Result |
| --- | --- |
| `python -m pytest backend/tests -q` | 68 passed, 1 skipped |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | 32 files already formatted |
| `python -m mypy --config-file backend/pyproject.toml backend/src` | Passed, 25 source files |
| `python -m pip check` | No broken requirements |
| `git diff --check` | Passed |
| Installed `aicr doctor`, `version`, `config show` | Passed |
| Real terminal, JSON and Markdown review runs | Passed |
| Real working-tree and staged CLI modes | Passed |

The skipped test requires Windows symlink creation privileges. The CI matrix is
configured for Linux/Windows with Python 3.11/3.12 but has not run remotely in this
implementation session. No live model or cloud API was used. Provider transport,
failure, schema validation and engine integration tests use controlled HTTP responses;
they do not measure model reasoning quality. No accuracy or performance benchmark is
claimed from these tests or the intentionally vulnerable fixtures.

## Self-review outcomes

- Fixed JSON round-trip model consistency while retaining static/AI source provenance.
- Verified exact index reads, unborn branches, renames, deletions, literal pathspecs,
  ignored files, file/byte budgets and unresolved-conflict errors using real Git repos.
- Replaced worktree Git diff calls with in-memory snapshot comparisons so clean filters
  cannot execute repository-configured programs. Disabled fsmonitor and lazy fetching.
- Preserved caller-supplied Git ownership exceptions without accepting repository
  redirection; Git errors in known repositories no longer silently fall back to folder scans.
- Required fix preimages and edit ranges to match the cited source. Real `git apply
  --check` tests cover ordinary patches and files without final newlines.
- Revalidated model claims rather than trusting their submitted evidence/trust states.
  Invalid locations are rejected and unsupported claims receive no score penalty.
- Kept provider failures nonfatal to static review and made `--no-ai` override an
  incomplete model configuration. Reports and source files are never overwritten.
- Preserved research/prototype artifacts, marked unsupported claims historical, and
  documented deferred components explicitly.

The engine's own heuristic review also flags maintainability considerations such as
branch-heavy rule dispatch/input validation, nested iteration and missing helper
docstrings. These are human-review suggestions, not demonstrated runtime defects.
The local core review returned no high or critical findings; that is not security
assurance and does not replace external review or broader analysis.
