# CLI, scoring and local-AI reference

[Back to the project overview](../README.md)

## CLI

```sh
aicr review .
aicr review src/main.py
aicr review --staged
aicr review --diff HEAD~1
aicr review --no-ai
aicr review --severity high
aicr review --format json --output review.json
aicr review --format markdown --output review.md
aicr review --save-report findings.json
aicr explain FINDING_ID --report findings.json
aicr review --fail-on high
aicr config show
aicr doctor
aicr version
```

`--staged` analyzes index content against HEAD, even with different unstaged edits.
`--diff REF` analyzes tracked working-tree changes against a verified commit. These
options are mutually exclusive. Diff scoring includes only findings intersecting
changed new-side lines. Deleted code is not analyzed. Normal directory review includes
nonignored untracked files; diff review does not. Common generated/vendor directories
are excluded. Non-Git directory review uses built-in excludes, not `.gitignore`.

Text reports show locations, confidence, validation, evidence, recommendations, counts,
score and duration. JSON is a complete versioned `ReviewReport` with clean stdout.
`--severity` filters text/Markdown without changing the score; it cannot be combined
with JSON output. Exports refuse to overwrite existing files. Reports are saved only
when requested; `explain` takes an explicit saved JSON path.

Exit codes: **0** completed, **1** explicit `--fail-on` quality gate failed, **2** input,
configuration or output error. AI failures and partial scans produce warnings: inspect
`warnings` and `ai_status` in automation. Successful exit does not certify source safe.
No command automatically applies patches, commits or posts comments.

## Working capabilities

| Capability | Current scope |
| --- | --- |
| Tree-Sitter | Python, JavaScript/JSX, TypeScript, TSX; installed grammars |
| Security patterns | Python eval/exec, shell=True, pickle trust boundaries, formatted execute calls; JS/TS eval |
| Bug patterns | Python mutable defaults, literal zero divisors, bare except; parser syntax errors |
| Maintainability | Python long functions and branch counts; JS/TS debugger statements |
| Performance | Python nested-iteration heuristic, not a runtime complexity proof |
| Documentation | Python public functions missing docstrings |
| AI specialists | Optional local security, bug, performance and maintainability reasoning |
| Grounding | Snapshot file/line, exact snippet and enclosing symbol checks |
| Scoring | Deterministic per-finding penalties with explanations |
| Patches | Exact-preimage unified diffs; built-in debugger removal and optional AI suggestions |

These are review heuristics, not proven exploitability. No accuracy benchmarks have
been run. AI evidence matching source is `GROUNDED`, not semantically verified.
Unverifiable AI findings remain visible with zero score penalty; invalid locations
are retained separately as rejected findings. Deduplication uses rule and exact location.

Score = `max(0, 100 - sum(severity_weight * confidence * validation_weight))`.
Severity weights: critical 25, high 12, medium 5, low 2, info 0. Validation weights:
verified static 1, grounded AI 0.5, unverified/rejected 0. AI confidence is capped at
0.85. Score 100 may mean no supported files or no matching rules; read warnings.

## Optional local AI

Use an already installed local Ollama model suitable for your hardware. This project
does not download models. In a copy of `.env.example`, set:

```dotenv
AICR_PROVIDER=ollama
AICR_BASE_URL=http://localhost:11434
AICR_MODEL=your-installed-local-model
```

Run `aicr review . --env-file .env`. A local compatible server is supported with
`AICR_PROVIDER=openai-compatible` and a base URL such as `http://localhost:1234/v1`.
Remote endpoints and Ollama `:cloud` model names are rejected. Ensure your local server
does not itself forward to cloud services. Local compute, disk and model license
requirements still apply. No paid provider is needed.

Process environment overrides the explicit dotenv file. Configuration files from the
reviewed repository are never auto-loaded. `config show` masks the API key. With AI
enabled, selected source and AST metadata go to the local server. Default budgets allow
eight requests; oversized contexts are skipped with warnings. Provider failures preserve
static findings. Saved reports include code snippets and should be handled like source.

The adapters follow the [Tree-Sitter bindings](https://tree-sitter.github.io/py-tree-sitter/)
and [Ollama chat API](https://docs.ollama.com/api/chat) contracts.

## Shared library

```python
from pathlib import Path
from ai_code_review.core.models import ReviewRequest
from ai_code_review.review.engine import ReviewEngine

report = ReviewEngine().review(ReviewRequest(path=Path("src"), no_ai=True))
print(report.model_dump_json(indent=2))
```

The FastAPI application calls this same engine. CLI rendering contains no
review rules. See [core architecture](phase1_architecture.md) for contracts,
trust states, free-resource policy, scoring and extension points.
