# Product validation — 11 September 2026

Validated locally on Windows with Python 3.11, Node.js 24 and Microsoft Edge.
No paid API, cloud host or model account was used. The optional local-model adapter
is tested with controlled responses; model inference quality was not benchmarked.

## Quality gates

| Gate | Result |
| --- | --- |
| Backend suite | 100 passed, 1 skipped (Windows symlink privilege) |
| Backend lint / format | Ruff clean |
| Backend strict typing | mypy clean, 39 source files |
| Frontend unit/component tests | 7 passed in 3 files |
| TypeScript | `tsc --noEmit` passed; production build typecheck passed |
| Frontend lint | ESLint clean |
| Production build | All application routes built successfully |
| Browser E2E | All six critical journeys passed; affected main journey rechecked after favicon fix |
| Browser console | Zero console errors in the final complete landing-to-review journey |
| CLI compatibility | `aicr doctor`, real file review and browser/CLI parity passed |

Two upstream deprecation warnings are reported by Starlette's HTTPX TestClient and
AnyIO portal alias. They do not indicate failing assertions. CI is configured for
Linux/Windows core checks and Chromium browser tests; remote CI has not been run here.

## Browser coverage

1. Landing → explicit demo input → real API analysis → completed review → finding/file/line
   selection → evidence → patch copy and download → dialog Escape/focus restoration →
   saved triage → filters → score explanation → disabled AI trace → command palette → history.
2. Empty history and disconnected API states, including an available retry control.
3. Desktop canvas context loss and a live change to reduced-motion preference, retaining SVG fallback.
4. Identical TypeScript source reviewed by a real CLI subprocess and uploaded via browser.
   Findings, complete score object and schema version match exactly; run-specific root/time differ.
5. 375px mobile Code/Findings/Files navigation, jump-to-code, no horizontal page overflow,
   keyboard palette activation and static graph with reduced motion.
6. 768×1024, 1024×768 and 812×375 route checks; local LCP/CLS performance budgets.

Axe checks WCAG A/AA rules on landing, desktop review and mobile review screens, with
zero violations in the tested states. Keyboard controls, visible focus and dialog return
focus are exercised. This is automated coverage plus visual inspection, not certification
or a complete assistive-technology audit. Error-state tests deliberately intercept requests;
the main demo, upload, patch and parity workflows use the real API.

Local unthrottled performance sample: LCP 208 ms, CLS 0.000634, four long tasks during
initial load. Budgets are CLS <0.1 and local LCP <5s. This is a browser PerformanceObserver
check, not a Lighthouse score or a claim about slower hardware/networks. WebGL is isolated
to lazy chunks, DPR limited, offscreen/hidden scenes stopped, and source rendering bounded
to 300 visible lines. Screenshots were inspected for desktop and 375px mobile layouts.

## Live GitHub checks

Read-only import of `kailash0001/ai-code-review-system` reviewed one supported Python
file, producing ten findings and score 89.6 from the shared engine. A source-changing
public PR, `pallets/flask#6154`, imported one changed Python file and its merge-base diff.
No findings were generated in that changed-line scope. Also verified a documentation-only
PR returns an explicit no-supported-source warning; a score of 100 is not assurance.
Private credentials were not required or tested live. MockTransport tests additionally
cover server-token isolation, fixed-host requests, unsupported/symlink/path exclusion,
PR diff reconstruction, redirects, access denials and rate-limit error scrubbing.

## Five-perspective self-review

- Engineering: fixed the queued-review undefined selection crash; added a regression
  test. Reused the shared engine and report schema. Kept immutable source and original scores.
- Product design: retained the original graphite/chartreuse identity, corrected graph
  label alignment, tightened mobile score/header layout, removed unused mobile panel space.
- Accessibility: gave icon-only mobile navigation explicit names, increased muted text
  contrast, preserved focus-safe dialogs, provided keyboard commands and reduced-motion fallback.
- Performance: dynamic R3F import, eight nodes/eleven edges, no textures or postprocessing,
  bounded DPR, demand rendering, pause/offscreen controls, memoized source tokenization.
- QA: tested real API and CLI parity, zero-result/failed/pending states, persistence,
  patch download/copy, source focus, responsive routes and live GitHub imports. The console
  audit identified a missing favicon; a product SVG icon was added.

The final affected-journey rerun passed after that icon fix, including clipboard copy,
download, focus restoration, accessibility assertions and zero browser console errors.

## Remaining limits

The graph is a labeled process schematic with actual event counters, not a real call graph.
No invented topology, per-category rating or completed AI activity is presented as measured data.
This release is a local single-user MVP. Future work includes production authentication,
multiuser worker isolation, a GitHub App/webhooks, deeper interprocedural checks, more
language rules, local-model evaluation, actual symbol topology, and safe approved patch
application. Source snapshots expire; evidence in reports persists until deletion.
No deployment, commit, push or remote CI execution was performed by this phase.
