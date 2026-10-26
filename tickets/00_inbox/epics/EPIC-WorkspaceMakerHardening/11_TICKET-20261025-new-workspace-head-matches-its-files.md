---
title: "A new workspace's line of work starts exactly where its files are, or the maker refuses"
ac_traceability:
  l2:
    - BO-4300a-1
    - BO-4300c-1
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
status: done
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-25'
last_updated: '2026-10-25'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
ac_coverage: 5/5
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - found-after-pr-1318
files_touched:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_ensure_steps.py
  - templates/scripts/worktree_ensure_state.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/worktree_migrate_carry.py
  - unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 11: A new workspace's line of work starts exactly where its files are, or the maker refuses

## Actor / Goal
A new workspace must never start with HEAD on one commit and its index and files on another. If it
does, the gap shows as "staged changes" that nobody made. A routine first commit would then sweep
in, or revert, merged work. ensure must build the line from one resolved commit, or refuse.

## Context
- **Found:** 2026-10-25, after PR #1318. `ensure --kind feature --slug injection-bundle-utf8-output`, and again `--slug maker-checkout-race`, answered **ok**, but:
  - HEAD and the branch were at the main checkout's stale main (1a5c47cc3);
  - the index and files held the hub's main (5f3dada88, PR #1348);
  - so 61 files showed as staged changes;
  - `base_commit` 5f3dada88 was not equal to `origin_main_commit` 1a5c47cc3, and tree_clean was false.
- **Reproduced:** it happens on every ensure while the hub's main is ahead of the main checkout's local main.
- **Root cause** (investigation, with a scratch repro at scratchpad/repro1.sh):
  1. **The checkout resolves the start point twice.** `checkout -B <branch> origin/main` (worktree.py ~86) takes the start point by ref NAME. git resolves it once for the tree and again when it creates the branch. A concurrent ref update of `refs/remotes/origin/main` between the two splits HEAD from the index. That update comes from an outside fetch: VS Code's git.autofetch opens every new clone. While the clone's origin is still the main checkout's path, a plain `git fetch` rewrites origin/* to the main checkout's stale local branches.
  2. **The set-aside step treats the gap as work.** `work_set_aside` (worktree_ensure_state.py ~349-376) runs on a brand-new workspace, takes the gap for "the work's changes", proves readiness on a clean tree, then puts the gap back and re-stages it.
  3. **Nothing refuses afterwards.** The ok decision is made before the put-back (worktree.py ~142-147), and `with_restored_tree` records tree_clean false but never refuses.
  4. **The freshness check reads the moved ref.** `base_is_fresh` (worktree_readiness.py ~225) compares HEAD with origin/main as re-read, which is the moved ref, rather than with the `base_commit` resolved at the fetch (worktree.py ~107).

## Scope
1. Resolve the base to ONE SHA right after the hub fetch: the recorded `base_commit`, or for a resumed line the SHA of `origin/<branch>`. Create or reset the line from that SHA (`checkout --no-track -B <branch> <sha>`), then set the upstream explicitly. After the checkout, assert that HEAD equals that SHA and that the tree is clean. Otherwise refuse, with a contract code and a `step`, and discard the new clone (`created`).
2. On a `created` workspace there is no work to protect. Skip the set-aside entirely, and refuse when the tree is not clean.
3. Compute `base_is_fresh` and `base_matches_origin_main` from the recorded `base_commit` and the SHA the line was built from, never from a re-read of a ref that might have moved.
4. Close the clone window. Clone with a temporary remote name (`clone -o leafcutter-src ...`), then add `origin` pointing at the hub and remove the temporary remote, so an outside bare `git fetch` never sees the main checkout as `origin`.
5. A resumed or re-readied line keeps today's behaviour for the user's real uncommitted work: the set-aside still protects it.

