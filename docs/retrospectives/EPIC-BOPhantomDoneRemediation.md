---
title: 'Retrospective: EPIC-BOPhantomDoneRemediation'
date: 2026-07-15
epic_pr: 281
squash_commit: 50e28cc1
created: '2026-07-15'
last_updated: '2026-07-15'
type: tutorial
status: active
components:
- build_orchestration
description: 'Overview of Retrospective: EPIC-BOPhantomDoneRemediation.'
---
# Retrospective: EPIC-BOPhantomDoneRemediation
Date: 2026-07-15
Epic duration: 2026-07-14 to 2026-07-15
Merged: PR #281, squash commit 50e28cc1

## Summary

This epic resolved approximately 40 phantom-done acceptance criteria in the
Build Orchestration component cluster, discovered by the 2026-07-14 BO-AC
implementation audit. The ACs had green test sign-offs but the underlying code
was either orphaned (never invoked), dead (helpers untested at the call path),
or implemented the _opposite_ of the specified behaviour. Five tickets each
targeted a single root-cause fix cluster: wiring the commit classifier/learner
library into the commit agent (BO-1100, 21 ACs), wiring six dead probe helpers
into `run_checks()` and flipping the fail-open gate to fail-closed (BO-1700, 10
ACs), requiring `change_target`/`risk_surface` fields and rejecting null/empty
values (BO-600/610/630, 4 ACs), switching the done-folder prohibition from
presence-based to move-based detection with `99_done` support (BO-400, 3 ACs),
and implementing glob resolution for `it_requirements` reference patterns
(BO-2000, 2 ACs).

All five tickets closed on 2026-07-14. The epic was driven as a coordinator-
supervised sequential batch (not via the automated epic-supervisor), required
approximately 20 implementation commits before the final squash merge, and
exposed four coordinator-level process failures that are more significant than
the per-ticket friction: the build-feature workflow returning "epic complete"
while a ticket's implementation was uncommitted; a parallel test-backfill epic
(PRs #282/#290) writing green tests against the pre-fix broken code (creating a
merge conflict at finalize); a unit-test false pass for BO-400c-3-i that only
behavioral verification against a real git working tree could detect; and two
invocations of finalize-feature that required manual PR merge as a fallback.

## Metrics

### Phase Agent Events (blocker events = status:blocker comments per phase)

| Phase | Signed Off | Blocker Events | Not Needed |
|-------|-----------|----------------|------------|
| architect-review | 3 | 0 | 2 |
| test-writer | 5 | 0 | 0 |
| python-coder | 5 | 1 | 0 |
| sql-coder | 0 | 0 | 5 |
| test-runner | 5 | 1 | 0 |
| documentation-expert | 0 | 0 | 5 |
| pr-reviewer | 5 | 3 | 0 |
| commit | 5 | 0 | 0 |
| pull-request | 5 | 1 | 0 |

pr-reviewer was the most productive gate: it surfaced 4 high-confidence
findings across 3 tickets that unit tests had not caught (BO-1700 hooks-dir
resolution, BO-1700 freshness return value, BO-600 empty-list asymmetry, BO-400
production call-site not threading `old_path`).

## Category Breakdown (Feedback System)

No structured feedback is available for this epic. The worktree was driven
without an established `.leafcutter/feedback_categories.yaml`, causing all
`submit_feedback.py` calls to silently fail with `(submit-failed)` — visible
in several ticket comment feedback IDs. The 123 entries in `feedback.jsonl`
predate this epic and belong to prior epics.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 5 |
| Completed tickets | 5 |
| AC coverage (leaf) | ~40 across BO-1100/1700/600/400/2000 |
| Epic-specific implementation commits | ~20 (squashed to 50e28cc1) |
| Epic PR | #281 |
| Blocker comments (status: blocker) | 6 |
| Handoff comments (status: handoff) | 0 |
| Feedback entries with submit-failed | 3 (sink not established in worktree) |
| Subagent quality supervisor entries | 0 (pre-dates EPIC-SupervisorFeedback) |

