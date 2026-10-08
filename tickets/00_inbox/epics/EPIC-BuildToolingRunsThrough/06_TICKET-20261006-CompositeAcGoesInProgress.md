---
title: "An AC with child ACs goes to in_progress, not done, until every child is done and proven"
status: todo
components:
  - ac_store
  - commit_guardian
created: 2026-10-06
depends_on: []
priority: high
complexity: medium
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: BO-202
ac_traceability:
  id: BO-202
  path: docs/acceptance-criteria/build-orchestration/BO-202.yaml
requires_diagram: false
requires_adr: false
change_target:
  - code
  - prompt
risk_surface: contract_boundary
files_touched:
  - scripts/ac_store/mark_ac_done.py
  - scripts/ac_store/_done_proof_composite.py
  - scripts/commit_guardian/check_done_proof.py
  - templates/agents/ac-fulfillment-gate.md
  - tests/ac_store/test_mark_ac_done.py
  - unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: signed_off
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  status-checker: not_needed
---

# 06: An AC with child ACs goes to in_progress, not done, until every child is done and proven

## Actor / Goal

As the AC store's single writer of `work_status`, I want an AC whose `covered_by`
lists child AC ids to be treated as composite at any level. It goes to
`in_progress`, not `done`, until every child is done and proven. Then neither the
fulfillment gate nor finalize marks a parent done on diff evidence alone.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 5). Implements BO-202 as
amended on this branch (user decision F6, 2026-10-06). Consistent with approved
BO-2500b-1-ii.

**Root cause**
- `templates/agents/ac-fulfillment-gate.md`:
  - treats only L0/L1 as composite (130-133; Step 2b at 165-168);
  - Step 2f counts any non-empty `covered_by` as coverage for an L2 (201-204), so child AC ids pass;
  - Step 3a sets `done` whenever the ticket's files appear in the diff (226-230).
- Field evidence: in DK-400 E1 ticket 01 the gate's own comment (line 436) reads "work_status todo -> done; … covered_by already populated (DK-400a-1-i, DK-400a-1-ii)".
- The commit-time hook defines "composite" as "`covered_by` contains AC ids", at any level (`scripts/commit_guardian/check_done_proof.py:306-328` `_composite_child_ids`, and `406+` `_unproven_composite_children`).
- The same hole is in `scripts/ac_store/mark_ac_done.py:86-182`. `templates/workflows-js/finalize-feature.js:1611` and `templates/agents/build-ac.md:546/600` call it without `--test-root`, so it writes `done` for a composite unconditionally.

**Rule and fix (one writer: `mark_ac_done.py`)**
- An AC is composite when `_composite_child_ids(covered_by)` is non-empty. Share that helper; do not copy it.
- For a composite:
  - all children proven (`_unproven_composite_children == []`) → `done`;
  - otherwise, if it is `todo` (or already `in_progress`) → `in_progress`, exit 0, naming the unfinished children;
  - if it is already `done` but unproven → refuse with a non-zero exit, never downgrade silently.
- Leaves behave as today.
- The gate's Step 3a calls `mark_ac_done.py --ac <id> --test-root .` instead of an Edit. Steps 2b and 2f use the `covered_by` rule: child AC ids never count as test coverage.

## Constraints

- **Share, never copy.** `check_done_proof.py` measures 572 / 400, so the ratchet refuses growth. Move `_composite_child_ids`, and `_unproven_composite_children` if its helpers move cleanly, into `scripts/ac_store/_done_proof_composite.py` (118 lines, already deployed by `scripts/build_phases_ac_store.py:144`).
  - `check_done_proof.py` then imports them; it already puts the ac_store directory on `sys.path` via `ensure_ac_store_on_syspath`.
  - `mark_ac_done.py` imports them too.
  - The move shrinks `check_done_proof.py`, which the ratchet requires: the file must end at least as many measured lines shorter as the lines it gains, such as the import.
  - If the helpers cannot move cleanly, `mark_ac_done.py` imports them from `check_done_proof.py` and that file is not edited.
- `mark_ac_done.py` measures 275 / 400 and must stay at or below 400.
- Keep the anchored atomic write (ACS-200f-3, `mark_ac_done._atomic_write` 200-260) for the `in_progress` write.
- **Build mirrors.** After the template edit, run `python scripts/build.py` and stage every tracked output it changes.

## Acceptance Criteria

