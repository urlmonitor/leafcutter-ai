---
title: "Build drivers: the ticket-completion write leaves status: done unstaged"
status: todo
components:
  - build_orchestration
created: 2026-10-08
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build-feature
  - epic
  - ticket-lifecycle
last_updated: 2026-10-08
files_touched:
  - scripts/set_ticket_status.py
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/finalize-feature.js
  - templates/agents/status-checker.md
  - templates/skills/build-feature-ops-notes/SKILL.md
  - unit_tests/test_set_ticket_status_no_stage.py  # new
  - unit_tests/workflows/test_completion_write_no_stage.py  # new
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: signed_off
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  status-checker: not_needed
---

# Build drivers: the ticket-completion write leaves status: done unstaged

## Actor / Goal
In order that a /build-feature epic run builds through instead of stopping after its first completed
ticket, we need the driver's completion write to record `status: done` in the ticket file without
staging it, so that the staged-leftovers stop and the next ticket's commit never meet a done ticket.

## Context
- **Observed on DK-400 E1 (2026-10-07, run wf_8e53ea6f-ab6):** batch 1 completed ticket 02; in batch 2
  ticket 03 halted; the dirty read then found ticket 02's record staged with `status: done` and stopped
  the run (`staged_leftovers`), so tickets 04, 07 and 09 never ran.