Note: `extract_epic_facts.py` was not found in this repo; the table above is
derived from ticket comments and git log.

## What Went Well

- All five tickets completed the same day they were created (2026-07-14).
  The "disjoint files → fully parallel" design in `Master_Plan.md` held; no
  cross-ticket locking was needed.
- pr-reviewer functioned as the primary correctness gate. In three of five
  tickets it caught production-path defects that all prior phases (test-writer,
  python-coder, test-runner) had missed — the pattern where a unit test passes
  in isolation while the production call path omits the new parameter.
- Ticket 01 (BO-1100): test_drift was detected and cleanly classified by
  python-coder, which stopped short rather than break pre-existing passing
  tests. The respawn-test-writer → respawn-python-coder recovery pattern worked
  as designed. All 77 tests ended green.
- Ticket 03 (BO-600): the inverted tests (`test_null_change_target_passes`,
  `test_absent_risk_surface_passes`) that asserted the opposite of the AC were
  correctly identified and rewritten to assert the correct behavior. The
  behavioral spot-check against a real on-disk ticket confirmed the guard fires.
- Ticket 05 (BO-2000): the cleanest ticket. No phase blockers; the phantom
  `# covers:` labels were removed from the unrelated dispatch-string test and
  placed on a test that genuinely exercises path resolution. Three medium
  findings from pr-reviewer were all pre-existing limitations, none correctness
  blockers.
- The coordinator's real-time detection of the orchestration phantom-done
  (journal.jsonl + git status per ticket) prevented an incomplete epic from
  being declared done and pushed to origin prematurely.

## Friction Points

- **Ticket 01 — test_drift loop (2 extra agent dispatches).** The legacy
  `TestPatternsConfigFileExists` test class asserted the old dict schema while
  AC BO-1100c-1 required a top-level JSON array. python-coder's first pass
  correctly refused to implement the array schema (it would have broken 4 green
  tests). architect-review had to be re-dispatched to widen the scope of stale
  tests before test-writer could fix them. This is the canonical test_drift
  failure: tests that originally validated the wrong behaviour survived as "green"
  and blocked the correct implementation.

- **Ticket 02 — uncommitted implementation when build-feature claimed done
  (orchestration-level phantom done).** The `/build-feature` workflow returned
  "5 tickets completed / epic complete" while ticket 02's implementation
  (`verify_precommit_active.py`, `building-epics/SKILL.md`) was in the working
  tree only — uncommitted. The failure ladder (respawn python-coder for H-1/H-2)
  hit its retry cap and the batch loop exited claiming success. Detection required
  manually reading `journal.jsonl` + running `git status` per ticket. The commit
  for ticket 02 was issued by the coordinator as a manual intervention, not by the
  automated pipeline.

- **Ticket 02 — pr-reviewer H-1/H-2 production-path gaps.** `run_checks()`
  called `resolve_hooks_path(cwd)` at line 615 but then `check_c_git_hook` still
  re-resolved the hooks path internally via `_resolve_git_commondir` — so the
  external resolution was ignored (H-1 / BO-1700h-3). `check_hook_freshness()`
  return value was silently discarded — stale hooks never populated
  `failing_checks` (H-2 / BO-1700h-1). Both passed all unit tests because the
  tests called the helpers directly, not via `run_checks()`.

- **Ticket 03 — asymmetric empty-list guard.** `_check_change_target` had an
  empty-list guard (`if not value: error`) but the identically structured
  `_check_risk_surface` did not. All 22 tests passed because no subtest exercised
  `risk_surface: []`. pr-reviewer caught the asymmetry on the first review pass.
  Required one targeted python-coder fix + test addition before sign-off.