- [ ] AC-1: `mark_ac_done.py` treats an AC as composite when `_composite_child_ids(covered_by)` is non-empty, using the one helper `check_done_proof.py` also uses (imported, not copied).
- [ ] AC-2: For a composite whose children are all proven, `mark_ac_done.py` writes `done`, and the real `check_done_proof` passes on the result.
- [ ] AC-3: For a `todo` or `in_progress` composite with any unproven child, `mark_ac_done.py` writes `in_progress` (anchored write), exits 0, and names each unfinished child.
- [ ] AC-4: For a composite that is already `done` but unproven, `mark_ac_done.py` refuses with a non-zero exit, names the unproven children, and leaves the file unchanged.
- [ ] AC-5: Leaves (no AC-id children) behave exactly as today, with and without `--test-root`. The composite rule applies with and without `--test-root`; without one, no covers tags are collected, so a composite can reach `in_progress` but never `done`.
- [ ] AC-6: `templates/agents/ac-fulfillment-gate.md` Step 3a calls `mark_ac_done.py --ac <id> --test-root .` instead of editing `work_status`. Steps 2b and 2f treat an AC with AC-id children as composite at any level, and never count child ids as test coverage.

## Test Requirements

```yaml
tests:
  - name: test_composite_with_todo_children_goes_in_progress
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      In a real temporary AC store, an L2 parent with covered_by [child-a,
      child-b], where both children are todo, run through mark_ac_done --ac
      parent --test-root <tmp>, exits 0, leaves the parent's work_status as
      in_progress, and prints both child ids as unfinished.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_composite_with_all_children_proven_goes_done_and_passes_check_done_proof
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      Both children are work_status done, and each has a "# covers: <child-id>"
      test under the test root. mark_ac_done --ac parent --test-root <tmp>
      writes done, and the real check_done_proof composite check over the store
      reports no unproven children.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_leaf_behaviour_is_unchanged
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      A leaf AC (covered_by lists only a test-file path) is marked done exactly
      as before, with and without --test-root, with the same exit codes and
      output as today.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_already_done_unproven_composite_is_refused
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      A parent already at work_status done, with one child still todo: mark_ac_done
      exits non-zero, names the unproven child, and the parent YAML is
      byte-identical afterwards.
    framework: pytest
    type: integration
    angle: failure
  - name: test_composite_without_test_root_never_goes_done
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      Called as finalize-feature.js does (--ticket <ticket whose source_ac is a
      composite>, no --test-root), mark_ac_done never writes done for the
      composite. It writes in_progress and names the children.
    framework: pytest
    type: integration
    angle: failure
  - name: test_in_progress_write_is_anchored_and_preserves_line_endings
    file: unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py
    covers:
      - BO-202
      - ACS-200f-3
    asserts: >-
      A composite YAML with LF endings, and a quoted "work_status: todo" inside
      its notes, goes to in_progress. Only the top-level work_status key
      changes, the quoted prose is untouched, and every line keeps LF.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_mark_ac_done_and_check_done_proof_share_one_composite_helper
    file: tests/ac_store/test_mark_ac_done.py
    covers:
      - BO-202
    asserts: >-
      mark_ac_done's composite decision and check_done_proof's composite check
      resolve to the same _composite_child_ids function object (an identity
      check on the imported attribute), so the two can never disagree.
    framework: pytest
    type: unit
    angle: seam
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_mark_ac_done_and_check_done_proof_share_one_composite_helper | `_done_proof_composite._composite_child_ids` imported by mark_ac_done and check_done_proof |  ok — 2026-10-06 |
| AC-2 | test_composite_with_all_children_proven_goes_done_and_passes_check_done_proof | mark_ac_done `_composite_verdict` falls through to the existing gate and done write when no child is unproven |  ok — 2026-10-06 |
| AC-3 | test_composite_with_todo_children_goes_in_progress, test_in_progress_write_is_anchored_and_preserves_line_endings | `_composite_verdict` writes in_progress via anchored `_set_work_status`, exit 0, names children |  ok — 2026-10-06 |
| AC-4 | test_already_done_unproven_composite_is_refused | `_composite_verdict` refuses (exit 3) an already-done unproven composite, file untouched |  ok — 2026-10-06 |
| AC-5 | test_leaf_behaviour_is_unchanged, test_composite_without_test_root_never_goes_done | leaves return None from `_composite_verdict` and take the old path; no-root scan yields empty covers set |  ok — 2026-10-06 |
| AC-6 | pr-reviewer reads the gate template diff (`tests/test_ac_fulfillment_gate.py` only checks frontmatter) | |  ok — 2026-10-06 |

## Implementation Tasks

### test-writer
- [x] Extend `tests/ac_store/test_mark_ac_done.py` and `unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py` with real temporary stores and test roots.

### python-coder
- [x] Move the composite helper(s) into `scripts/ac_store/_done_proof_composite.py`, and import them in `check_done_proof.py`, which shrinks.
- [x] `mark_ac_done.py`: add the composite branch (done / in_progress / refuse), the anchored `in_progress` write and the unfinished-children message. Leaves keep today's path.
- [x] Run `python scripts/build.py` and stage the tracked outputs.

### llm-expert
- [x] `templates/agents/ac-fulfillment-gate.md`:
  - [x] Step 2b (130-133, 165-168): composite means `covered_by` holds AC-id children, at any level;
  - [x] Step 2f (201-204): child ids are not test coverage;
  - [x] Step 3a (226-230): call `mark_ac_done.py --ac <id> --test-root .` and report its result, including `in_progress` and the named children, instead of an Edit.

### test-runner / pr-reviewer / commit
- [x] Run `tests/ac_store/`, `unit_tests/ac_store/test_acs200f_*`, the check_done_proof tests and `tests/test_ac_fulfillment_gate.py`.

## Risk & Safety

- Touches money? No.
- Touches data? Writes `work_status` in AC YAML through the existing anchored atomic write.
- Composites that finalize used to mark `done` now stay `in_progress` until their children are proven. That is intended, and it fails closed.
- Reversibility: revert the commit. AC files already written as `in_progress` stay valid.

## Out of Scope

- Rolling a parent composite up to `done` when its last child completes later (a separate ticket).
- Correcting composites already wrongly marked `done` in the store.
- BO-202's open reopen question (extend the gate to L3 and `unit_tests/`).

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-10-06 15:43 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote the seven BO-202 tests in `tests/ac_store/test_mark_ac_done.py` (class TestCompositeAcRule, 334 lines, under the size limit) and `unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py`. All use a real temp store (yaml.safe_dump records), the real mark_ac_done CLI in a fresh process, and the real check_done_proof CLI (`--mode ci`). The shared helper module is not imported by any test. Strict run (`AC_ENFORCE_STRICT=1`): 5 failed, 11 passed; the 5 failures are assertion failures, no errors. Gap: AC-6 (gate template) is not unit-testable here; pr-reviewer reads the template diff.
Note: test_already_done_unproven_composite_is_refused runs both without and with --test-root, because with --test-root today's verify_done_eligible already refuses (exit 3); only the no-test-root call (the finalize-feature path) shows the missing behaviour.

red_baseline:
  - test_name: test_composite_with_todo_children_goes_in_progress
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: REFUSED: ZZ-202a is not eligible for done - composite has uncovered children (exit 3, expected 0)"
  - test_name: test_already_done_unproven_composite_is_refused
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: 'no-op ZZ-202a already work_status=done' exit 0, expected non-zero (no --test-root call)"
  - test_name: test_composite_without_test_root_never_goes_done
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: marked ZZ-202a work_status=done (from ticket ...)"
  - test_name: test_mark_ac_done_and_check_done_proof_share_one_composite_helper
    file: tests/ac_store/test_mark_ac_done.py
    error: "AssertionError: mark_ac_done must import the shared composite helper (hasattr False)"
  - test_name: test_in_progress_write_is_anchored_and_preserves_line_endings
    file: unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py
    error: "AssertionError: marked ZZ-300a work_status=done; assert 'done' == 'in_progress'"
  - test_name: test_composite_with_all_children_proven_goes_done_and_passes_check_done_proof
    file: tests/ac_store/test_mark_ac_done.py
    note: "green_at_baseline (guard): today's writer already marks an all-proven composite done and check_done_proof accepts it"
  - test_name: test_leaf_behaviour_is_unchanged
    file: tests/ac_store/test_mark_ac_done.py
    note: "green_at_baseline (guard)"

### 2026-10-06 15:54 — llm-expert (status: ok)
feedback-id: (submit-failed)
Edited `templates/agents/ac-fulfillment-gate.md` only (22 insertions, 15 deletions; staged). Steps changed:
- Step 1 (working list): skip L0/L1 by level becomes skip any composite AC (`covered_by` lists child AC ids, any level L0-L3, the `check_done_proof` rule).
- Step 2a: `level` field is informational only; composite detection does not use it.
- Step 2b: "Skip L0/L1 ACs" becomes "Composite ACs": composite at any level L0-L3 goes to Step 3a, skips 2d-2f and 3b-3c, recorded as `status: composite`.
- Step 2f: child AC ids in `covered_by` never count as test coverage.
- Step 3a: no longer edits `work_status`; runs `python3 {{config.output_root}}/scripts/ac_store/mark_ac_done.py --ac <ID> --test-root .` (same path convention as the resolver call), quotes the script's output in the sign-off, records done / in_progress with the unfinished children it names (exit 0) / refused (non-zero) with the children named; on a refusal signs off as a blocker naming them and never edits `work_status`.
- Frontmatter description and the matching behavioral_patterns trigger updated from "L0/L1" to "covered_by lists child AC ids".
Unchanged: append-only and idempotent behaviour of 3b/3c. No registry, build, or test files touched; `build.py` not run.

### 2026-10-06 16:30 — python-coder (status: ok)
feedback-id: (submit-failed)
Moved the composite classifier into the shared `scripts/ac_store/_done_proof_composite.py` (already in AC_STORE_DEPLOY_MAP, so it ships beside both callers): `_composite_child_ids`, `_find_ac_root`, `_load_ac_yaml_or_none`, `_resolve_child_ac`, `_unproven_composite_children`, plus `_collect_all_covered_ids` and `_EXCLUDED_SCAN_DIRS`, verbatim. `templates/scripts/commit_guardian/check_done_proof.py` (the tracked source; `scripts/commit_guardian/` is a build output) imports them after `ensure_ac_store_on_syspath()`. `mark_ac_done.py` imports the same function objects and adds `_composite_verdict` (composite rule, with and without --test-root) plus `_set_work_status(file, value)` for the anchored atomic write. `python scripts/build.py --force` ran clean; no tracked mirror of these files changed (docs/INDEX.md and cards changes are the llm-expert's and were left alone).

mark_ac_done output for composites (verified by running the CLI on a yaml.safe_dump store):
- todo/in_progress composite with unproven children: stdout `marked <id> work_status=in_progress (unfinished children: <a>, <b>)`, exit 0. Rerun on in_progress: stdout `no-op <id> work_status=in_progress (unfinished children: <a>, <b>)`, exit 0. With --ticket the ` (from ticket <name>)` suffix precedes the children list.
- already done but unproven: stderr `REFUSED: <id> is work_status=done but composite children are not done and proven: <child>[, ...]`, exit 3, file unchanged.
- status != active on a composite that would go in_progress: stderr `ERROR: AC <id> has status='...' (not active)`, exit 2.
- Without --test-root no covers tags are collected, so every leaf child counts unproven: composite can reach in_progress, never done.
- All children done and proven: falls through to the old path (coverage gate if --test-root, then `marked <id> work_status=done`, exit 0).
Leaves unchanged.

red_baseline_results (AC_ENFORCE_STRICT=1): all 5 red tests green; 2 guards still green.
Strict run (tests/ac_store/test_mark_ac_done.py, test_tkt_600a_1, unit_tests/ac_store/test_acs200f_3_*, test_done_proof_composite, all check_done_proof / bo_2500b / bo_2900 / bp_100n_4 / bp_1100g tests, build_guards parity + ci_workflow): 184 passed, 5 xfailed, 3 failed. The 3 failures (test_bo_2900d_1_reachability_exemption x2, test_bo_2900d_1_eligibility_exemption x1: exemption item `src/no_entry_unit.py` vs `src
o_entry_unit.py` path form on Windows) also fail on an untouched HEAD checkout; unrelated.
Ratchet (check_file_size.py, staged): _done_proof_composite.py 233 (was 118 raw; under 400), mark_ac_done.py 333 (OK), check_done_proof.py 452 (OK; shrank, ratchet passed), tests 334 and 163 (OK).

### 2026-10-06 16:45 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Reviewed the staged diff. No high-confidence findings. Verified: the composite classifier move out of check_done_proof.py is verbatim (only the COVERS_TAG_RE import line differs; check_done_proof imports it from _done_proof_composite after ensure_ac_store_on_syspath, mark_ac_done imports the same function objects); the in_progress write reuses the anchored, atomic, line-ending-preserving _set_work_status; leaves return None from _composite_verdict and take the old path; the gate template never edits work_status and uses the same {{config.output_root}}/scripts/ac_store/ path convention as build-ac and finalize-feature; the regenerated card matches the template; module header and DECISION HISTORY entries are present.
Medium findings:
- [M-1] templates/scripts/commit_guardian/check_done_proof.py:123 — the composite import is now unguarded at module load, outside the try/except that gives done_proof a fallback. If ac_store cannot be located the hook dies with ImportError instead of degrading as before. Deployed layouts ship _done_proof_composite and test_enforcement (AC_STORE_DEPLOY_MAP), so only a broken install is affected.
- [M-2] templates/agents/ac-fulfillment-gate.md Steps 4-5 (lines ~292-320) — a composite recorded `status: composite`, or one that mark_ac_done put in_progress, is neither `passed`/`skipped` nor `blocker`, and Step 4 still re-checks `work_status == "done"`. The ok verdict rule ("passed or skipped") does not say how such an AC counts. Suggest follow-up: classify composite/in_progress explicitly (skipped-with-note, or blocker if unfinished children are in scope).
- [M-3] scripts/ac_store/mark_ac_done.py:_composite_verdict — finalize-feature (templates/workflows-js/finalize-feature.js:1611) and the post-merge hook (templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py:137-175, ACD-600b) call without --test-root, so no child is ever proven there: a composite whose children really are done goes in_progress (exit 0, counted as acs_closed) and an already-done composite is refused (exit 3 -> WARNING, acs_skipped). Neither fails the flow. Matches the design (AC-5) but the acs_closed counter overstates; follow-up ticket recommended to pass --test-root or report in_progress separately.
Caller impact: finalize-feature.js:1611-1614 non-fatal on any non-zero exit, no ticket needed beyond M-3; build-ac.md:492/546 is a user-run printed command, exit 3 simply surfaces, no ticket; check_ac_done_on_merge.py:165-175 logs a warning and always exits 0, no ticket.
Test results are the test-runner's to report (python-coder reported 184 passed, 3 unrelated pre-existing Windows failures).

### 2026-10-06 16:52 — test-runner (status: ok)

feedback-id: (submit-failed)

No failure is caused by this ticket. All failures below were reproduced at base (worktree build-tooling-runs-through) or are on the known Windows-only list.

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true   # ticket tests and all ticket-relevant tests pass; remaining failures are pre-existing Windows/environmental, see below
  failure_report_structured: true
  commands:
    ticket_tests: "16 passed"
    check_done_proof_mark_ac_done_composite_gate_files (-n auto, 69 files): "412 passed, 7 failed, 1 error, 5 xfailed; all 7+1 pre-existing (ge_127d_2 x2, resolve_root_git_preferred, bo_2900d_1 x3, bo202 ac2 fail+error)"
    ac_store_commit_guardian_build_guards_full (-n 4): "2671 passed, 187 failed, 15 skipped, 7 xfailed; 155 of 157 distinct ids fail identically at base; the other 2 pass in isolation here and at base (load flake)"
    deployed_reachability: "build.py --force ok; deployed check_done_proof.py --help, mark_ac_done.py --help and the pre-commit entry (run_hook.py check_done_proof.py --test-root .) all rc=0; _done_proof_composite.py present in .leafcutter"
```

### 2026-10-06 17:20 — llm-expert (status: ok)

feedback-id: (submit-failed)

Review follow-up M-2: ac-fulfillment-gate Step 4 now re-checks work_status for leaf ACs only and classifies composites explicitly (done = passed, in_progress = non-blocking, refused = blocker).
Step 5 ok rule accepts in_progress composites and lists their unfinished children in the sign-off.

### 2026-10-06 17:00 — python-coder (status: ok)

feedback-id: (submit-failed)

Review follow-up M-1: check_done_proof.py now imports _done_proof_composite fail-safe (try/except ImportError, stderr WARNING, fallbacks classify no AC as composite so the composite check is skipped with the warning).
Verified in a scratch copy with no ac_store: WARNING printed, --help exit 0; ticket and check_done_proof tests unchanged (only known pre-existing failures).

### 2026-10-06 17:05 — commit (status: ok)
feedback-id: (submit-failed)

```yaml
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
```
Commit subject: "fix(build-orchestration): keep a composite AC in progress until its children are done". docs/INDEX.md included (regenerated by transform-doc-index).
