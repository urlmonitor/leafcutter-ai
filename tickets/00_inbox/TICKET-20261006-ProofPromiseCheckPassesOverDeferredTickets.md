---
title: "Proof-promise check: pass over deferred tickets the way it passes over planned ones"
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-10-06
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
roadmap_phase: phase_1
tags:
  - proof-promise
  - pre-commit
  - ticket-lifecycle
last_updated: 2026-10-06
files_touched:
  - templates/scripts/commit_guardian/check_proof_promise_claim.py
  - unit_tests/commit_guardian/test_bp_1100g_4_ii.py
  - docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g-4-ii.yaml
agents:
  test-writer: signed_off
  python-coder: signed_off
  commit: signed_off
---

# Proof-promise check: pass over deferred tickets the way it passes over planned ones

## Actor / Goal
In order to park a ticket (`status: deferred`) without inventing tests for work nobody will do,
we need `check-proof-promise-claim` to pass over deferred tickets the same way it passes over
`status: todo` ones, so that deferring a ticket is never blocked by a proof that is not due.

## Context
- **Hit 2026-10-06.** Deferring TICKET-20260923-BO-4100a-1 and its `-1-i` child was blocked.
  Their scope is covered by epic BO-4300, so they were set to `status: deferred`, and the commit
  was refused for promised proofs with no test claiming them. Neither ticket was ever started.
- `templates/scripts/commit_guardian/check_proof_promise_claim.py` exempts only
  `_STILL_PLANNED_STATUS = "todo"` (BP-1100g-4-ii). Every other state is examined.
- The parent requirement BP-1100g-4 says the refusal belongs at **hand-off**. A deferred ticket
  is parked, not offered for hand-off, so no claim is due yet. Passing it over is consistent with
  the parent.
- **This reverses an explicit constraint.** BP-1100g-4-ii's constraints say
  "Exempt ONLY the still-planned state. Everything else — started, offered, blocked, deferred —
  remains subject to the check." The user decided on 2026-10-06 (option "a") that `deferred` joins
  `todo` as not yet due. `in_progress`, `blocked`, `done` and every unreadable or unknown state
  stay examined, so the guard against "exempt anything not finished" is kept.

## Scope
1. **Amend BP-1100g-4-ii.** In `criteria`, `constraints` and `title`, the passed-over set becomes
   "still planned (`todo`) or parked (`deferred`)". Add an `amended_by` entry citing this ticket and
   the user decision. Keep `in_progress` and `blocked` named as still examined.
2. **Hook.** Pass over `status: deferred` exactly as `todo`. The PASSED OVER line must name the
   real status: today it hard-codes "still declared status: todo". A deferred ticket must read as
   parked, not as planned. Do not change promise extraction, the claim index, the comparison or the
   refusal wording. Unreadable, missing or unknown status still fails closed (examined). Add a
   DECISION HISTORY entry.
3. **Rebuild** with `python scripts/build.py --target-dir .`. The tests execute the **deployed** hook
   as a subprocess, so an unrebuilt tree runs the old copy. Then `git restore` the build's
   side effects on tracked files (`LEAFCUTTER_VERSION`, `docs/agents/cards`).

## Out of Scope
- Closing BO-4100a-1 / -1-i: a separate commit on the same branch, after this lands.
- Any change to which proofs count as claims.

## Test Requirements

```yaml
tests:
  - name: test_deferred_work_with_an_unclaimed_promise_is_passed_over_and_says_so
    location: unit_tests/commit_guardian/test_bp_1100g_4_ii_parked.py
    type: behavioral
    covers: BP-1100g-4-ii
    description: |
      The executed (deployed) check, run over a staged ticket declaring status: deferred that
      carries an unclaimed promised kind, exits 0 and states in its output that the ticket was
      passed over, naming status deferred (not "todo"). It is red today: deferred is examined
      and refused.

  - name: test_the_same_work_once_blocked_is_still_refused_by_name
    location: unit_tests/commit_guardian/test_bp_1100g_4_ii_parked.py
    type: behavioral
    covers: BP-1100g-4-ii
    description: |
      Byte-identical work apart from status: blocked is refused with a non-zero exit, naming the
      ticket and the unclaimed kind. This is the mutation guard against widening the exemption to
      "anything not finished". It is green today and must stay green.
```

## Comments

### 2026-10-06 06:26 — test-writer (status: ok)
feedback-id: fb_2026-10-06_7deb8f6b
red_baseline:
  - test_name: test_deferred_work_with_an_unclaimed_promise_is_passed_over_and_says_so
    file: unit_tests/commit_guardian/test_bp_1100g_4_ii.py
    error: "AssertionError: 1 != 0 : deferred (parked) work with an unclaimed promise must not be refused: stdout='ZZ-BP1100G4II-LIFECYCLE: promised 'reachability' proof ... was never claimed by any test ...'"
completion_manifest:
  tests_written: true
  new_tests_red_as_required: true
  mutation_guard_green_and_stays_green: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "staged ticket fixture built by the real yaml.dump serializer (_build_ticket_fixture)"
    consuming_side: "deployed check_proof_promise_claim.py run via run_hook.py as a subprocess (status gate in main())"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/check_proof_promise_claim.py <ticket> (pre-commit hook runner, subprocess)"
Added two behavioral tests to the existing file. The deferred test is red (exit 1, refused today); the status: blocked test is a mutation guard that is green today. Both execute the deployed hook; no source-reading tests. The deferred test also asserts the output names "deferred" and not "todo", so a fix that only widens the exemption but keeps the hard-coded wording stays red. This ticket has no ## Sign-offs section, so only frontmatter and this comment were edited.

### 2026-10-06 07:00 — python-coder (status: ok)
feedback-id: (submit-failed)
red_baseline_results:
  - test_name: test_deferred_work_with_an_unclaimed_promise_is_passed_over_and_says_so
    result: green
guard: test_the_same_work_once_blocked_is_still_refused_by_name stays green.
Hook now passes over any status in _NOT_YET_DUE_STATUSES (todo, deferred); the PASSED OVER line prints the real status and words deferred as parked. AC BP-1100g-4-ii widened and amended. Rebuilt; AC_ENFORCE_STRICT=1 pytest over 4-ii, 4, 4-i: 14 passed; ruff clean; LF-only; ast.parse ok.

### 2026-10-06 06:32 — commit (status: ok)
feedback-id: fb_2026-10-06_259d8eb9
Auto-authorized commit gate: subject "fix(proof-promise): pass over deferred tickets like planned ones"; staged files: changelog entry, BP-1100g-4-ii.yaml, check_proof_promise_claim.py, this ticket, test_bp_1100g_4_ii.py.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-06 06:37 — test-writer (status: ok)
feedback-id: fb_2026-10-06_031aa150
Split-only follow-up (GE-127a-1 size gate). Moved TestDeferredWorkWithAnUnclaimedPromiseIsPassedOverAndSaysSo and TestTheSameWorkOnceBlockedIsStillRefusedByName into unit_tests/commit_guardian/test_bp_1100g_4_ii_parked.py; shared helpers extracted (not duplicated) to unit_tests/commit_guardian/_bp_1100g_4_ii_fixture.py, imported by both files per the _ge_127e_1_fixture.py pattern. Same 7 tests, same assertions, covers/angle tags kept. Test Requirements locations and BP-1100g-4-ii covered_by updated.