- **Ticket 04 — production call-site not threaded.** The canonical
  CLAUDE.md "Function Signature Extension — Call-Site Audit Required" violation:
  `_check_done_folder_prohibition` gained the `old_path` parameter and all unit
  tests called it correctly, but the single production call site at
  `check_ticket_signoff_parity.py:143` still called
  `_check_done_folder_prohibition(ticket_path)` without `old_path`. BO-400c-3-i
  (in-place edit false positive suppression) remained broken in production despite
  green unit tests. The fix required a second python-coder dispatch to add
  `_build_rename_map()` and thread `old_path` through `_validate_ticket()` →
  `_validate_ticket_content()` → the call site. Behavioral verification against
  a real git working tree (not a synthetic fixture) was the only way to confirm
  the production path actually suppressed the false positive.

- **Parallel test-backfill collision (PRs #282/#290).** While this epic was in
  flight, a separate backfill effort wrote "green" test coverage for the same
  BO-400 and BO-1100 ACs against the _pre-fix_ (broken) code and merged to main
  first. At finalize, the epic PR conflicted with main on two test files. The
  resolution was a union merge (keeping both the backfill tests that pass on
  broken code and the new tests that pass on fixed code). This introduces the
  risk that the backfill tests — which were authored against the wrong behavior —
  now pass silently on main alongside the correct tests.

- **Finalize fragility.** The automated finalize-feature workflow was disrupted
  twice mid-run. Step 0 baseline degraded on one invocation. Manual PR merge
  via `gh pr merge` was more reliable than re-invoking finalize. The worktree
  lacked `.leafcutter` symlinks, so all pre-commit hooks silently skipped during
  the drive.

## Knowledge Gaps Found

- The orchestration-level phantom-done failure mode (batch loop claims success
  after retry-cap exhaustion, independent of ticket state) is not documented as a
  pre-merge verification step in CLAUDE.md. The memory entry
  (`project_build_feature_false_epic_complete.md`) exists but is only visible to
  the user, not to agents.

- Backfilling tests against unimplemented/broken code is not documented as a
  phantom-done vector. The existing repo guidance focuses on code being orphaned
  or tests passing on incorrect fixtures; it does not address the case where a
  parallel branch writes tests that deliberately pass on the broken behaviour and
  merges before the fix.

- The "Function Signature Extension — Call-Site Audit Required" rule in CLAUDE.md
  correctly identifies the risk but does not extend it to the test isolation case:
  tests that call the extended function directly always pass (they use the new
  parameter), while the production call chain omits it. The behavioral spot-check
  rule covers the fixture bias but not the call-path gap explicitly.

- The worktree `.leafcutter` bootstrap gap (pre-commit hooks silently skip) is
  documented in CLAUDE.md but the feedback sink gap (`feedback_categories.yaml`
  absent → all `submit_feedback.py` calls silently fail) is not flagged as a
  parallel check item.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors pre-date
EPIC-SupervisorFeedback or no adjudication events were recorded during this
drive). The drive was conducted as a coordinator-supervised sequential batch,
not via the automated epic-supervisor with its adjudication ladder.

## Unresolved Feedback

There are 123 unresolved feedback entries in feedback.jsonl.
Run `/feedback-review` to triage them before closing the epic branch.

---

## Proposed Improvements

---

### KI-1: Build-Feature Epic-Complete Verification Step

**Proposed Knowledge Item:**

Add a mandatory post-drive verification step to the Pre-Drive Checklist (or
a new "Post-Drive Checklist" section) in CLAUDE.md:

> **Do not trust the build-feature "epic complete" payload.**
> Before declaring an epic done, independently verify each ticket:
> (a) `journal.jsonl` shows a commit sign-off entry for that ticket;
> (b) `git log --oneline` shows the ticket's implementation commit(s) on the
> branch (not just in the working tree);
> (c) `git status` shows no uncommitted changes to files in the ticket's
> `files_touched` list.
> The failure mode is: the retry-cap loop in the batch orchestrator exits after
> exhausting retries, returns `tickets_completed=N / epic_complete=true`, while
> a ticket's implementation files remain uncommitted in the working tree.

**Routing (route-knowledge Step 5 — long universal project rule):**