- **Who stages it:** `writeTicketCompletion` (templates/workflows-js/build-feature.js ~1326-1342, BUG-22,
  and its twin in templates/workflows-js/build-ticket.js ~1163) dispatches status-checker to run exactly
  `python3 scripts/set_ticket_status.py --ticket <path> --status done, with no additional flags`.
  `scripts/set_ticket_status.py` stages the file after a successful write ("stages the file via git add for
  the next commit", line 14; `git add` at ~217). It has no flag to skip that.
- **Why staging hurts on an epic branch:**
  - the epic loop's dirty read (BO-100e-4, user decision F4 option A) stops the run on any staged path
    after a batch with a halt;
  - the commit agent commits what is staged, so the next ticket's commit sweeps the done ticket in, and
    `check-predone-scope` blocks it: it compares a done ticket with the whole epic branch diff, and the E1
    tickets list no source files in `files_touched` (TICKET-20261007-PredoneScopeIsPerTicketOnEpicBranches,
    PR #1045).
- **Decision:** Decision Kernel run run-f6524c703be24639 resolved `opt.completion_unstaged`:
  `set_ticket_status.py` gets a `--no-stage` flag; the completion write passes it; the done status stays in
  the worktree's ticket record and reaches main through finalize-feature.js step 3.5, the pre-merge
  closure (~1476-1650): it runs `git reset --hard HEAD` on the feature branch (~1559), which discards the
  unstaged done edits, then re-reads each changed ticket's status (todo again), sets `status: done` with
  set_ticket_status (default, staging), runs mark_ac_done for the source ACs and commits the closure on the
  branch before the merge. (The kernel input named finalize-feature's archive-check skill instead; that
  skill is not called by finalize-feature.js. The pr-reviewer caught the wrong mechanism; the conclusion
  holds through step 3.5.) The user approved the decision basis.
- **Size ratchet:** build-feature.js and build-ticket.js are over the 1000-line limit; every added measured
  line costs two removed lines in the same file (`python scripts/commit_guardian/check_file_size.py`).

## Acceptance Criteria
- [ ] AC-1: `python scripts/set_ticket_status.py --ticket <path> --status done --no-stage` writes the status
  exactly as today (same transition and parity checks, same exit codes) and does NOT stage the file:
  `git diff --cached --name-only` is unchanged by the call.
- [ ] AC-2: without `--no-stage`, `set_ticket_status.py` behaves exactly as today, including staging the file.
- [ ] AC-3: both twins' `writeTicketCompletion` dispatch the command with `--no-stage`; the prompt still
  forbids any other route and any other flag, and the failure contract (non-zero exit → not closed) holds.
- [ ] AC-4: build-feature-ops-notes says the completion write leaves `status: done` unstaged on purpose and
  that finalize-feature step 3.5 resets the worktree, re-sets it and commits the closure before the merge;
  status-checker's Closing protocol names `--no-stage` for the driver-dispatched completion write.
- [ ] AC-5: finalize-feature step 3.5 sub-step A ends at the feature branch's HEAD on both paths: after
  `merge --abort` (test merge in progress, the normal case for a branch behind main) it also runs
  `git reset --hard HEAD`, as the no-merge path already does, so B2 reads each ticket's committed status
  and an unstaged done edit left by the completion write is re-set and committed by the closure.
  (pr-reviewer H-1: `merge --abort` is `reset --merge` and keeps unstaged edits.)

## Test Requirements
```yaml
tests:
  - name: test_no_stage_writes_status_without_staging
    file: unit_tests/test_set_ticket_status_no_stage.py
    covers: []
    asserts: "In a real temp git repo with a committed ticket file, --status done --no-stage changes the
      file's status line and leaves `git diff --cached --name-only` empty; exit 0."
    framework: pytest
    type: behavioral
    angle: real_artifact
  - name: test_default_still_stages_the_ticket
    file: unit_tests/test_set_ticket_status_no_stage.py
    covers: []
    asserts: "Guard: the same call without --no-stage stages the ticket file (it appears in
      `git diff --cached --name-only`), as today."
    framework: pytest
    type: behavioral
    angle: real_artifact
  - name: test_no_stage_keeps_transition_checks
    file: unit_tests/test_set_ticket_status_no_stage.py
    covers: []
    asserts: "A transition the allow-list refuses (for example todo -> done without --force where the
      script refuses it today) is still refused with the same exit code when --no-stage is passed, and
      the file is unchanged."
    framework: pytest
    type: behavioral
    angle: failure
  - name: test_completion_write_passes_no_stage
    file: unit_tests/workflows/test_completion_write_no_stage.py
    covers: []
    asserts: "Parametrised over TWIN_DRIVERS: a ticket driven to completion under the harness dispatches
      the completion write (label ticket-completion-write) with a prompt that contains
      `set_ticket_status.py --ticket` ... `--status done --no-stage` and still says no other flags."
    framework: pytest
    type: behavioral
    angle: seam
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/test_set_ticket_status_no_stage.py:test_no_stage_writes_status_without_staging, unit_tests/test_set_ticket_status_no_stage.py:test_no_stage_keeps_transition_checks | | |
| AC-2 | unit_tests/test_set_ticket_status_no_stage.py:test_default_still_stages_the_ticket | | |
| AC-3 | unit_tests/workflows/test_completion_write_no_stage.py:test_completion_write_passes_no_stage | | |
| AC-4 | (prose, reviewed by pr-reviewer) | | |
| AC-5 | test_step_3_5_resets_to_head_after_merge_abort | | |

## Comments

### 2026-10-08 14:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote 4 tests (5 cases with the twin parametrisation). No signoff checkbox section exists in this ticket, so only the frontmatter flag and task were updated. Strict run: 4 red by assertion, 1 green guard. The refused transition pinned is done -> todo without --force: exit 1, "Invalid transition" on stdout, file unchanged. The driver test checks the prompt only (not the on-disk done state) so it does not depend on the CRLF harness defect.
cross_layer_seam_answer: covered (producing side: build-feature.js / build-ticket.js writeTicketCompletion prompt; consuming side: scripts/set_ticket_status.py argparse) - the subprocess tests and the prompt test pin the two ends separately.
red_baseline:
  - test_name: test_no_stage_writes_status_without_staging
    file: unit_tests/test_set_ticket_status_no_stage.py
    kind: assertion
    error: "AssertionError: (2, '', '... set_ticket_status.py: error: unrecognized arguments: --no-stage') assert 2 == 0"
  - test_name: test_no_stage_keeps_transition_checks
    file: unit_tests/test_set_ticket_status_no_stage.py
    kind: assertion
    error: "AssertionError: (2, '', '... unrecognized arguments: --no-stage') assert 2 == 1"
  - test_name: test_completion_write_passes_no_stage[build-feature.js]
    file: unit_tests/workflows/test_completion_write_no_stage.py
    kind: assertion
    error: "AssertionError: assert '--status done --no-stage' in <prompt ending '--status done, with no additional flags'>"
  - test_name: test_completion_write_passes_no_stage[build-ticket.js]
    file: unit_tests/workflows/test_completion_write_no_stage.py
    kind: assertion
    error: "AssertionError: assert '--status done --no-stage' in <prompt ending '--status done, with no additional flags'>"
green_at_baseline (guard): test_default_still_stages_the_ticket

### 2026-10-08 15:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
Added KI-10 to templates/skills/build-feature-ops-notes/SKILL.md: done tickets are modified-but-unstaged by design (--no-stage), must not be staged/committed by hand on an epic branch, and are committed by finalize-feature on main.
KI-9 did not claim completion writes are staged leftovers, so it is unchanged; skill tests (31) pass.

### 2026-10-08 16:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Added `--no-stage` (store_true) to scripts/set_ticket_status.py: `set_ticket_status(..., stage=True)` gates only `_stage_file`; docstring and DECISION HISTORY updated; transitions, parity, messages, exit codes, --force and --scan-epic untouched. Both twins' `writeTicketCompletion` prompt now prescribes `... --status done --no-stage, with no additional flags beyond --no-stage and no override` (the test pins the literal "no additional flags"); failure contract kept. No tracked mirror of set_ticket_status.py exists (only scripts/).
red_baseline_results:
  - test_no_stage_writes_status_without_staging: green
  - test_no_stage_keeps_transition_checks: green
  - test_completion_write_passes_no_stage[build-feature.js]: green
  - test_completion_write_passes_no_stage[build-ticket.js]: green
  - test_default_still_stages_the_ticket (guard): green
Tests: strict run of the 4 new + guard, commit_guardian/test_set_ticket_status.py, prompt_assembly/, finalize single-writer, tq500f3ii driver tests with -p lfopen -p lfposix: 239 passed, 1 skipped, 0 failed.
Ratchet: check_file_size passes. Paid with one condensed comment ("Provisional...", 2 lines to 1) and one empty `//` banner line removed in each driver. Raw line counts: build-feature.js 3735 -> 3732, build-ticket.js 2194 -> 2191.

### 2026-10-08 07:52 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
Verdict: BLOCKER. The code change itself is correct; the lifecycle claim behind it (AC-4, KI-10, Context) is not.
[H-1] templates/workflows-js/finalize-feature.js:1595 (+ 1560-1650, 2183) and templates/skills/build-feature-ops-notes/SKILL.md:376-379 - finalize-feature does NOT run the archive check and does NOT set the unstaged done status. Step 5 is sync-main; the finalize-feature-archive-check skill is not called from the JS at all. The only closure is step 3.5 pre-merge: B2 reads each ticket's status from disk and skips status == done as already closed (idempotency), so OPEN_TICKETS is empty, sub-step D (mark_ac_done for source_ac) is skipped, no closure commit is made, and the done write stays an uncommitted worktree edit that never reaches main (step 6 is read-only and Step 7 removes the worktree). Before this change the done file was staged, so step 3.5 STAGED_PATHS commit swept it in; --no-stage removes that path. Effect: tickets stay todo on main and source ACs stay unclosed after epic and single-ticket /build-ticket merges. KI-10 and AC-4 state the opposite. Fix needed: make step 3.5 detect worktree-vs-HEAD status drift (read status from git HEAD, not disk) or have the driver commit the done writes at the end of the run; correct KI-10 accordingly.
[M-1] templates/agents/status-checker.md:147-152, 211 - the agent's Closing protocol still shows the command without --no-stage and says 'The script stages the file automatically'. The dispatch prompt ("--no-stage, with no additional flags beyond --no-stage and no override") is unambiguous and the test pins it, but it contradicts the agent protocol the prompt tells it to follow 'exactly'. Low risk of the agent dropping the flag; update the protocol text for the driver-dispatched path.
[L-1] unit tests cover the script and the prompt only; nothing exercises finalize step 3.5 against an unstaged done ticket (that is the gap behind H-1).
Checked, no finding: set_ticket_status.py --no-stage gates only _stage_file (transitions, parity, messages, exit codes, --force, --scan-epic untouched; default still stages). Twin prompts are identical and keep the no-other-route and non-zero-exit-means-not-closed contract. Ratchet payment: only a comment reworded and an empty // banner line removed in both drivers; no AC or requirement id lost.
Callers of set_ticket_status.py (all unchanged, default stages): templates/agents/status-checker.md:149,211; templates/skills/build-single-ticket/SKILL.md:554; templates/skills/building-epics/SKILL.md:347,401,437,1244; templates/skills/finalize-feature-archive-check/SKILL.md:62 (--scan-epic),126; templates/workflows-js/finalize-feature.js:1601 (step 3.5 sub-step C); templates/workflows-js/build-feature.js:1328 and build-ticket.js:1161 (the changed completion write). No hooks call it; scripts/ only packages it (build_phases*.py); scripts/commit_classifier.py:288 only mentions its output.
Order note: in build-ticket.js the completion write runs after the commit and pull-request phases, so the done edit was never part of the branch commit; only finalize's step 3.5 staged-path sweep could commit it.

### 2026-10-08 07:55 — test-runner (status: ok)
feedback-id: (submit-failed)
Targeted: unit_tests/test_set_ticket_status_no_stage.py + unit_tests/workflows/test_completion_write_no_stage.py -> 5 passed.
Wide run (16 referencing files + unit_tests/workflows + unit_tests/prompt_assembly, -n auto, AC_ENFORCE_STRICT=1, -p lfopen -p lfposix): 40 failed, 1091 passed, 1 skipped, 49 errors.
Baseline (hook-followup-tickets, same command minus the 2 new files): 40 failed, 1086 passed, 1 skipped, 49 errors. The 89 failing/erroring node ids are identical in both; the +5 passes are the new tests.
feedback-id: (submit-failed)

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true   # new tests pass; 0 attributable failures
  failure_report_structured: true
  counts: {targeted_passed: 5, wide_failed: 40, wide_errors: 49, wide_passed: 1091, wide_skipped: 1}
  failures: {attributable: 0, pre_existing: 89, flake: 0}
```

### 2026-10-08 07:56 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
Re-review of H-1 and M-1 against the corrected files. M-1 is resolved (templates/agents/status-checker.md:165 now names --no-stage). H-1 is narrowed, not refuted: my first description (no archive check; B2 skips on disk-done) was right about the mechanism but wrong that it applies everywhere. The coordinator's reset-wipes-it claim is correct for only one of the two step-2 outcomes.
[H-1, narrowed] templates/workflows-js/finalize-feature.js:1544-1563 (sub-step A) with 996-1015 (step 2). Step 3.5 sub-step A runs `reset --hard HEAD` only when there is NO MERGE_HEAD. That is the step-2 already_up_to_date outcome (line 998-999), where no merge was started. When step 2 instead merged origin/main cleanly (`merge origin/main --no-commit --no-ff`, line 1007, exit 0 leaves MERGE_HEAD in place - the normal outcome for any branch behind main, and the typical long-lived epic branch), sub-step A takes the `merge --abort` branch (line 1555). `merge --abort` is `reset --merge`, which by git's definition keeps changes that are in the working tree but not in the index. So an unstaged status: done survives, B2 (line ~1595) reads done from disk, skips the ticket, OPEN_TICKETS is empty, and C/D/E never run: no set, no mark_ac_done, no closure commit. The done status and source-AC closure are then lost on that path. Only the up-to-date path is rescued by the reset. I could not run a scratch repo to confirm the abort behaviour empirically (the commit hook blocks git commit even in a temp repo), so this rests on git's documented reset --merge semantics; the coder or test-runner should confirm with a real merge --no-commit/--abort round trip.
Skip paths, same sub-step A not reached: (a) closure commit already on branch (line 1509): a ticket completed after that commit stays unstaged and uncommitted, never closed; (b) PR already merged (line 1535): the unstaged done is never committed. Both are lost with --no-stage; with the old staged write they were equally not committed by step 3.5, so these are not regressions, only gaps KI-10 should not paper over.
KI-10 (SKILL.md:377-382) now says anything unstaged is discarded by the reset and 'nothing else should be left there'. That is true only for the no-merge path and is false for the merged_main path; it must say the abort path keeps unstaged edits and describe what actually closes the ticket there.
Needed to clear: make step 3.5 not depend on the worktree's disk status for the merged_main path, e.g. sub-step A also runs `git checkout -- tickets/` (or reset --hard after abort) so B2 sees HEAD status, or B2 reads status from HEAD (`git show HEAD:<path>`). Add a driver-level test for the merged_main case. Then update KI-10.

### 2026-10-08 17:00 — python-coder (status: ok)
feedback-id: (submit-failed)
AC-5: templates/workflows-js/finalize-feature.js step 3.5 sub-step A (`step-3.5-reset-merge`): the merge-in-progress branch now runs `git -C "${WORKTREE_ROOT}" reset --hard HEAD` after `merge --abort`; its log text is now 'Step 2 test-merge aborted and reset to feature-branch HEAD.'; Return shape `{"status": "aborted"}` unchanged. node --check ok, LF only.
red_baseline_results:
  - test_step_3_5_resets_to_head_after_merge_abort: green
Tests (strict, -p lfopen -p lfposix): all files matching finalize-feature/finalize_feature in unit_tests and tests, plus my earlier 4 tests: the AC-5 test and the earlier tests are green. The remaining 3 failures (test_check_workflow_meta.py) and 103 errors (fixture/build-environment errors in tests/ac_store, tests/knowledge, build_guards, test_bp_900g_6 and others) are identical to the same run in the hook-followup-tickets base worktree, so pre-existing.
Ratchet: check_file_size passes. Added 2 lines (reset run line, rewritten log line); paid by removing both dashed banner lines around the sub-step A comment (a single-line comment remains) plus the replaced log line. Raw lines 2380 -> 2379.

### 2026-10-08 08:07 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
H-1 cleared. What changed my verdict: finalize-feature.js step 3.5 sub-step A (~1550-1556) now runs `reset --hard HEAD` after `merge --abort` in the merge-in-progress branch, and the no-merge branch already reset. Both step-2 outcomes (already_up_to_date, merged_main) therefore end at the feature branch's committed HEAD, B2 reads the committed `todo`, and C (set done), D (mark_ac_done) and E (closure commit) run, so done and AC closure reach main through the merge. The new test unit_tests/workflows/test_finalize_step35_reset_after_abort.py passes (1 passed) and pins the abort-then-reset order plus the no-merge control.
Checked: Return shape unchanged ({status: aborted}/{status: reset}); only the log text changed. Ratchet: two empty banner comment lines removed from the Sub-step A header; no AC or requirement id lost (the AC-5 idempotency reason string at ~1539 is intact). M-1: status-checker.md:161-167 now states the --no-stage exception for the driver completion write and keeps the default for the interactive path; clear. KI-10 (SKILL.md:377-383) accurately describes both paths and the reset discarding unstaged edits.
Skip paths confirmed pre-existing: closure-already-committed (finalize-feature.js:1509) and PR-already-merged (:1535) bypass sub-steps A-E entirely, and sub-step E (git add / commit) lives only inside the else branch, so a staged done write was equally never committed by step 3.5 there. --no-stage introduces no regression on them.
Residual (low, informational): the abort-then-reset also discards any other unstaged worktree work at finalize, as the no-merge branch always did; KI-10 says so.

## Implementation Tasks
### test-writer
- [x] Write the four tests above; confirm red where they pin new behaviour.
### python-coder
- [x] Add `--no-stage` to scripts/set_ticket_status.py (skip `_stage` only; everything else unchanged).
- [x] Pass `--no-stage` in both twins' `writeTicketCompletion` prompt; pay the size ratchet in each file.
### llm-expert
- [x] Add the build-feature-ops-notes note (AC-4).
### test-runner / pr-reviewer / commit
- [ ] Run, review, commit.

## Risk & Safety
- Touches money? No.
- Touches data? Ticket records only: the done status is still written, just not staged.
- Reversibility? Fully reversible (drop the flag).

## Out of Scope
- Fixing check-predone-scope for epic branches (TICKET-20261007-PredoneScopeIsPerTicketOnEpicBranches).
- Moving the red-baseline gate's executor off status-checker (the verdict relay corrupted a 1.6 KB reply
  once on E1 ticket 03; separate follow-up).

### 2026-10-08 17:00 — test-writer (status: ok)
feedback-id: (submit-failed)
AC-5 scope addition. Wrote test_step_3_5_resets_to_head_after_merge_abort in unit_tests/workflows/test_finalize_step35_reset_after_abort.py. Harness: no driver harness exists for finalize-feature.js; followed the established structural pattern (unit_tests/test_finalize_feature_single_writer_close.py) by extracting the real `step-3.5-reset-merge` dispatch prompt by its label and asserting on its merge-in-progress branch. Asserts merge --abort is present, `reset --hard HEAD` follows it in the same branch, plus a control that the no-merge branch keeps its reset. Q1 wrong version caught: abort-only branch (today's code). Not behavioural against a real repo: the prompt is instructions to an agent, and git's reset --merge semantics are documented, not under test here.
cross_layer_seam_answer: not_applicable (reason: prompt-text assertion on a single dispatch; no producer/consumer pair is piped).
red_baseline:
  - test_name: test_step_3_5_resets_to_head_after_merge_abort
    file: unit_tests/workflows/test_finalize_step35_reset_after_abort.py
    kind: assertion
    error: "AssertionError: merge --abort keeps unstaged edits; the merge-in-progress branch must also run `git reset --hard HEAD`"

### 2026-10-08 17:30 — llm-expert (status: ok)
feedback-id: (submit-failed)
Reworded KI-10 in build-feature-ops-notes so step 3.5 resets to the feature branch's HEAD on both paths (aborting any test merge first); tests/knowledge/test_native_skill.py and tests/test_skill_registry.py pass (31).

### 2026-10-08 08:37 — test-runner (status: ok)
feedback-id: (submit-failed)
Re-run after AC-5 scope addition (finalize step 3.5 reset --hard HEAD after merge --abort, --no-stage in both drivers, KI-10 and status-checker wording).
Targeted (3 new files): 6 passed.
Wide (97 referencing files + unit_tests/workflows + unit_tests/prompt_assembly, -n auto, AC_ENFORCE_STRICT=1, -p lfopen -p lfposix): 101 failed, 1492 passed, 1 skipped, 1 xfailed, 172 errors.
Baseline (hook-followup-tickets, same command minus the 3 new files): 101 failed, 1486 passed, 1 skipped, 1 xfailed, 172 errors. The 273 failing/erroring node ids are identical in both (comm diff empty); the +6 passes are the new tests. Zero attributable, zero flake.
feedback-id: (submit-failed)

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true   # all new/changed-behaviour tests pass; 0 attributable failures
  failure_report_structured: true
  counts: {targeted_passed: 6, wide_failed: 101, wide_errors: 172, wide_passed: 1492, wide_skipped: 1, wide_xfailed: 1}
  failures: {attributable: 0, pre_existing: 273, flake: 0}
```

### 2026-10-08 08:43 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit: subject "fix(build-orchestration): keep a finished ticket's done status unstaged until finalize".
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
