---
epic: EPIC-TrustworthyTestGate
date: 2026-07-08
status: closed
pr: '#172'
created: '2026-07-08'
last_updated: '2026-07-08'
type: tutorial
description: Retrospective for EPIC-TrustworthyTestGate — AC-status-gated test enforcement gate (PR #172); 8 of 25 tickets completed.
---
# Retrospective: EPIC-TrustworthyTestGate
Date: 2026-07-08
Epic duration: 2026-06-24 to 2026-07-08
Commits on main: 9 (8 AC tickets + 1 post-merge fix)

## Summary

EPIC-TrustworthyTestGate implemented AC TQ-100: "Your test suite only blocks main for
failures that actually matter." The epic delivered two foundational pillars of trustworthy
testing: (1) collection-error isolation so a single broken import cannot abort the entire
suite, and (2) AC-status-gated enforcement so a failing test linked to a not-yet-done AC
is reported informationally rather than failing the run. The core mechanism is a globally
registered pytest plugin (`scripts/ac_store/pytest_ac_enforcement.py`) loaded via
`pytest.ini addopts`, together with a session-scoped AC-store cache
(`scripts/ac_store/test_enforcement.py`).

Of the 25 planned tickets, 8 were completed and merged. The remaining 17 tickets (covering
lifecycle diagrams, linkage integrity checks, allowlist mechanics, and enforcement-mode
configuration) are deferred to future drives. One post-merge fix commit (H-1) was required
after an adversarial code review discovered that the CI workflow's `-x` / `--exitfirst`
flag was silently defeating the collection-isolation guarantee — the entire suite would
abort at the first failure before the isolation behaviour could take effect.

An additional caveat (L-4): the CI pytest job is `continue-on-error: true` (tracked as
BP-1200b), meaning the enforcement gate does not block merges even when it fires. This
must be fixed before the TQ-100 guarantee is operationally meaningful in CI.

## Metrics

| Phase | Signed Off | Failed | Needed (remaining) | Not Needed |
|-------|-----------|--------|--------------------|-----------|
| python-coder | 8 | 0 | 14 | 0 |
| test-writer | 8 | 0 | 14 | 0 |
| test-runner | 8 | 0 | 14 | 3 |
| pr-reviewer | 8 | 0 | 17 | 0 |
| commit | 8 | 0 | 17 | 0 |
| pull-request | 8 | 0 | 17 | 0 |
| architecture-diagram-author | 0 | 0 | 2 | 0 |
| reference-author | 0 | 0 | 1 | 0 |
| documentation-expert | 0 | 0 | 0 | 25 |
| sql-coder | 0 | 0 | 0 | 25 |

## Category Breakdown (Feedback System)

No structured per-ticket feedback was captured for this epic. All agent comment blocks
record `feedback-id: (submit-failed)`, indicating the feedback submission script
(`scripts/feedback/submit_feedback.py`) was not present in the drive worktree. This is
the known worktree-precommit-gap pattern (see Pre-Drive Checklist in CLAUDE.md).

One TTG entry appears in the shared `feedback.jsonl` corpus (test-runner for ticket 04,
`fb_2026-06-24_a296bfdd`) because it was submitted from a different worktree context.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 25 |
| Completed tickets | 8 |
| Tickets deferred | 17 |
| Git commits on main | 9 |
| First commit | 2026-06-24 |
| Last commit (fix) | 2026-07-08 |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Post-merge fix commits | 1 (H-1: drop -x from ci.yml) |

## What Went Well

- **Single-day drive for 8 tickets.** All 8 completed tickets (TQ-100a-1 through
  TQ-100b-2) were implemented and signed off on 2026-06-24 with zero blockers and zero
  retries.
- **TDD discipline maintained.** test-writer ran before python-coder on every ticket;
  red baselines were captured and verified on every ticket with a test requirement.
- **Fail-safe by default.** The plugin correctly enforces tests whose AC ID is absent from
  the store (TQ-100b-1-ii) — an elegant fail-safe design that avoids silent permissiveness.
- **Session-scoped AC cache.** The AC store is read once per session (TQ-100b-1-iii),
  preventing TOCTOU issues and keeping the enforced set stable across repeated runs within
  a drive.
- **PR reviewer picked up a phantom `files_touched` entry.** On ticket 05, pr-reviewer
  noted that `scan_ac_store.py` was listed in `files_touched` but not modified — a
  medium-confidence finding that would have confused downstream scope checkers.
- **check-feedback-id hook self-corrected.** On ticket 06, the pre-commit hook blocked
  the commit because upstream agent comments lacked `feedback-id:` lines. The commit
  agent identified and fixed the headings before retrying — exactly the intended hook
  behaviour.

## Friction Points

- **Feedback system absent in drive worktree (all tickets).** All 8 completed tickets
  record `feedback-id: (submit-failed)`. The submit_feedback.py script was not deployed
  into the EPIC-TrustworthyTestGate worktree, producing a zero-telemetry epic drive. This
  is the same gap documented in EPIC-ComputedQualityGates (FP-5, 2026-07-07). The
  Pre-Drive Checklist in CLAUDE.md now covers this but was not yet in place at the start
  of this drive.

- **H-1: CI -x flag silently defeated the guarantee (post-merge).** After the 8 tickets
  merged via PR #172, an adversarial code review discovered that `.github/workflows/ci.yml`
  invoked pytest with `-x` (`--exitfirst`). The `-x` flag aborts the suite at the first
  failure — which means the collection-isolation guarantee (every loadable file runs even
  when one import fails) was effectively inert in real CI. The per-ticket tests did not
  catch this because they spawn subprocess pytest calls without `-x`. Fix: drop `-x` from
  ci.yml and add `--continue-on-collection-errors`, plus a regression guard
  (`test_ci_invocation_isolation.py`). Commit: `2a377f91`.

- **Ticket 08 (TQ-100b-2) finalized weeks after the initial drive.** The test-writer and
  python-coder sign-offs were from 2026-06-24 but pr-reviewer, commit, and pull-request
  were not completed until 2026-07-08 (finalize day). The delay suggests the ticket was
  left partially open at the end of the initial drive session.

- **17 of 25 tickets remain TODO.** The TQ-100c (linkage integrity), TQ-100d (allowlist),
  and TQ-100e (enforcement mode configuration) pillars were not driven. The epic was
  merged with roughly one-third of the planned scope complete.

- **L-4: CI pytest is `continue-on-error: true` (BP-1200b).** The CI job that runs
  pytest is configured with `continue-on-error: true`, so even with the enforcement
  plugin active, a failing enforced test does not block a merge. The delivered code is
  correct; the operational guarantee requires BP-1200b to be fixed first.

## Knowledge Gaps Found

- Globally-registered pytest plugins (loaded via `pytest.ini addopts`) affect every
  subprocess pytest invocation launched with `--config-file=<repo_root>/pytest.ini`. When
  merging a long-lived branch into a fast-moving main, a dead `conftest.py` added at the
  worktree root can shadow `tests/conftest.py` and break unrelated tests' `from conftest
  import` statements — this is only caught by a full-suite regression diff against an
  origin/main baseline, not by the epic's own per-ticket suite.

- The CI invocation flags must be audited against any globally-registered pytest plugin's
  guarantees. A plugin designed to continue-through-collection-errors is neutralised by
  the `-x` flag in the CI call, yet per-ticket tests never see this because they
  construct their own subprocess calls. Neither the test-writer nor the pr-reviewer
  template includes a "check CI flags for plugin-defeating interactions" step.

- finalize-feature.js resolves the target branch from `args` only when `typeof args ===
  'string'`. Passing `{branch: "EPIC-Name"}` as the argument object causes fallback to
  CWD detection and fails with "must be run from a feature branch (detected: main)". The
  slash-command example showing `{ branch: "..." }` is misleading.

- finalize-feature.js does not `git push` the local branch before executing
  `gh pr merge`. Any local-only commit made after the last push (e.g. a post-review fix
  committed with "finalize will handle the push") is silently absent from the merged PR
  head. The fix is to push the feature branch to origin and verify `git log origin/HEAD`
  == `git log HEAD` before invoking finalize.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).

## Unresolved Feedback

There are 42 unresolved feedback entries in feedback.jsonl. These span multiple epics
(the corpus is global and no per-epic resolution is tracked). Run `/feedback-review` to
triage them before closing the epic branch.

## Proposed Improvements

### KI-1: Push feature branch before invoking finalize or merging the PR

**Proposed Knowledge Item text:**

finalize-feature.js does NOT `git push` the local branch before merging. It invokes
`gh pr merge` against the ORIGIN PR head. Any local-only commit (e.g. a post-review fix
made with "finalize will handle the push") is silently absent from the merge to main.

Before invoking `/finalize-feature` or merging a PR, always:
1. `git push origin HEAD` to ensure the branch is current on origin.
2. Verify: `git log origin/<branch> -1` == `git log HEAD -1` (same SHA).
3. Never rely on finalize to push — it will not.

**Routing:** `CLAUDE.md-toc` → new subsection `### Pre-finalize: verify origin HEAD matches local HEAD` added to the existing Pre-Drive Checklist section.

**Proposed diff (CLAUDE.md — append under the Pre-Drive Checklist section, before the closing `### Commit agent in batch-drive mode` subsection):**

```diff
+### Pre-finalize: verify origin HEAD matches local HEAD
+
+**What to check:** Before invoking `/finalize-feature` or manually merging the epic PR,
+confirm that the local branch and the origin PR head are in sync.
+
+```bash
+# Should output identical SHAs:
+git log HEAD -1 --format="%H %s"
+git log origin/<branch> -1 --format="%H %s"
+```
+
+**Why this matters:** `finalize-feature.js` merges via `gh pr merge` against the ORIGIN
+PR head — it does NOT `git push` before merging. A post-review fix committed locally
+with "finalize will handle it" is silently dropped from the merged commit. Observed
+during EPIC-TrustworthyTestGate finalization, 2026-07-08.
+
+**Fix:** `git push origin HEAD` to sync the branch, then re-verify.
```

---

### KI-2: finalize-feature.js requires a plain string arg, not an object

**Proposed Knowledge Item text:**

finalize-feature.js resolves the target branch by testing `typeof args === 'string'`.
Invoking it as `finalize-feature({branch: "EPIC-Name"})` causes it to fall back to CWD
detection and error with "must be run from a feature branch (detected: main)". The
slash-command documentation's `{ branch: "..." }` example is misleading.

Pass the epic name as a plain string: `finalize-feature("EPIC-TrustworthyTestGate")`.

**Routing:** `CLAUDE.md-inline` — short universal fact; fits in one bullet under the
Pre-Drive Checklist or in a new "Finalize" section.

**Proposed diff (CLAUDE.md — add note to the `### Commit agent in batch-drive mode`
section or as a new standalone note):**

```diff
+### finalize-feature.js — pass epic name as a plain string
+
+`finalize-feature.js` resolves the target branch only when `typeof args === 'string'`.
+Invoking it with an object (`{branch: "EPIC-Name"}`) falls back to CWD detection and
+errors with "must be run from a feature branch (detected: main)".
+
+**Right:** `/finalize-feature EPIC-TrustworthyTestGate`
+**Wrong:** `/finalize-feature {branch: "EPIC-TrustworthyTestGate"}`
+
+(Source: EPIC-TrustworthyTestGate finalization, 2026-07-08.)
```

---

### KI-3: Full-suite regression diff for stale branches before merge

**Proposed Knowledge Item text:**

For branches that are far behind main (many merge commits), validate the merged state
against an origin/main baseline before declaring done. A dead `conftest.py` added by
the epic at the repo root can shadow `tests/conftest.py` and break unrelated tests'
`from conftest import` statements — this breakage is not visible in the epic's own
per-ticket tests and only appears in a full-suite run that compares against the baseline.

Procedure:
1. On `origin/main`, capture baseline: `python -m pytest unit_tests/ -q 2>&1 | tee /tmp/baseline.txt`
2. On the feature branch (after merge simulation), capture: `python -m pytest unit_tests/ -q 2>&1 | tee /tmp/branch.txt`
3. Diff the two outputs: `diff /tmp/baseline.txt /tmp/branch.txt` — any new FAILED lines are regressions to fix before merge.

**Routing:** `CLAUDE.md-toc` → extend the existing
`### Full test suite + ruff at epic-finalize (before merge)` subsection with a new
"baseline regression diff" step.

**Proposed diff (CLAUDE.md — extend the existing "Full test suite + ruff at epic-finalize" subsection):**

```diff
 **Why this matters:** During EPIC-WorktreeQualityGateGuard (2026-07-06), two defects
 passed per-ticket sign-off but were caught only by the full run...
 (Source: EPIC-WorktreeQualityGateGuard retrospective KI-3, 2026-07-06.)

+**Additional step for branches far behind main:** When the feature branch is more than
+~50 commits behind `origin/main`, run a baseline regression diff before declaring done:
+
+```bash
+# Step A: capture baseline from a clean origin/main checkout or worktree
+python -m pytest unit_tests/ -q 2>&1 | tee /tmp/baseline_main.txt
+
+# Step B: on the feature branch (after merging origin/main into it), capture:
+python -m pytest unit_tests/ -q 2>&1 | tee /tmp/branch_merged.txt
+
+# Step C: any new FAILED lines are regressions introduced by the merge:
+diff /tmp/baseline_main.txt /tmp/branch_merged.txt
+```
+
+**Why:** A root `conftest.py` added by the epic can shadow `tests/conftest.py` and break
+unrelated tests' `from conftest import` statements — invisible to per-ticket tests, only
+caught by a cross-suite diff. Observed in EPIC-TrustworthyTestGate finalization, 2026-07-08.
```

---

### KI-4: Audit CI invocation flags for plugin-defeating interactions

**Proposed Knowledge Item text:**

A globally-registered pytest plugin loaded via `pytest.ini addopts` is active for every
subprocess pytest call that uses `--config-file=<repo_root>/pytest.ini`. However, the
same `pytest.ini` that loads the plugin may cause the plugin's guarantee to be silently
defeated by another flag in the CI invocation.

Concrete example: the collection-isolation plugin guarantees every loadable file runs even
when one import fails. The CI workflow's `-x` (`--exitfirst`) flag aborts the suite at the
first failure — defeating the guarantee entirely. The per-ticket tests never see this
because they construct their own subprocess calls without `-x`.

Before merging any epic that ships a globally-registered pytest plugin, add a step to the
adversarial code review checklist: "Do any flags in `.github/workflows/ci.yml`'s pytest
invocation defeat this plugin's stated guarantee?"

**Routing:** `CLAUDE.md-toc` → extend the existing
`### Real-artifact behavioral spot-check before declaring done` subsection with a
CI-flags audit note.

**Proposed diff (CLAUDE.md — extend the "Real-artifact behavioral spot-check" subsection):**

```diff
 (Source: EPIC-PhantomDoneFilesTouched retrospective KI-1, 2026-07-07.
 See also user-memory feedback_spotcheck_real_data_format.)

+**Additional check for globally-registered pytest plugins:** When the epic ships a
+plugin loaded via `pytest.ini addopts`, audit `.github/workflows/ci.yml`'s pytest
+invocation flags for plugin-defeating interactions before declaring done.
+
+Example: a collection-isolation plugin (guarantees every loadable file runs) is silently
+defeated by `-x` / `--exitfirst` in the CI call — the CI suite aborts at the first
+failure before isolation takes effect. Per-ticket subprocess tests do not see `-x` and
+pass green. The real-CI code path is the only context where the defeating interaction
+is observable.
+
+Checklist question: "Do any flags in `ci.yml`'s pytest invocation defeat this plugin's
+stated guarantee?" Add a regression guard test (e.g. `test_ci_invocation_isolation.py`)
+that asserts the CI flags do NOT include any defeating option.
+
+(Source: EPIC-TrustworthyTestGate H-1 post-merge fix, 2026-07-08, commit 2a377f91.)
```

---

### KI-5: CI pytest job is continue-on-error: true (BP-1200b)

**Proposed Knowledge Item text:**

The CI "Test suite (pytest)" job is configured with `continue-on-error: true` (tracked
as BP-1200b). Even when the AC-status enforcement plugin fires and marks tests as failing,
the CI job does not block merges. The TQ-100 enforcement guarantee is operationally
inert until BP-1200b is fixed.

**Routing:** `memory-project` — project-context fact about a known CI configuration state
that should persist across sessions.

**Proposed new memory file:**
`/home/henzeh/projects/leafcutter/finalize-ttg-artifacts/memory/project_ci_pytest_continueonfailure.md`

```diff
+# CI pytest job: continue-on-error: true (BP-1200b)
+
+The "Test suite (pytest)" CI job is configured with `continue-on-error: true`.
+Consequence: even when tests fail (including tests enforced by the TQ-100
+AC-status plugin), the CI job does not block PR merges.
+
+The TQ-100 enforcement guarantee (AC-status-gated test enforcement) is
+operationally inert in CI until BP-1200b is resolved.
+
+Tracked: BP-1200b (open as of 2026-07-08).
+(Source: EPIC-TrustworthyTestGate retrospective L-4, 2026-07-08.)
```