## Acceptance Criteria
- [x] AC-1: When `refs/remotes/origin/main` is rewritten during the checkout, in either direction (older or newer), ensure never answers ok with HEAD ≠ base_commit or a dirty tree. It either builds the line at the recorded SHA with a clean tree, or refuses naming the step (BO-4300a-1 IT3, BO-4300c-1).
- [x] AC-2: A `created` workspace never runs the set-aside. A dirty tree after creation is refused, not preserved and re-staged.
- [x] AC-3: base_is_fresh and base_matches_origin_main compare against the recorded base_commit.
- [x] AC-4: Throughout and after the clone, the clone never has a remote named `origin` whose URL is the main checkout's path.
- [x] AC-5: A resumed workspace with the user's real uncommitted change still keeps it byte-identical (the existing set-aside tests stay green).

## Test Requirements

```yaml
tests:
- name: test_origin_main_moved_back_during_checkout_never_answers_ok_split
  file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
  asserts: With a git filter or hook that rewrites refs/remotes/origin/main to an OLDER commit mid-checkout (scratchpad repro1.sh technique), ensure either answers ok with HEAD == base_commit, a clean tree and an empty `git status`, or refuses with a step; it never gives ok with staged changes.
  framework: unittest
  type: behavioral
- name: test_origin_main_moved_forward_during_checkout_never_answers_ok_split
  file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
  asserts: The same with origin/main moved to a NEWER commit mid-checkout; no staged reverts are ever left in an ok workspace.
  framework: unittest
  type: behavioral
- name: test_created_workspace_with_dirty_tree_is_refused_not_preserved
  file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
  asserts: When a fresh clone's tree differs from HEAD after checkout, ensure refuses (no rescue folder written, no re-staged files) and discards the new clone.
  framework: unittest
  type: behavioral
- name: test_clone_never_exposes_main_checkout_as_origin
  file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
  asserts: The clone step uses a temporary remote name; at no point is there an `origin` remote whose URL is the main checkout path, e.g. observed via a reference-transaction or post-checkout hook recording `git remote -v`.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [x] test-writer — 2026-10-25 12:00
- [x] python-coder — 2026-10-25 15:00
- [x] pr-reviewer — 2026-10-25 16:00
- [x] ac-validator — 2026-10-25 17:00
- [x] ac-fulfillment-gate — 2026-10-25 18:00
- [x] commit — 2026-10-25 19:00

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-25 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  tests_red_for_right_reason: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "templates/scripts/worktree.py ensure (clone + checkout) as deployed"
    consuming_side: "real git (checkout, index, status) and the hub refs it reads, observed through filter and hook probes"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "deployed maker worktree.py ensure --kind feature --slug <x> via run_maker (CLI subprocess)"
red_baseline:
  - test_name: test_origin_main_moved_back_during_checkout_never_answers_ok_split
    file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
    kind: assertion
    error: "AssertionError: HEAD is not the recorded base: status ok, HEAD at the seed commit, base_commit at the hub tip"
  - test_name: test_origin_main_moved_forward_during_checkout_never_answers_ok_split
    file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
    kind: assertion
    error: "AssertionError: HEAD is not the recorded base: status ok, HEAD at the newer commit, base_commit at the old tip"
  - test_name: test_created_workspace_with_dirty_tree_is_refused_not_preserved
    file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
    kind: assertion
    error: "AssertionError: 'ok' not found in ('refused', 'error') : a dirty new workspace must be refused"
  - test_name: test_clone_never_exposes_main_checkout_as_origin
    file: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
    kind: assertion
    error: "AssertionError: a remote named origin pointed at the main checkout: ['origin\t<project> (fetch)', ...12 records]"
Four tests written, all red on Linux (Docker) with assertion-shaped failures. Wrong versions caught: checkout by ref name (HEAD and index split, both directions), set-aside plus put-back on a created workspace, origin pointing at the main checkout during clone.


### 2026-10-25 14:00 — python-coder (status: handoff)
feedback-id: (submit-failed)
handoff_target: test-writer
red_baseline_results:
  - test_name: test_origin_main_moved_back_during_checkout_never_answers_ok_split
    result: red (test defect, classification: test_drift)
  - test_name: test_origin_main_moved_forward_during_checkout_never_answers_ok_split
    result: red (test defect, classification: test_drift)
  - test_name: test_created_workspace_with_dirty_tree_is_refused_not_preserved
    result: green
  - test_name: test_clone_never_exposes_main_checkout_as_origin
    result: green
Production change done (worktree_ensure_steps.build_line, clone with leafcutter-src, no set-aside on created, base_ref
to prove_ready). The two race tests now reach their last assertion with HEAD == base_commit == hub tip and nothing staged,
but fail on `git status --porcelain` because the stub install leaves untracked `.leafcutter/` and `INSTALLED_MARKER.txt`
(the fixture project has no .gitignore). A copy using `status --porcelain -uno` passes all 4 on Linux. Needed test fix:
use `--untracked-files=no` (or ignore those two paths) at test line 124. Family run on Linux: no other failures.

### 2026-10-25 13:00 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: test_drift) The race tests' last assertion treated the stub install's own untracked files as a dirty tree. `_assert_no_split` now drops exactly `?? .leafcutter/` and `?? INSTALLED_MARKER.txt` (staged or modified lines still fail). The three classes that rely on sh hooks or filters are skipped when `sh` is absent. File ran 3 times and the bo_4300 family once on Linux: all green.

### 2026-10-25 15:00 — python-coder (status: ok)
feedback-id: (submit-failed)
red_baseline_results:
  - test_name: test_origin_main_moved_back_during_checkout_never_answers_ok_split
    result: green
  - test_name: test_origin_main_moved_forward_during_checkout_never_answers_ok_split
    result: green
  - test_name: test_created_workspace_with_dirty_tree_is_refused_not_preserved
    result: green
  - test_name: test_clone_never_exposes_main_checkout_as_origin
    result: green
All 4 green on Linux after test-writer's fix of the two race tests; bo_4300 family shows no failures.

### 2026-10-25 16:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Review of the staged diff vs base 5f3dada88: no high-confidence findings.
- build_line resolves origin/main once (worktree.py `_checkout_line`) and origin/<branch> once; checkout, verify, marker, answer and prove_ready use that SHA. Residual re-reads are fail-closed or outside the build: compute_checks re-reads `origin/<branch>` for resumed lines (M-1), and the re-ready path (no built_from) re-reads origin/main by design (M-2).
- Created workspaces skip the set-aside; resumed and re-readied lines keep it. Refusals from build_line discard the clone and carry code, step and no workspace_path.
- Temporary remote leafcutter-src is swapped for a hub origin with no window where origin names the main checkout; the seed is overwritten by the hub fetch or kept only under --allow-stale-base with fetch_status failed (tip null).
- Medium: M-1 (resumed freshness re-read), M-2 (re-ready path not on built_from), M-3 (`-B` can reset a pre-existing local branch in the creating-not-checked-out resume), M-4 (new lines no longer get upstream origin/main; intended). Local run of the race tests on Windows failed the filter-fired precondition (sh filter did not fire); verify on Linux.


### 2026-10-25 14:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Added for pr-reviewer M-3 (class `TestResumeNeverResetsLocalWork`): a 'creating' workspace (maker stopped by the after_clone abort seam) with local feature/x one commit ahead of the hub's must be refused with a step, with the local branch tip unchanged; control: local equal to the hub resumes ok at that SHA. Both green against the coder's current working tree on Linux. The refusal test was not seen red here, because the coder's guard was already in place when I ran it.

### 2026-10-25 16:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework for pr-reviewer M-3 and M-1 (templates/scripts only, no test edits).
- M-3: `build_line` (worktree_ensure_steps) refuses with code WORK_AT_RISK, step `checkout`, naming the branch, when a resumed line's local branch exists and is not an ancestor of the hub SHA; equal or behind is reset as before. WORK_AT_RISK is an existing BO-4300c-2 code, no new code.
- M-1: `build_line` now returns the start SHA; `_checkout_line` carries it as a 5th tuple element and `_install_and_mark` passes it to `prove_ready(base_ref=...)`, so `compute_checks` uses it as the resumed freshness target instead of re-reading origin/<branch>.
- Linux bo_4300 family: no failures except two new sibling tests in TestResumeNeverResetsLocalWork, which fail with NameError `_creating_workspace` (helper not yet written by test-writer).
- ruff, complexity, file-size, exception-handling hooks and ast.parse pass.

### 2026-10-25 17:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  all_acs_have_implementation_evidence: true
  all_acs_have_test_evidence: true
  store_alignment_check_clean: true
  cross_file_contract_trace_not_applicable: true
All 5 ACs and the linked BO-4300a-1 (IT3) / BO-4300c-1 are covered. Store alignment exit 0. No delivers_to/expects_from fields. Caller-reported Linux Docker runs: 6 passed; disabling the resumed-line guard fails exactly test_resume_refuses_when_local_line_holds_commits_the_hub_lacks. This validator did not re-run tests.
AC-1 covered:
  implementation: templates/scripts/worktree_ensure_steps.py build_line (single resolved SHA, `checkout --no-track -B <branch> <sha>`), _verify_built (HEAD == sha and clean tracked tree, VERIFY_FAILED step verify-checkout), _unsent_local_refusal (WORK_AT_RISK)
  test: test_origin_main_moved_back_during_checkout_never_answers_ok_split, test_origin_main_moved_forward_during_checkout_never_answers_ok_split (unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py, TestCheckoutRace)
AC-2 covered:
  implementation: templates/scripts/worktree.py `contextlib.nullcontext() if action == "created" else wes.work_set_aside(workspace_path)`
  test: test_created_workspace_with_dirty_tree_is_refused_not_preserved (same file, TestCreatedWorkspaceIsNeverPreserved)
AC-3 covered:
  implementation: templates/scripts/worktree_readiness.py compute_checks `target = base_ref or f"origin/{branch}"` and prove_ready(base_ref=...); worktree_ensure_state.ok_fields uses built_from
  test: the two TestCheckoutRace tests (moved ref must not split or falsify freshness) plus TestResumeNeverResetsLocalWork control test_resume_control_local_line_equal_to_hub_resumes_ok. Indirect: no test asserts base_is_fresh/base_matches_origin_main values directly (note, not blocking).
AC-4 covered:
  implementation: templates/scripts/worktree_ensure_steps.py SOURCE_REMOTE = "leafcutter-src", clone_main_checkout, _swap_source_for_hub
  test: test_clone_never_exposes_main_checkout_as_origin (same file, TestCloneNeverExposesMainCheckout)
AC-5 covered:
  implementation: templates/scripts/worktree.py keeps wes.work_set_aside for non-created actions
  test: existing set-aside tests in the bo_4300 family, reported green on Linux; test_resume_control_local_line_equal_to_hub_resumes_ok
Anomalies: the ticket has no ## AC Coverage table, so none was filled. Feedback submit failed (knowledge_sink.json absent in this worktree). AC-5 test evidence is existing tests outside the diff, taken from the caller's report.

### 2026-10-25 18:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_verified: true
  auto_fixes_applied: true
  done_proof_precommit_green: true
All 2 ACs verified (BO-4300a-1, BO-4300c-1; both composite, work_status done, all children done, left unchanged). Appended unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py to covered_by of both (carries both # covers: tags); added templates/scripts/worktree_readiness.py to BO-4300a-1 implemented_by and templates/scripts/worktree_ensure_steps.py to BO-4300c-1 implemented_by. check_ac_schema and check_done_proof (precommit) pass. Feedback submit failed (knowledge_sink.json absent).

### 2026-10-25 19:00 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: 8 files committed through the shared commit step.
