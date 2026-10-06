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
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
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
| AC-1 | test_mark_ac_done_and_check_done_proof_share_one_composite_helper | | |
| AC-2 | test_composite_with_all_children_proven_goes_done_and_passes_check_done_proof | | |
| AC-3 | test_composite_with_todo_children_goes_in_progress, test_in_progress_write_is_anchored_and_preserves_line_endings | | |
| AC-4 | test_already_done_unproven_composite_is_refused | | |
| AC-5 | test_leaf_behaviour_is_unchanged, test_composite_without_test_root_never_goes_done | | |
| AC-6 | pr-reviewer reads the gate template diff (`tests/test_ac_fulfillment_gate.py` only checks frontmatter) | | |

## Implementation Tasks

### test-writer
- [ ] Extend `tests/ac_store/test_mark_ac_done.py` and `unit_tests/ac_store/test_acs200f_3_mark_ac_done_anchored_write.py` with real temporary stores and test roots.

### python-coder
- [ ] Move the composite helper(s) into `scripts/ac_store/_done_proof_composite.py`, and import them in `check_done_proof.py`, which shrinks.
- [ ] `mark_ac_done.py`: add the composite branch (done / in_progress / refuse), the anchored `in_progress` write and the unfinished-children message. Leaves keep today's path.
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### llm-expert
- [ ] `templates/agents/ac-fulfillment-gate.md`:
  - Step 2b (130-133, 165-168): composite means `covered_by` holds AC-id children, at any level;
  - Step 2f (201-204): child ids are not test coverage;
  - Step 3a (226-230): call `mark_ac_done.py --ac <id> --test-root .` and report its result, including `in_progress` and the named children, instead of an Edit.

### test-runner / pr-reviewer / commit
- [ ] Run `tests/ac_store/`, `unit_tests/ac_store/test_acs200f_*`, the check_done_proof tests and `tests/test_ac_fulfillment_gate.py`.

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
