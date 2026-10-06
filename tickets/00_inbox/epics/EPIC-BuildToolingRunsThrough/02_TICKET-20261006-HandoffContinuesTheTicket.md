---
title: "A handoff runs its target through the normal phase loop and the ticket continues"
status: todo
components:
  - build_orchestration
  - supervisor_system
created: 2026-10-06
depends_on:
  - 01_TICKET-20261006-GateUsesProjectInterpreter.md
priority: high
complexity: high
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: BO-3000a
ac_traceability:
  id: BO-3000a
  path: docs/acceptance-criteria/build-orchestration/BO-3000a.yaml
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - prompt
risk_surface: contract_boundary
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
  - unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py
  - unit_tests/workflows/test_bo_3000c_handoff_continuation.py  # new
  - templates/skills/building-epics/SKILL.md
  - templates/skills/build-feature-ops-notes/SKILL.md
agents:
  architect-review: needed
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

# 02: A handoff runs its target through the normal phase loop and the ticket continues

## Actor / Goal

As the build driver, I want a valid handoff to put its target back into the normal
phase loop, and the ticket to continue once the record confirms the target's
sign-off. Then a ticket whose phase hands off finishes in the same run. The target
also gets every check a normal dispatch gets: the test guard, the red-baseline gate,
the record read-back and the phase promotions.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 1a). Implements BO-3000a as
amended on this branch (user decision F1, 2026-10-06): a handoff re-dispatches the
target, then the ticket continues. It halts only on a repeated pair, the per-ticket
cap (3), or a target the record cannot confirm.

**Root cause**
- `templates/workflows-js/build-feature.js:2353-2388` (twin `build-ticket.js:1979-2014`):
  - after a valid `handoff_target`, the driver calls `agent()` inline for the target (2359-2374);
  - it then always returns `status: "blocked", classification: "cross_agent"`, saying "re-run /build-feature" (2376-2388).
- In an epic, the halted filter (`build-feature.js:3497-3505`) catches that `blocked` result, and the epic returns (3507-3662).
- **Hidden second defect.** The inline dispatch skips everything the normal dispatch path does:
  - the BO-1900d-1 pointer block (`ticket_path:` / `worktree_path:`);
  - the record read-back and its check (2207-2237);
  - `dispatchedAgents`, `absorbPromotedPhases` and the `tests_written` evidence;
  - the test-requirements guard (2053) and the red-baseline gate (2107).

  So a handoff to python-coder runs the coder with no test guard and no gate. Signoff skill §6.3 even uses architect-review → python-coder as its example.

**Intended behaviour**
1. Keep refusals (a) "no target" and (b) "target not in phaseOrder" exactly as they are.
2. Add refusals that dispatch nobody:
   - (c) the target is the handing phase itself;
   - (d) the target is not a key in this ticket's `agents` map (a key marked `not_needed` is allowed);
   - (e) the target is deferred for this drive (pull-request for an epic member).
3. Otherwise put the target at the head of `pendingPhases`, removing any pending copy, with handoff context (from-phase and message). It then runs through the normal loop.
4. When the target returns ok and the record confirms it (`verdict.verified`), look at the handing phase H in that same read-back:
   - if H is in `needed_phases` or `failed_phases`, run H next;
   - if H is `signed_off`, continue in normal order.

   `isHandoffResolved` (791-844, BO-400e-1-i) already treats the second case as resolved at completion.
5. If the target's ok cannot be confirmed (not verified, or the record cannot be read), halt exactly as today (`cross_agent`, `handoff_target`). This fails closed.
6. Caps:
   - `MAX_HANDOFFS_PER_PAIR = 1` honoured handoff per (from→to) per drive, matching building-epics §4;
   - `MAX_HANDOFFS_PER_TICKET = 3` as a backstop against cycles;
   - exceeding either halts with `classification: "handoff_loop"`, naming the chain.
7. A target that itself returns a handoff goes through the same branch. Blocker and failed use the existing adjudication.

**Minimal change (both twins, same commit)**
- Replace the handoff branch body after case (b) (2353-2388 / 1979-2014) with: refusals (c)-(e), the cap check, a de-duplicated unshift, and `break`.
- Add `handoffPairs` and `handoffFrom` maps beside `attemptedPhases` (2041 / 1674).
- When `handoffFrom[phaseName]` is set, append the existing "RE-DISPATCHED… Handoff message" sentence (now at 2361 / 1987) to the normal dispatch prompt (2171-2194 / 1806-1816).
- After `completedPhases.push` (2506 / 2124), add the H re-queue check.
- Deleting the inline block (about 36 lines) pays for the additions.

## Constraints

