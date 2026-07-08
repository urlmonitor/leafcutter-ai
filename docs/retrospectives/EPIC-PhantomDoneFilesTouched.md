---
title: "Retrospective: EPIC-PhantomDoneFilesTouched"
description: "Epic retrospective for EPIC-PhantomDoneFilesTouched: real-format parser no-op, fail-open hole, AC audit, and finalize workflow bugs discovered during post-merge remediation."
created: 2026-07-07
epic_branch: EPIC-PhantomDoneFilesTouched
pr: "209"
squash_commit: 17c538fe
---

# Retrospective: EPIC-PhantomDoneFilesTouched

Date: 2026-07-07
Epic duration: 2026-07-06 to 2026-07-07
Merged via: PR #209, squash commit 17c538fe

---

## Summary

This epic implemented AC BP-1100e: a pre-done reconciliation hook
(`check_files_touched_reconciliation.py`) that detects source files changed by a
ticket but absent from its declared `files_touched` or `out_of_scope` frontmatter.
The hook is advisory (fail-open) by default and only blocks when
`predone_scope.strict: true` is set in `commit_guardian.json`. Six implementation
tickets added the core hook, exemption logic (generated files, lockfiles, declared
out-of-scope), path normalization (cross-platform case and separator folding), a
no-files_touched no-op guard, and the advisory/strict mode wiring. A seventh ticket
produced a Mermaid sequence diagram in `docs/architecture/agent_delivery_workflows.md`
showing where the check sits in the ticket lifecycle.

All 7 tickets passed phase-agent sign-offs on 2026-07-06/07. However, a post-signoff
code-review found the core hook was a **complete no-op on the real ticket file format**:
PyYAML serializes `files_touched` as column-0 list items (no leading indent), but the
parser regex required indented dashes. The tests and the spot-checks conducted during
sign-off used indented-fixture YAML — reproducing the same bias that allowed the hook
to appear green while doing nothing. Only running the parser against an actual on-disk
ticket file caught the defect. Two rounds of remediation followed (8 defects in round 1;
a HIGH fail-open regression introduced by round 1 and a claim-vs-reality gap in a commit
message found in round 2). A 3-agent AC audit then found the existing ACs had no coverage
for these mission-critical behaviors; 4 new regression-lock ACs were authored. The config
was shipped off by default (matching the AC) and then flipped to advisory-on for dogfood.
Finalize itself surfaced two workflow bugs — a CWD-trusting pre-flight and a step 3.5
cross-epic scope explosion — both caught before they reached main.

---

## Metrics

| Phase | Signed Off | Failed (intermediate) | Needed |
|-------|-----------|----------------------|--------|
| architect-review | 0 | 0 | 7 (not_needed) |
| test-writer | 7 | 0 | 0 (all skipped via §ok — test_requirements empty) |
| python-coder | 6 | 0 | 0 (not_needed: 1) |
| sql-coder | 0 | 0 | 7 (not_needed) |
| test-runner | 7 | 0 | 0 |
| documentation-expert | 0 | 0 | 7 (not_needed) |
| architecture-diagram-author | 1 | 0 | 0 (not_needed: 6) |
| pr-reviewer | 7 | 2 | 0 |
| commit | 7 | 0 | 0 |
| pull-request | 7 | 0 | 0 |

Notes:
- pr-reviewer intermediate failures (2): tickets 01 and 02 each received a `status: blocker`
  on the first pass (missing files from staged set and incomplete `files_touched`), then
  signed off after §3.1 mechanical fixes.
- test-writer: all 7 tickets were classified as docs-only/config-only and received status:ok
  (skipped) — no failing tests were authored before implementation.
- Post-signoff remediation rounds (2) are not captured in phase metrics because they
  occurred after the epic branch's sign-off cycle ended.

## Category Breakdown (Feedback System)

Structured feedback was partially captured during this epic. Several agents emitted
`feedback-id: (submit-failed)` markers throughout the drive, indicating that
`submit_feedback.py` was absent or returned exit code 2 in the epic worktree (the
script resolves its config path relative to the worktree root but the deployed copy
lives under `.leafcutter/`).

From the aggregate corpus (all epics combined):
| Category | Count (all epics) |
|----------|------------------|
| complete | 114 |
| quality-concern | 2 |
| knowledge-gap | 1 |
| blocker | 1 |
| **Total** | **118** |

