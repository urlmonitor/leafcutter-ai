---
description: Retrospective for the GenReviewFixes loose-ticket remediation batch (PR
created: '2026-07-21'
last_updated: '2026-07-21'
type: tutorial
status: active
---
# Retrospective: GenReviewFixes
Date: 2026-07-21
Batch type: Loose-ticket remediation batch (not an EPIC-* folder)
Merged: PR #372 — fix(generator): components-list + implemented_by backref robustness
Commit: 439b74007 (2026-07-21 12:34:54 +0200)

> Note: The structured epic-folder tooling (extract_epic_facts.py, aggregate.py) cannot
> resolve loose-ticket batches. Quantitative data was derived directly from the ticket
> files in tickets/99_done/.

---

## Summary

This batch remediated 10 defects found in the generator (generate_ticket_from_ac.py) by
an independent code-review + adversarial logic-check pass run against PR #362 AFTER it
had merged with per-ticket green sign-offs. None of the defects had been caught by the
per-ticket TDD cycle; all were surface-level bugs in data normalisation and module-load
side effects.

The ACs split evenly across two concerns: (1) components-list normalisation — scalar
shatter, kebab normalisation, unresolvable-value warning, and data-driven validity via
components.json (TKT-500f-14-ii, -15, -16, -17, -17-i, -18, -18-i); (2) implemented_by
back-reference path canonicalisation — legacy absolute-path dedup via a shared
canonicaliser and git-derived repo-root relativisation with graceful fallback
(ACD-1200a-13, -14, -14-i). All 10 tickets landed in a single batched commit (PR #372).

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 10 |
| Completed tickets | 10 (100 %) |
| PR | #372 |
| Merged | 2026-07-21 |
| Primary file changed | scripts/ac_store/generate_ticket_from_ac.py |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Feedback entries available | 0 (feedback.jsonl absent in this worktree; pre-drive check skipped) |

---

## Phase Metrics

All 10 tickets ran through the same 8-phase sequence. No phase failed across the batch.

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| test-writer | 10 | 0 | 0 |
| python-coder | 10 | 0 | 0 |
| test-runner | 10 | 0 | 0 |
| pr-reviewer | 10 | 0 | 0 |
| ac-validator | 10 | 0 | 0 |
| ac-fulfillment-gate | 10 | 0 | 0 |
| commit | 10 | 0 | 0 |
| pull-request | 10 | 0 | 0 |

Note: commit and pull-request phases were batched at the end of the drive rather than
per-ticket, confirmed in each ticket's batch-finalization comment.

---

## Category Breakdown (Feedback System)

No structured feedback entries are available for this batch. The worktree's
debugging/logs/feedback.jsonl was not populated (feedback sink not established before
the drive). Omitted per the pre-epoch fallback rule.

---

## What Went Well

- **TDD red-baseline discipline held.** All 10 test-writer phases produced genuine RED
  baselines (verified with non-zero exit). The error messages in the baselines were
  exact and directly diagnosed the production bug — no fixture-bias issues.

- **Batched commit approach.** Parallel test-writers followed by focused python-coder
  passes in a single coder session proved significantly more disruption-resilient than
  10 sequential full ticket-supervisor drives. When sessions were disrupted, recovery
  required only reading git state and sign-off comments, not replaying entire drives.

- **pr-reviewer run on the full diff.** Running pr-reviewer once across the complete
  diff (rather than per-ticket) caught 2 HIGH findings that all per-ticket green tests
  had missed: a forward-reference NameError in _load_migration_map's cold-import
  fallback path (masked by importlib.reload() in tests), and an apparent "deleted"
  function that was actually origin/main having advanced past the branch base.

- **100 % completion, zero blockers.** No structural blockers, no cross-agent rework
  loops, no brainstorm escalations. Every ticket closed with status: ok on the first
  coder pass.

- **Data-driven component resolution.** The fix avoided hard-coded kebab maps by loading
  validity directly from docs/components.json, making the set extensible without code
  changes — a clear architectural improvement over the defective generator.

---

## Friction Points

- **Session disruptions killed background supervisors mid-drive.** At least two session
  interruptions required manual recovery: reading worktree git state, inspecting
  sign-off comments, and re-dispatching incomplete ticket phases. Recovery was
  unambiguous but manual; no automated resume checkpoint was available.

- **Root conftest.py blast radius.** During the drive, a python-coder introduced a
  root-level conftest.py to fix a cross-test sys.modules ordering issue. It silently
  hijacked `from conftest import load_fixture` imports in another test subdirectory
  (unit_tests/ac_driven_dev/), because Python's import resolution treats the repo root
  conftest as global scope. The breakage was caught only by running the FULL strict
  suite — per-file runs of the affected tests passed because they picked up conftest
  before the conflict. Diagnosis required diffing which tests suddenly had different
  import resolution.

- **importlib.reload() masks cold-import failures.** The pr-reviewer found a H-2
  NameError (forward reference in _load_migration_map) that the green test suite had
  missed. The relevant tests used importlib.reload() to re-exercise the module, but
  reload() re-executes the module body in the already-populated namespace, so names
  that would fail on a true cold import were already present. The bug only surfaces in a
  genuinely fresh process (subprocess import or a fresh Python interpreter). This is a
  systematic blind spot for any test that validates module-load-order behaviour via
  reload() rather than fresh subprocess.

- **AC_ENFORCE_STRICT=1 noise.** Running the suite with AC_ENFORCE_STRICT=1 floods
  results with xfail-turned-red baselines from OTHER in-flight ACs (unrelated tickets
  not yet done). Triage must explicitly separate: (a) noise from not-done in-flight ACs,
  (b) build-deploy-env failures (registry build-guard), and (c) real regressions
  introduced by the branch. Without this triage pass, the signal-to-noise ratio makes it
  easy to miss a genuine new failure hidden in a wall of expected reds.

- **Batch-commit sign-off timestamps.** All 8 later phases (test-runner through
  pull-request) share timestamp 2026-07-21 12:44 in every ticket because they were
  applied as batch-finalization. This loses per-phase timing granularity in the
  retrospective but was a deliberate trade-off for simplicity.

---

## Knowledge Gaps Found

- **No documented pattern for "run pr-reviewer over the full diff" as a finalize gate.**
  CLAUDE.md's Pre-Drive Checklist has "Full test suite + ruff at epic-finalize" but does
  not mention running pr-reviewer across the combined diff before the batch commit. The
  full-diff pr-reviewer is what caught both H-level bugs in this batch.

- **No documented warning about root-level conftest.py blast radius.** The conftest
  hazard is subtle and not mentioned in any agent template or CLAUDE.md convention. A
  coder agent can introduce a root conftest for apparently local reasons and silently
  break import resolution across unrelated test directories.

- **No documented warning that importlib.reload() masks cold-import-order bugs.** The
  project error handling policy and implementation conventions do not mention this
  systematic testing blind spot. Test-writer agents writing reload()-based tests for
  import-side-effect ACs will reliably reproduce the masking pattern.

- **No documented triage protocol for AC_ENFORCE_STRICT=1 noise.** The pre-drive
  checklist mentions running strict mode but does not describe how to triage the noise
  from in-flight ACs vs. real regressions.

---

## Subagent Quality Trends

No supervisor feedback entries found for this batch (feedback sink was not established;
feedback.jsonl absent in the gen-finalize worktree). No adjudication events were
recorded during this drive.

---

## Proposed Improvements

---

### KI-1: Run pr-reviewer over the full diff as a mandatory pre-commit gate for batches

**Proposed text (to add to CLAUDE.md Pre-Drive Checklist, under "Full test suite + ruff at epic-finalize"):**

```
### Full-diff pr-reviewer before batch commit (MANDATORY for multi-ticket batches)

When driving multiple tickets in a single batch (not using epic-supervisor with
per-ticket PRs), run pr-reviewer once across the complete staged diff before the
batch commit — not just per-ticket:

  python -m claude --run "pr-reviewer" -- <staged diff path>

Or via the Agent tool from the main loop:
  Dispatch: pr-reviewer over the working diff.

Per-ticket test suites verify individual ACs in isolation but cannot see
cross-ticket interactions, latent cold-import bugs masked by importlib.reload(),
or apparent "deletions" that are actually origin/main advancing past the branch base.
A full-diff pr-reviewer caught 2 HIGH findings (H-2 NameError, H-1 framing) in the
GenReviewFixes batch that all per-ticket green tests had missed.

Why this matters: green per-ticket sign-offs on PR #362 passed all phase agents but
missed defects caught only by the post-merge code-review + logic-check that
triggered this batch.
(Source: GenReviewFixes retrospective KI-1, 2026-07-21.)
```

Routing: `CLAUDE.md-toc` (too long for inline; add a sub-heading under the existing
"Full test suite + ruff at epic-finalize" entry and expand it).

**Diff (proposed addition to CLAUDE.md Pre-Drive Checklist section):**

```diff
 ### Full test suite + ruff at epic-finalize (before merge)
 
-**What to check:** Per-ticket sign-offs run only that ticket's own tests...
+**What to check:** Per-ticket sign-offs run only that ticket's own tests (often via
+`unittest discover` on a subdir), so cross-cutting breakage and lint violations slip
+through — especially when the worktree pre-commit hooks are not established. Before
+merging any epic PR, run the FULL suite and ruff from the worktree root:
 
 [existing content unchanged]
+
+### Full-diff pr-reviewer before batch commit (MANDATORY for multi-ticket batches)
+
+When driving multiple tickets in a single batch, run pr-reviewer once across the
+complete staged diff BEFORE the batch commit — not just per-ticket. Per-ticket tests
+verify individual ACs in isolation but cannot see cross-ticket interactions or cold-import
+bugs masked by importlib.reload(). A full-diff pr-reviewer is what catches H-level latent
+bugs that all per-ticket green tests can miss.
+
+**Why this matters:** Green per-ticket sign-offs passed all phases in PR #362 but missed
+defects found only by the subsequent code-review + adversarial logic-check pass — which
+required 10 remediation tickets in PR #372.
+(Source: GenReviewFixes retrospective KI-1, 2026-07-21.)
```

---

### KI-2: Root conftest.py has repo-wide blast radius on import resolution

**Proposed text (to add to CLAUDE.md Implementation Conventions):**

```
### Root-level conftest.py — repo-wide import-resolution blast radius

A conftest.py placed at the repository root (or at any common ancestor of two or
more test subdirectories) is picked up by pytest as a global fixture / plugin file.
Any name it defines — including helper functions like `load_fixture` — is visible to
ALL test files in the repo via `from conftest import <name>`. This silently overrides
any same-named import that individual test subdirectories previously resolved through
their own local conftest or test helper.

Rule: DO NOT introduce a root-level conftest.py to fix a cross-test import-ordering
problem. Instead, fix the ordering in the affected test files (e.g., explicit import
ordering, sys.modules guards, or a module-level fixture in the specific test file).
If a shared conftest is genuinely needed, scope it to the narrowest common ancestor
directory that does not inadvertently cover unrelated test trees.

Catchability: the blast-radius breakage only manifests when you run the FULL suite
(not per-file runs of the affected tests), because a per-file run resolves conftest
relative to that file's directory, whereas pytest's collection traversal picks up the
root conftest when discovering across subdirectories.
(Source: GenReviewFixes retrospective KI-2, 2026-07-21.)
```

Routing: `CLAUDE.md-inline` (fits as a named convention block in Implementation
Conventions, same style as the existing "Function Signature Extension" block).

**Diff (proposed addition to CLAUDE.md under ## Implementation Conventions):**

```diff
 ## Implementation Conventions
 
 ### Function Signature Extension — Call-Site Audit Required
 [existing content unchanged]
 
 ### In-Place Workflow Specs — Protected-Branch AC Required
 [existing content unchanged]
+
+### Root-level conftest.py — Repo-wide Import-Resolution Blast Radius
+
+A conftest.py at the repo root (or any ancestor of two or more test trees) is picked
+up by pytest globally. Any name it defines overrides same-named imports that individual
+test subdirectories previously resolved locally — silently, with no error. The breakage
+only manifests on a FULL suite run, not on per-file runs of the affected tests.
+
+Rule: DO NOT introduce a root-level conftest.py to fix a cross-test import-ordering
+problem. Fix the ordering in the affected test files instead. If a shared conftest is
+genuinely required, scope it to the narrowest common ancestor that does not cover
+unrelated test trees.
+(Source: GenReviewFixes retrospective KI-2, 2026-07-21.)
```

---

### KI-3: importlib.reload() masks cold-import-order bugs — verify with a fresh process

**Proposed text (to add to CLAUDE.md Implementation Conventions):**

```
### importlib.reload() — Masks Module-Load-Order Bugs

Tests that call importlib.reload() to re-exercise module-level side effects (e.g.,
logging.basicConfig calls, forward-reference assignments, migration-map loading at
import time) do NOT reproduce a genuine cold-import. reload() re-executes the module
body in the ALREADY-POPULATED namespace — names that would raise NameError on a true
first import are already present from the prior import, so the reload() call succeeds
silently.

Systematic blind spot: any AC that says "importing this module must not X" (logging
side effect, NameError, circular import) and is tested only via reload() will produce
a false green even when the bug is present.

Fix: test cold-import behaviour in a subprocess or a fresh Python interpreter, not
via importlib.reload(). For example:

  subprocess.check_output([sys.executable, "-c", "import generate_ticket_from_ac"])

Verify the test is RED (catches the bug) in the unpatched state before accepting the
green sign-off.
(Source: GenReviewFixes retrospective KI-3, 2026-07-21.)
```

Routing: `CLAUDE.md-inline` (fits as a named convention block in Implementation
Conventions, under the existing conventions).

**Diff (proposed addition to CLAUDE.md under ## Implementation Conventions):**

```diff
 ### Root-level conftest.py — Repo-wide Import-Resolution Blast Radius
 [content as above]
+
+### importlib.reload() Masks Cold-Import-Order Bugs
+
+`importlib.reload()` re-executes the module body in the already-populated namespace.
+Names that would raise NameError on a true first import are already present, so
+reload() succeeds silently where a cold import would fail.
+
+Rule: any AC that asserts "importing this module must not X" (logging side effect,
+NameError, circular import, missing attribute) MUST be tested with a subprocess cold
+import, not via reload():
+
+    subprocess.check_output([sys.executable, "-c", "import <module>"])
+
+Confirm the test is RED on the unpatched code before accepting a green sign-off.
+(Source: GenReviewFixes retrospective KI-3, 2026-07-21.)
```

---

### KI-4: AC_ENFORCE_STRICT=1 triage — separate noise from real regressions

**Proposed text (to add as a memory-project file):**

```
# AC_ENFORCE_STRICT=1 — Noise Triage Protocol

Running the test suite with AC_ENFORCE_STRICT=1 will turn every not-yet-done AC's
xfail into a real failure, producing a wall of red from in-flight ACs across the
entire store — not just the tickets being built.

Before treating any failure as a real regression, triage into three buckets:

1. **In-flight AC noise** — FAIL on an xfail test whose AC id is not in the current
   batch. These are expected and do not indicate a regression. Ignore.

2. **Build/deploy-env failures** — FAIL on the registry self-description build-guard
   or any test that requires build.py to have been run first. These are pre-existing
   non-required failures (see project_main_ci_pytest_pre_existing_fail.md). Ignore.

3. **Real regressions** — FAIL on a test that was GREEN in the per-ticket baseline
   for a ticket in the current batch, or a NEW test that never had a green baseline.
   These need investigation before committing.

Practical approach: run the full strict suite, save the failure list, then diff
it against the per-ticket red baselines captured in test-writer comments. Anything
in the failure list that is NOT in any red baseline (and is not an in-flight AC xfail)
is a genuine regression.
```

Routing: `memory-project`
Path: `memory/project_ac_enforce_strict_triage.md`

**Diff (proposed new file — no existing file to diff against):**

```diff
+# AC_ENFORCE_STRICT=1 — Noise Triage Protocol
+
+Running the suite with AC_ENFORCE_STRICT=1 floods results with in-flight ACs' red
+baselines from OTHER tickets not in the current batch. Before treating any failure
+as a real regression, separate into three buckets:
+
+1. In-flight AC noise: xfail-turned-red whose AC id is NOT in the current batch. Ignore.
+2. Build/deploy-env failures: registry build-guard + deploy-dependent tests. Ignore.
+3. Real regressions: failures that were GREEN in any per-ticket baseline, or NEW tests
+   that never had a green baseline. Investigate before committing.
+
+Method: diff the full-strict failure list against the test-writer red_baseline blocks
+in the current batch's ticket comments. Failures not in any baseline and not from
+in-flight ACs are genuine regressions.
+(Source: GenReviewFixes retrospective KI-4, 2026-07-21.)
```

---

### KI-5: Batched parallel test-writers + focused single coder pass is disruption-resilient

**Proposed text (to add to CLAUDE.md Pre-Drive Checklist or a how-to):**

```
### Batch drive pattern: parallel test-writers → single focused coder session

When building 5+ tickets that share a single implementation file, a sequential
full ticket-supervisor drive (one supervisor per ticket) is vulnerable to session
disruptions: each supervisor runs background agents; a disruption mid-drive leaves
some supervisors dead with indeterminate state, requiring manual triage of every
ticket's sign-off status.

A more resilient pattern:
1. Dispatch all test-writers in parallel (via parallel Agent calls or manually
   per ticket) to write all red baselines before any coder runs.
2. Run a single python-coder session across ALL implementation tickets in one pass,
   because they share the same file. The coder has full context of all red tests.
3. Run test-runner on the full suite once (or per-batch), then batch-commit.

Benefits:
- A session disruption after step 1 leaves all baselines captured and stable.
- A disruption during step 2 is easy to recover: re-read git state + remaining red tests.
- No coder context-switch between tickets; single-file changes are reviewed once.

This pattern was validated in the GenReviewFixes batch (10 tickets, 1 implementation
file, 0 blockers, single session).
(Source: GenReviewFixes retrospective KI-5, 2026-07-21.)
```

Routing: `CLAUDE.md-toc` — too long for inline; add a sub-heading under Pre-Drive
Checklist or create `docs/how-to/batch-drive-pattern.md` and link from CLAUDE.md.

**Diff (proposed addition to CLAUDE.md Pre-Drive Checklist section):**

```diff
 ## Pre-Drive Checklist
 
 [existing entries unchanged]
+
+### Batch drive pattern for shared-file ticket groups (resilient to session disruptions)
+
+When building 5+ tickets that all touch the same implementation file, prefer:
+1. Dispatch all test-writers in parallel (all red baselines captured first).
+2. Run a single python-coder session covering all tickets in one pass.
+3. Run the full test suite once, then batch-commit.
+
+This pattern is more disruption-resilient than one full ticket-supervisor per ticket
+because recovery after a disruption only requires reading git state + remaining red tests
+— no phantom-state risk from partially-completed supervisor loops.
+(Source: GenReviewFixes retrospective KI-5, 2026-07-21.)
```

---

## Appendix: Tickets in this Batch

| Ticket ID | Title (abbreviated) |
|-----------|---------------------|
| TKT-500f-14-ii | Source extension set excludes markup/style/shell, includes .go/.rs/.mjs |
| TKT-500f-15 | Scalar-string components becomes single-element graph-id list (no per-char shatter) |
| TKT-500f-16 | Kebab values in components LIST normalised to underscore graph ids |
| TKT-500f-17 | Unresolvable component value warns; validity data-driven from components.json |
| TKT-500f-17-i | Unresolved value surfaced verbatim, warning emitted once per distinct value |
| TKT-500f-18 | Kebab-to-graph-id mapping from side-effect-free source; no logging.basicConfig at import |
| TKT-500f-18-i | Malformed/unavailable mapping source degrades to logged fallback without raising |
| ACD-1200a-13 | Legacy absolute implemented_by entry collapsed to repo-relative via shared canonicaliser |
| ACD-1200a-14 | Ticket outside worktree recorded repo-relative via git-derived repo root |
| ACD-1200a-14-i | git rev-parse fallback when repo root unavailable; never records raw absolute path |