- **Twins.** `build-feature.js` and `build-ticket.js` change together, in the same commit. Every new test runs against both through `_driver_harness.TWIN_DRIVERS`.
- **File-size ratchet (GE-127b-1, GE-127f-2).** `build-feature.js` measures 2964 / 1000 and `build-ticket.js` 1647 / 1000. Each staged file may measure at most `previous − gross measured lines added` (a changed line counts as added). So in each twin the deleted inline block must outweigh the added lines **twice over**, not just match them. `//` comment lines count; `/* */` content does not. Keep decisions small. If the cap or refusal logic grows, move it into a small pure helper instead of adding inline lines.
- **Test-file ratchet.** `unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py` measures 633 / 400. Re-casting its test must leave the file shorter by at least the measured lines it adds or changes. `harness_build_ticket_guard.mjs` measures 873 / 1000: keep it at or below 1000, because crossing the limit is refused.
- **Build mirrors.** After the template edits, run `python scripts/build.py` and stage every tracked output it changes.
- **Lane parity (TQ-500f-3-ii).** A handoff to a coder must pass through the same red-baseline gate as a first dispatch. The gate's command and verdict are unchanged.

## Acceptance Criteria

- [ ] AC-1: Refusals (a) "no target" and (b) "not in phaseOrder" are unchanged. New refusals that dispatch nobody: (c) self-handoff, (d) a target that is not a key in the ticket's `agents` map (a `not_needed` key is allowed), and (e) a target deferred for this drive (pull-request for an epic member). Each refusal says which case held.
- [ ] AC-2: An accepted handoff puts the target at the head of `pendingPhases`, removing any pending copy, and dispatches it through the normal loop. The pointer block, the test-requirements guard, the red-baseline gate (before a coder), the record read-back and the phase promotions all apply. The dispatch prompt carries the "RE-DISPATCHED… Handoff message" sentence, naming the from-phase and its message.
- [ ] AC-3: When the target returns ok and the read-back confirms it (`verdict.verified`), the handing phase H runs next if that read-back lists H in `needed_phases` or `failed_phases`. If H is `signed_off`, the drive continues in phaseOrder. Either way the ticket can complete in the same run.
- [ ] AC-4: When the target's ok cannot be confirmed (not verified, or the record cannot be read), the drive halts exactly as today, with `classification: "cross_agent"` and the `handoff_target` named.
- [ ] AC-5: At most 1 handoff is honoured per (from→to) pair and at most 3 per ticket in one drive. Exceeding either halts with `classification: "handoff_loop"`, naming the chain, and no later phase runs.
- [ ] AC-6: In an epic (`build-feature.js`), a ticket whose handoff resolves completes in the same run, and the halted filter does not catch it.
- [ ] AC-7: `templates/skills/building-epics/SKILL.md` (the "two handoff readers" note, 659-670) and `templates/skills/build-feature-ops-notes/SKILL.md` describe the continuation, refusals (c)-(e) and both caps.

## Test Requirements