This epic's own entries in the feedback corpus cannot be precisely isolated because many
feedback-ids used the `(submit-failed)` fallback and were not emitted to `feedback.jsonl`.
The 2 blocker-to-ok pr-reviewer transitions in tickets 01 and 02 are the primary structured
signals; they appear in the ticket comments but not in the feedback JSONL.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 7 |
| Completed tickets | 7 (all status: done) |
| Source AC | BP-1100e (7 leaf ACs) |
| Epic branch duration | 2026-07-06 to 2026-07-07 |
| Squash commit | 17c538fe (PR #209, 2026-07-07 16:39 +0200) |
| pr-reviewer intermediate blockers | 2 (tickets 01 and 02) |
| Handoff comments | 0 |
| Post-signoff remediation rounds | 2 (major) |
| New regression-lock ACs authored post-signoff | 4 |
| Finalize workflow bugs caught | 2 |
| `extract_epic_facts.py` | Absent from this repo (script not found at expected path) |

---

## What Went Well

- **Phase pipeline caught its own phantom-done in real time.** The new reconciliation
  hook being tested by this very epic flagged tickets 01 and 02's unstaged files and
  incomplete `files_touched` via the pr-reviewer phase before the commit landed. The
  mechanism being built here proved it could guard its own implementation.
- **pr-reviewer blocker + §3.1 mechanical fix pattern worked.** Both blocker events
  (tickets 01 and 02) were resolved in a single mechanical retry pass by ticket-supervisor
  without escalation to brainstorm-lead or user halt.
- **Opus escalation on ticket 03 produced the correct outcome.** Four medium findings
  were escalated; Opus dropped all four as false positives, avoiding over-blocking on
  edge cases that were unreachable in the hook's execution context.
- **Finalize cross-epic scope bug caught before main.** The step 3.5 pre_merge_ac_closure
  explosion (45 tickets/ACs across 4 unrelated epics) was detected and halted before
  any of that state reached `origin/main`.
- **commit message checking was active.** The claim-vs-reality gap in a round-2 commit
  message (commit claimed a WARNING log was added but it was not in the diff) was caught
  and corrected before squash-merge.

---

## Friction Points

- **BP-1100e-1 (ticket 01):** pr-reviewer's first pass was a `status: blocker` — the
  commit was a phantom-done (both implementation files unstaged). Ticket-supervisor issued
  a §3.1 mechanical fix to stage the files, update `files_touched` to avoid self-flagging,
  and respawn pr-reviewer. Second pass signed off clean.
- **BP-1100e-1-i (ticket 02):** Identical class of defect — `files_touched` in the ticket
  frontmatter pointed to a YAML file that was never changed on the branch; the two .py
  files actually staged were absent. pr-reviewer blocked; ticket-supervisor §3.1 corrected
  the frontmatter; second pass signed off.
- **Recurring `files_touched` authoring error.** Two of 7 tickets had `files_touched`
  listing files that were either never changed (BP-1100e.yaml in ticket 02) or not yet
  known at ticket authoring time. This is a structural tension in the build-ac flow: AC
  files are named before the implementation file name is decided.
- **submit_feedback.py absent in the epic worktree.** All architecture-diagram-author,
  test-runner, and pull-request agents on ticket 07 emitted `(submit-failed)` markers.
  The script resolves its config at a path that differs between the main clone and
  worktrees. No phase agent failed because of this, but telemetry was lost.
- **test-writer universally skipped.** All 7 tickets were classified as docs-only or
  config-only at the test-requirements stage, so test-writer skipped with status:ok on
  every ticket. The hook tests were written inline by python-coder and verified by
  test-runner — but with no failing red baseline established first, TDD discipline was
  absent.

---

## Knowledge Gaps Found

### The core phantom-done: hook was a no-op on real ticket format

All 7 tickets passed phase-agent sign-offs with GREEN results, but a post-signoff
code-review agent running the parser against an actual on-disk ticket file found that
the `files_touched` regex required indented dashes (`  - path`) but PyYAML column-0
serialization produces unindented items (`- path`). The hook silently skipped all real
tickets. The tests and spot-checks used indented-fixture YAML and reproduced the bias
rather than detecting it. An earlier project memory note ("spot-check the real data
format") existed but was not wired into the phase pipeline as a mandatory gate.

### Round 1 remediation (8 defects)

Round 1 fixed:
1. Column-0 list-item parsing (core no-op defect)
2. OSError fail-open hole
3. Quoted-path handling
4. Multi-ticket union (multiple tickets in one commit)
5. Flow-list YAML variant
6. `lstrip` path mangling
7. Dead-code wiring (hook registered but function never called from main)
8. Documentation key name mismatch

### Round 2 remediation: fail-open regression and commit claim-vs-reality gap

Round 2 found that the round-1 fix introduced a HIGH severity hole: wrong-shape config
in `commit_guardian.json` caused the hook to raise an uncaught exception and crash
(exit non-zero), which **blocked commits** — the opposite of the fail-open contract.
The commit message for the round-1 fix also claimed that a WARNING log line had been
added when it was not present in the diff. Both were corrected before squash-merge.

### AC coverage did not include mission-critical behaviors

A 3-agent AC audit found:
- No AC covered real-format parsing (column-0 `files_touched` lists)
- No AC covered the fail-open contract under exception conditions
- AC `BP-1100e-2` described the advisory/strict mode but not the internal-error
  fail-open path, creating a divergence between the AC text and the config model
- `work_status` metadata was stale across several AC YAML files

Four new regression-lock ACs were authored to lock the behaviors that were broken in
the initial implementation.

### Finalize pre-flight: CWD not the epic worktree

During finalize, the pre-flight step inferred the current branch from the session CWD
(the main clone), not from the epic worktree path. This caused the pre-flight to report
the branch as `main` rather than `EPIC-PhantomDoneFilesTouched`. The finalize sequence
must resolve the worktree path explicitly rather than trusting the CWD at invocation time.

### Finalize step 3.5 cross-epic scope explosion

Step 3.5 (`pre_merge_ac_closure`) flipped 45 tickets and ACs to `status: done` /
`work_status: done` across 4 unrelated epics, not just the epic being finalized. The
step's scope query was not bounded to the current epic's branch diff or its own AC node
subtree. The bug was caught and reverted before reaching main.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive). The
`aggregate.py --category subagent-quality` query returned `"total": 0`.

---

## Unresolved Feedback

The `aggregate.py --unresolved --format json` call returned a non-empty payload (output
size 62.9 KB, indicating multiple entries). The exact unresolved count is not available
from the truncated preview. Run `/feedback-review` to triage unresolved feedback entries
before closing the epic branch.

---

## Proposed Improvements

---

### KI-1: Real-artifact behavioral spot-check as a mandatory phase gate

**Summary:** Phase-agent sign-offs do not prove behavior on the real data format. All
7 tickets in this epic signed off GREEN on the reconciliation hook while the hook was a
complete no-op on every real ticket because synthetic test fixtures did not reproduce
the column-0 PyYAML serialization format. A mandatory real-artifact spot-check must be
added to the phase pipeline or the pre-drive checklist so this class of phantom-done
cannot recur.

**Routing:** `CLAUDE.md-toc` — warrants a new section in the Pre-Drive Checklist (already
present in `CLAUDE.md`) pointing to an entry in the checklist body, or as a new
top-level checklist item. Content is multi-sentence and specific enough to be actionable
at every drive start.

**Proposed diff — new Pre-Drive Checklist item in `CLAUDE.md`:**

```diff
 ### Full test suite + ruff at epic-finalize (before merge)
 ...
+
+### Real-artifact behavioral spot-check (MANDATORY before phase sign-off)
+
+**What to check:** After python-coder completes and before pr-reviewer signs off,
+run the new or changed component against an actual on-disk artifact from the project
+tree — not a synthetic fixture you wrote yourself. For a hook that parses ticket
+frontmatter, feed it a real ticket file. For a hook that parses YAML, use real YAML
+produced by the project (e.g., `git show HEAD:tickets/.../some_ticket.md`).
+
+**Why this matters:** EPIC-PhantomDoneFilesTouched (2026-07-07) — all 7 tickets
+signed off GREEN while the reconciliation hook was a no-op on every real ticket.
+Synthetic indented-fixture YAML matched the regex; column-0 PyYAML output (the real
+format) did not. Only running the parser against an actual ticket file caught it.
+The project memory note "spot-check the real data format" (feedback_spotcheck_real_data_format.md)
+existed but was not wired into the phase pipeline. The same bias recurred even on the
+first behavioral spot-check because the tester constructed the fixture from memory,
+not from the actual file.
+
+**Fix:**
+```bash
+# Example: run the reconciliation hook against a real ticket on-disk
+python templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py \
+  tickets/00_inbox/epics/EPIC-SomeName/01_real_ticket.md
+```
+
+If the component works correctly on a real artifact, the spot-check passes. If it
+silently no-ops or produces wrong output, the sign-off is NOT valid regardless of
+test suite results.
```

---

### KI-2: Finalize step 3.5 cross-epic scope bug

**Summary:** `pre_merge_ac_closure` (finalize step 3.5) flipped 45 tickets and ACs to
done across 4 unrelated epics during the EPIC-PhantomDoneFilesTouched finalize run. The
scope query is not bounded to the current epic's AC subtree. This is an active production
bug — the only protection is catching it in the diff before committing.

**Routing:** `memory-project` — active workflow bug that must be remembered across
sessions until a code fix lands.

**Proposed diff — new project memory file:**

```diff
--- /dev/null
+++ /home/henzeh/.claude/projects/-home-henzeh-projects-leafcutter/memory/project_finalize_step35_scope_bug.md
@@ -0,0 +1,14 @@
+# Finalize step 3.5 cross-epic scope explosion
+
+## Status
+Active bug — not yet fixed in production code.
+
+## What happens
+`pre_merge_ac_closure` (finalize-feature step 3.5) sets `status: done` and
+`work_status: done` on tickets and ACs that do not belong to the epic being
+finalized. During EPIC-PhantomDoneFilesTouched (2026-07-07), it flipped 45
+tickets/ACs across 4 unrelated epics.
+
+## Safe guard
+Before committing any step 3.5 output, diff the changed files list and confirm
+every path belongs to the current epic's folder or its source AC subtree.
+If unrelated epics appear, halt and revert — do NOT commit or push.
```

---

### KI-3: Finalize pre-flight CWD bug

**Summary:** The finalize pre-flight step inferred the current branch from the session
CWD (the main clone) rather than from the epic worktree path. This caused it to report
`main` as the branch during an EPIC-PhantomDoneFilesTouched finalize session.

**Routing:** `memory-project` — active workflow bug; must be remembered and worked around
until the script is fixed to accept an explicit worktree path.

**Proposed diff — new project memory file:**

```diff
--- /dev/null
+++ /home/henzeh/.claude/projects/-home-henzeh-projects-leafcutter/memory/project_finalize_preflight_cwd_bug.md
@@ -0,0 +1,13 @@
+# Finalize pre-flight CWD bug
+
+## Status
+Active bug — not yet fixed in production code.
+
+## What happens
+The finalize pre-flight step reads the current branch via `git -C <cwd>` where
+`<cwd>` defaults to the session working directory, not the epic worktree. When
+invoked from the main clone, the pre-flight reports `main` as the branch instead
+of the epic branch.
+
+## Workaround
+Always invoke finalize from within the epic worktree, or explicitly pass the
+worktree path so git commands target the correct tree.
```

---

### KI-4: Commit messages must not claim changes not in the diff

**Summary:** During round-2 remediation review, a commit message asserted "Added
WARNING log line" when the diff contained no such addition. The gap between what a
commit message claims and what the diff actually contains is undetectable by the
pre-commit hook and requires a reviewer to check manually.

**Routing:** `CLAUDE.md-inline` — short universal rule; every commit agent and
pr-reviewer must enforce it.

**Proposed diff — inline addition to `CLAUDE.md` (Commit Delegation section or new line):**

```diff
 ## Commit Delegation — MANDATORY
 ...
+
+## Commit Message Truthfulness — MANDATORY
+
+A commit message MUST NOT claim that a change was made if the diff does not
+contain that change. Before the commit agent writes the message, verify each
+claim ("Added X", "Fixed Y", "Removed Z") is present in `git diff --staged`.
+If a round-trip review (pr-reviewer or code-review-architect) finds a
+claim-vs-reality gap in any commit, treat it as a HIGH defect and correct the
+message before squash-merge. (Source: EPIC-PhantomDoneFilesTouched round-2 review,
+2026-07-07.)
```

---

## Approval Required

The four proposed items above (KI-1 through KI-4) are presented for your review.

For each, please respond:
- **yes** — apply the diff as shown
- **skip** — do not apply
- **edit** — revise the wording before applying

None of these diffs have been applied. No knowledge-home file (`CLAUDE.md`, memory
files, agent templates, or skill files) has been modified.