Route to `CLAUDE.md-toc` — the content warrants its own named section in
`docs/how-to/post-drive-verification.md` with a one-line link entry in
CLAUDE.md's Pre-Drive Checklist table (or a new Post-Drive Checklist table).

**Proposed diff:**

```diff
--- a/docs/how-to/post-drive-verification.md  (new file)
+++ b/docs/how-to/post-drive-verification.md
@@ -0,0 +1,40 @@
+# How-To: Post-Drive Verification Before Declaring Epic Done
+
+Run through these checks after `/build-feature` (or a manual batch drive)
+reports "epic complete". Do NOT push the epic PR or merge to main until
+all checks pass.
+
+## 1 — Do not trust the success payload
+
+`/build-feature` returns `tickets_completed=N / epic_complete=true` when
+the batch loop exits — including when it exits because the retry cap was
+exhausted. The payload is not a reliable signal that all tickets are committed.
+
+## 2 — Verify each ticket independently
+
+For each ticket in the epic:
+
+```bash
+# (a) Implementation commit on the branch:
+git log --oneline EPIC-<name> | grep -i "<ticket keyword>"
+
+# (b) No uncommitted implementation files:
+git -C <worktree-root> status --short
+
+# (c) journal.jsonl shows commit sign-off (if telemetry is enabled):
+grep '"type":"commit"' debugging/logs/journal.jsonl | grep '<ticket-id>'
+```
+
+If `git status` shows modified or untracked files matching the ticket's
+`files_touched`, the implementation is uncommitted — the batch claimed
+done prematurely.
+
+## 3 — Recover from a partially-committed epic
+
+If one or more tickets are uncommitted:
+1. Read the ticket's `## Comments` to identify the last successful phase.
+2. Identify uncommitted files via `git status`.
+3. Stage and commit them manually (with coordinator-approved
+   `COMMIT_AGENT_MODE=1`).
+4. Re-run `pr-reviewer` and `pull-request` phases for the affected tickets.
+
+**Source:** EPIC-BOPhantomDoneRemediation retrospective, 2026-07-15.
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -<Pre-Drive Checklist line>+1 @@
+### Post-Drive Verification (MANDATORY before merge)
+
+After `/build-feature` reports "epic complete", run the per-ticket
+verification checks documented in
+[docs/how-to/post-drive-verification.md](docs/how-to/post-drive-verification.md).
+The "epic complete" payload is not a reliable signal — the batch loop exits on
+retry-cap exhaustion regardless of whether tickets are committed.
```

---

### KI-2: Green-on-Broken-Code Test Backfill is a Phantom-Done Vector

**Proposed Knowledge Item:**

> Backfilling tests against unimplemented or pre-fix (broken) code is a
> phantom-done vector. A test written to pass on the broken behavior will
> merge to main, conflict with the remediation branch at finalize (both
> branches touch the same test file), and survive in the merged result
> alongside the correct tests — leaving a permanently misleading green test
> in the suite.
>
> Before initiating a test-backfill epic or PR, confirm the behavior the
> target ACs specify is actually present in main. If the fix has not yet
> landed, coordinate the backfill with the remediation so tests are written
> against the corrected behavior only.

**Routing (route-knowledge Step 5 — CLAUDE.md-toc / inline):**

This is a short enough rule (3 sentences) to fit inline in CLAUDE.md under
"Implementation Conventions", but its context (coordinating with active
remediation epics) makes a standalone note preferable.

Route to `CLAUDE.md-inline` under the Implementation Conventions section.

**Proposed diff:**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ Implementation Conventions section @@
+### Test Backfill — Confirm Fix Is Live Before Writing
+
+Backfilling test coverage for ACs whose implementation fix is not yet on
+`main` is a phantom-done vector. Tests written to pass on the pre-fix
+(broken) code merge green, then conflict with the remediation PR at
+finalize, and survive in the merged result alongside the correct tests.
+
+**Rule:** Before opening a test-backfill PR for a set of ACs, run the
+targeted behaviour from `origin/main` and confirm it produces the correct
+output. If the fix has not yet merged, coordinate: either merge the fix
+first, or include the fix in the same PR as the tests.
+
+(Source: EPIC-BOPhantomDoneRemediation retrospective, parallel PRs #282/#290
+vs #281, 2026-07-15.)
```