```yaml
tests:
  - name: test_resolved_handoff_with_handing_phase_signed_off_continues_in_order
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Parametrised over _driver_harness.TWIN_DRIVERS: architect-review hands off
      to test-writer and its record entry flips itself signed_off
      (flips_signed_off); test-writer returns ok with a readable, verified
      record. The dispatch order is [architect-review, test-writer,
      python-coder, pr-reviewer, ...], test-writer is dispatched exactly once,
      and the ticket completes with no cross_agent halt.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_resolved_handoff_with_handing_phase_still_needed_reruns_it
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Both twins: test-writer hands off to python-coder and stays needed;
      python-coder returns ok and the record confirms it. The dispatch order is
      [test-writer, python-coder, test-writer, python-coder, pr-reviewer, ...],
      and the ticket completes in the same run.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_repeated_handoff_pair_halts_as_handoff_loop
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Both twins: the same from-to pair hands off a second time in one drive.
      The drive halts with classification handoff_loop, the halt message names
      the chain, the target is not dispatched a second time for that pair, and
      pr-reviewer is never dispatched.
    framework: pytest
    type: integration
    angle: failure
  - name: test_fourth_handoff_in_one_ticket_halts_as_handoff_loop
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Both twins: three distinct from-to pairs are honoured. A fourth handoff
      (a new pair) halts with classification handoff_loop, naming all four
      steps, and its target is not dispatched.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_handoff_to_agent_not_on_ticket_is_refused
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Both twins: a handoff_target that is in phaseOrder but is not a key in the
      ticket's agents map dispatches nobody, and the refusal names the target
      and the "not on this ticket" case. A target present as not_needed is
      accepted and dispatched.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_self_handoff_and_deferred_target_are_refused
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      Both twins: a phase naming itself as handoff_target dispatches nobody, and
      the refusal names the self-handoff case. In build-feature.js, an epic
      member handing off to pull-request (deferred for the drive) dispatches
      nobody, and the refusal names the deferred case.
    framework: pytest
    type: integration
    angle: failure
  - name: test_handoff_to_python_coder_runs_red_baseline_gate_first
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
      - TQ-500f-3-ii
    asserts: >-
      Both twins, using the harness from the E2 gate tests, on a ticket with
      source_ac: architect-review hands off to python-coder. A
      "red-baseline-gate" dispatch is recorded before the python-coder dispatch,
      and with a failing gate verdict python-coder is never dispatched.
    framework: pytest
    type: integration
    angle: seam
  - name: test_epic_ticket_whose_handoff_resolves_completes_in_same_run
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    covers:
      - BO-3000a
    asserts: >-
      build-feature.js only, with an epic_scenario: a ticket whose
      architect-review hands off and resolves ends completed in the epic's
      batch results, is not listed among halted tickets, and a later-batch
      ticket that depends on it is built in the same run.
    framework: pytest
    type: integration
    angle: reachability
  - name: test_handoff_naming_a_known_agent_redispatches_exactly_that_agent
    file: unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py
    covers:
      - BO-3000a
    asserts: >-
      Existing test in TestHandoffTargetResolvedFromRecord, recast as the
      unresolved case: the re-dispatched test-writer's record is not confirmed
      (record false). The dispatch order is still [test-writer, python-coder,
      test-writer] and the drive halts with classification cross_agent, naming
      the handoff_target.
    framework: pytest
    type: integration
    angle: failure
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_handoff_to_agent_not_on_ticket_is_refused, test_self_handoff_and_deferred_target_are_refused (cases a, b: existing BO-3000a tests) | | |
| AC-2 | test_handoff_to_python_coder_runs_red_baseline_gate_first, test_resolved_handoff_with_handing_phase_signed_off_continues_in_order | | |
| AC-3 | test_resolved_handoff_with_handing_phase_signed_off_continues_in_order, test_resolved_handoff_with_handing_phase_still_needed_reruns_it | | |
| AC-4 | test_handoff_naming_a_known_agent_redispatches_exactly_that_agent (recast) | | |
| AC-5 | test_repeated_handoff_pair_halts_as_handoff_loop, test_fourth_handoff_in_one_ticket_halts_as_handoff_loop | | |
| AC-6 | test_epic_ticket_whose_handoff_resolves_completes_in_same_run | | |
| AC-7 | pr-reviewer reads the two skill diffs | | |

## Implementation Tasks

### architect-review
- [ ] Confirm the refusal set (a)-(e), the two caps, and that the read-back's `verified` is the only signal that a handoff resolved. Confirm `isHandoffResolved` (791-844) and completion still agree.

### test-writer
- [ ] Harness `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs`, `appendSignoff` (421-429): add two opt-in spec keys.
  - `record_handoff_target` writes the `handoff_target:` line the read-back parser already reads (326-350).
  - `flips_signed_off` makes a handoff entry also mark its own agent `signed_off`.
  - Defaults keep every existing test's behaviour.
- [ ] Write `unit_tests/workflows/test_bo_3000c_handoff_continuation.py`, parametrised over `_driver_harness.TWIN_DRIVERS`. Import the harness the same way `test_bo_3000a_3700_dispatch_defects.py` does.
- [ ] Re-cast `TestHandoffTargetResolvedFromRecord::test_handoff_naming_a_known_agent_redispatches_exactly_that_agent` as the unresolved case (`record: false` on the re-dispatched test-writer), so its assertions still hold. Shrink the file under the ratchet rule.
- [ ] These must stay green unchanged:
  - `unit_tests/workflows/test_bo_3000_handoff_routing.py` (its default `signoff-readback` stub has no `readable: true`, so the driver still halts there and pr-reviewer is never dispatched);
  - `unit_tests/workflows/test_bo_3000b_statusless_reply_schema.py`;
  - the BO-3700 tests.

### python-coder
- [ ] Both twins: replace the handoff branch body after case (b) with refusals (c)-(e), the cap check, a de-duplicated unshift and `break`.
- [ ] Both twins: add `handoffPairs` and `handoffFrom`, the handoff sentence in the normal dispatch prompt, and the H re-queue after `completedPhases.push`.
- [ ] Add `handoff_loop` wherever a schema enum validates the halt `classification`.
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### llm-expert
- [ ] `templates/skills/building-epics/SKILL.md:659-670`: describe the driver's continuation, refusals (c)-(e) and the two caps. Keep §4's "1 per phase pair per ticket" consistent.
- [ ] `templates/skills/build-feature-ops-notes/SKILL.md`: add a note on the old "handoff then re-run" behaviour, the new continuation, and how to read a `handoff_loop` halt.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/workflows/test_bo_3000*`, `unit_tests/prompt_assembly/test_bo_400e_1_i*` and the BO-3700 tests. pr-reviewer checks twin parity and that check-file-size passes on every touched file.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- The twins can drift apart. The parametrised tests enforce parity.
- This does not fix the status-checker handoff loop. A status-checker that hands off and stays `needed` now hits the pair cap; ticket 05 removes the cause.
- Reversibility: revert the commit. The halt-after-handoff behaviour returns.

## Out of Scope

- Recording and reusing the red-baseline gate's pass (ticket 03).
- The epic loop's behaviour after a halt (ticket 04).
- The ticket-supervisor agent's prose-based handoff routing. Only the JS drivers change.

## Comments

_(Append-only log — leave blank when authoring.)_