---

### KI-3: Production Call-Path Verification for Signature Extensions

**Proposed Knowledge Item (refinement of existing CLAUDE.md rule):**

The existing "Function Signature Extension — Call-Site Audit Required" rule
covers updating call sites when a function signature is extended. This adds a
behavioral verification clause: unit tests that call the extended function
directly always pass (they use the new parameter), while the production call
chain may silently omit it. The spot-check must exercise the full production
entry point (`main()` or the pre-commit hook runner), not just the extended
function in isolation.

**Routing (route-knowledge Step 4 — CLAUDE.md-inline, amendment to existing rule):**

Route to `CLAUDE.md-inline` as an appended paragraph to the existing
"Function Signature Extension — Call-Site Audit Required" convention.

**Proposed diff:**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ Function Signature Extension — Call-Site Audit Required @@
 3. **Include call-site updates in the same commit** as the signature change.

 A function whose signature is extended but whose callers still use the old
 signature silently exercises the legacy code path. This is not catchable by
 tests that test the function directly — the tests pass against the function
 in isolation while every real call path uses the old signature.
+
+**Behavioral verification is required in addition to the call-site audit.**
+After confirming call sites pass the new parameter, exercise the full
+production entry point (`main()` or the pre-commit hook runner) against a
+real on-disk artifact — not a synthetic fixture that calls the function
+directly. Unit tests that call the extended function with the new parameter
+always pass; only the production path test reveals whether the parameter
+actually flows end-to-end.
+
+(Source: EPIC-BOPhantomDoneRemediation ticket 04, BO-400c-3-i, 2026-07-15 —
+`_build_rename_map` threaded correctly but required real git working-tree
+verification to confirm the in-place edit false positive was suppressed.)
```

---

### KI-4: Worktree Feedback Sink as a Pre-Drive Check Item

**Proposed Knowledge Item:**

The CLAUDE.md Pre-Drive Checklist already documents the feedback sink
(`agent_telemetry.jsonl`) and the worktree pre-commit config as mandatory
pre-drive checks. This adds the `feedback_categories.yaml` as a parallel
required file.

**Routing (route-knowledge Step 4 — CLAUDE.md-inline, amendment to existing
"Feedback sink reachable" checklist item):**

**Proposed diff:**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ Feedback sink reachable @@
 **Also verify `feedback_categories.yaml` is accessible.** The `submit_feedback.py`
 script requires this file in the worktree's `.leafcutter/` directory. When
 absent, all agent feedback calls fail silently with `(submit-failed)`, making
 the retrospective's quantitative category breakdown unavailable.

 Check:
 ```
 ls <worktree-root>/.leafcutter/feedback_categories.yaml
 ```
 If the command fails (`No such file or directory`), the file is missing.

 Fix: symlink or copy from the main tree's `.leafcutter/` alongside the
 `.pre-commit-config.yaml` fix in the section below.
-(Source: EPIC-ComputedQualityGates FP-5, 2026-07-07.)
+(Source: EPIC-ComputedQualityGates FP-5, 2026-07-07;
+confirmed again in EPIC-BOPhantomDoneRemediation where 3 of 5 tickets
+produced (submit-failed) feedback IDs throughout the entire drive, 2026-07-15.)
```

Note: this is a source-attribution amendment only (the rule already exists).
The primary new check worth adding is that the feedback sink gap also affects
retrospective quantitative data — already stated in the existing rule. No new
text block needed; approve only if the source-attribution update is useful.

---

*All proposed rule changes above are diffs for user approval — none have been
applied. Type "yes" to apply an item, "skip" to skip, or "edit" to revise.*
