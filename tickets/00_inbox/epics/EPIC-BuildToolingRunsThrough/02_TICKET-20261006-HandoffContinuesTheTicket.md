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
  architect-review: signed_off
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
| AC-1 | test_bo_3000c_handoff_continuation.py:test_handoff_to_agent_not_on_ticket_is_refused, test_bo_3000c_handoff_continuation.py:test_self_handoff_and_deferred_target_are_refused (cases a, b: existing BO-3000a tests) | | |
| AC-2 | test_bo_3000c_handoff_continuation.py:test_handoff_to_python_coder_runs_red_baseline_gate_first, test_bo_3000c_handoff_continuation.py:test_resolved_handoff_with_handing_phase_signed_off_continues_in_order | | |
| AC-3 | test_bo_3000c_handoff_continuation.py:test_resolved_handoff_with_handing_phase_signed_off_continues_in_order, test_bo_3000c_handoff_continuation.py:test_resolved_handoff_with_handing_phase_still_needed_reruns_it, test_bo_3000c_handoff_continuation.py:test_chain_a_to_b_to_c_requeues_every_handing_phase | | |
| AC-4 | test_bo_3000a_3700_dispatch_defects.py:test_handoff_naming_a_known_agent_redispatches_exactly_that_agent (recast), test_bo_3000c_handoff_continuation.py:test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase | | |
| AC-5 | test_bo_3000c_handoff_continuation.py:test_repeated_handoff_pair_halts_as_handoff_loop, test_bo_3000c_handoff_continuation.py:test_fourth_handoff_in_one_ticket_halts_as_handoff_loop | | |
| AC-6 | test_bo_3000c_handoff_continuation.py:test_epic_ticket_whose_handoff_resolves_completes_in_same_run | | |
| AC-7 | (not testable: skill prose; pr-reviewer reads the two skill diffs) | | |

## Implementation Tasks

### architect-review
- [x] Confirm the refusal set (a)-(e), the two caps, and that the read-back's `verified` is the only signal that a handoff resolved. Confirm `isHandoffResolved` (791-844) and completion still agree.

### test-writer
- [x] Harness `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs`, `appendSignoff` (421-429): add two opt-in spec keys.
  - `record_handoff_target` writes the `handoff_target:` line the read-back parser already reads (326-350).
  - `flips_signed_off` makes a handoff entry also mark its own agent `signed_off`.
  - Defaults keep every existing test's behaviour.
- [x] Write `unit_tests/workflows/test_bo_3000c_handoff_continuation.py`, parametrised over `_driver_harness.TWIN_DRIVERS`. Import the harness the same way `test_bo_3000a_3700_dispatch_defects.py` does.
- [x] Re-cast `TestHandoffTargetResolvedFromRecord::test_handoff_naming_a_known_agent_redispatches_exactly_that_agent` as the unresolved case (`record: false` on the re-dispatched test-writer), so its assertions still hold. Shrink the file under the ratchet rule.
- [x] These must stay green unchanged:
  - `unit_tests/workflows/test_bo_3000_handoff_routing.py` (its default `signoff-readback` stub has no `readable: true`, so the driver still halts there and pr-reviewer is never dispatched);
  - `unit_tests/workflows/test_bo_3000b_statusless_reply_schema.py`;
  - the BO-3700 tests.
- [x] (python-coder handoff) Recast `TestHandoffTargetResolvedFromRecord::test_handoff_routing_is_reachable_from_the_workflow_top_level_body` in `unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py` as the unresolved case, the same way as its sibling: the re-dispatched test-writer's record must not confirm it (`record: false` on the SECOND test-writer dispatch only), so the expected order [test-writer, python-coder, test-writer] and the `cross_agent` halt still hold. Keep the file under the ratchet (shorter by at least the measured lines it adds or changes). Dicts with more than 5 keys or parametrize tables with more than 3 rows go to a JSON fixture under `tests/fixtures/`.

### python-coder
- [x] Both twins: replace the handoff branch body after case (b) with refusals (c)-(e), the cap check, a de-duplicated unshift and `break`.
- [x] Both twins: add `handoffPairs` and `handoffFrom`, the handoff sentence in the normal dispatch prompt, and the H re-queue after `completedPhases.push`.
- [x] Add `handoff_loop` wherever a schema enum validates the halt `classification`. (No-op by architect finding 5: nothing validates halt classifications; `CLASSIFY_SCHEMA` deliberately left alone.)
- [x] Run `python scripts/build.py` and stage the tracked outputs. (No tracked mirrors of the two drivers exist; tests read `templates/workflows-js/` directly, so no build output changes.)
- [x] M-1 (pr-reviewer review follow-up): in both twins, when the handing phase H is not open and `handoffFrom[H]` exists, continue to H's origin (re-queue it), so a chain A->B->C whose middle phase signed off with its handoff still re-queues A.
- [x] M-2 (pr-reviewer review follow-up): in both twins, treat an unreadable read-back at handoff acceptance as `seen = Infinity` (so no old entry can confirm the target), or refuse the handoff.

### llm-expert
- [x] `templates/skills/building-epics/SKILL.md:659-670`: describe the driver's continuation, refusals (c)-(e) and the two caps. Keep §4's "1 per phase pair per ticket" consistent.
- [x] `templates/skills/build-feature-ops-notes/SKILL.md`: add a note on the old "handoff then re-run" behaviour, the new continuation, and how to read a `handoff_loop` halt.

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

### 2026-10-06 14:30 — architect-review (status: ok)

feedback-id: (submit-failed)

**Impact classification: large by the file-count threshold (7 files, 2 components), medium in real risk.** No always-large trigger fires: no Alembic migration, hypertable, FastAPI surface or ADR contract change. Escalation: none spawned. The caller scoped this as a direct review, and the analysis below is the deep pass; ask for a separate Opus pass if you want a second opinion.

**ADR: no. Diagram: no.**
- The only new policy (1 handoff per from-to pair, 3 per ticket, `handoff_loop`) is already recorded in the approved BO-3000a and in building-epics section 4.
- ADR-019 (the loop stays inline), ADR-030 (JS only, no new primitive) and ADR-048 (completion reads the record, never dispatch order) are all unchanged.
- The rubric says `requires_adr: true` for 2 or more components, and this ticket lists 2 (`build_orchestration`, `supervisor_system`). I judge `false` here: the second component is only a skill-prose update.
- No data flow, container or state-machine boundary is added. `docs/architecture/components/` has no page that describes the handoff halt.

**Line references at HEAD 119fca8e2 (all confirmed)**
- `build-feature.js`: handoff block 2353-2388 (log, inline `agent()` 2359-2374, `cross_agent` return 2376-2388). Cases (a) 2304-2331 and (b) 2336-2351 stay. `attemptedPhases` is at 2041, the dispatch prompt at 2171-2194, the verdict at 2237, `completedPhases.push` at 2506.
- `build-ticket.js`: 1979-2014, `attemptedPhases` 1674, prompt 1806-1816, push 2124.
- Measured sizes match the ticket: 2964 / 1647 / 873 (harness .mjs; the raw `wc -l` of 1138 is not the measured figure) / 633.
- The classification enums at `build-feature.js:382` and `build-ticket.js:169` are `CLASSIFY_SCHEMA`, the failure-classifier's reply. They are NOT the driver's halt classification. Do NOT add `handoff_loop` to them: that would let the LLM classifier emit it. Nothing else validates halt classifications, so the python-coder task "add handoff_loop wherever a schema enum validates the halt classification" is a no-op. Delete it.

**Loop fit (no double dispatch)**
- The branch sits inside `while (retryLoop)` inside `while (pendingPhases.length)`. `retryLoop` is false at that point, so `break` leaves the inner loop and the next outer iteration shifts the target. This is the same exit the cross_agent-skip path already uses.
- The handing phase H already ran `dispatchedAgents.push`, the read-back and `absorbPromotedPhases`. It reaches neither `completedPhases` nor `unverifiedPhases`, so the handoff `break` leaves no stale entry. Completion reads the record, per ADR-048.
- `absorbPromotedPhases` skips every name in `attemptedPhases`. So neither the target T nor H can be re-absorbed behind the explicit unshift. The only double-dispatch risk is a pending copy of T, which the de-duplicated unshift removes.
- Use ONE small helper for both the T unshift and the H re-queue: remove any pending copy of the name, then put it at the head.
- The head item is consumed by the very next iteration, before any later `absorbPromotedPhases` re-sort, so the re-sort cannot displace it.
- `completedPhases` gets a second entry when T already completed earlier (the existing test shape: test-writer done, python-coder hands off to it). `writtenPhaseEntries` is keyed by agent, so this is harmless.
- `retryCounts` is shared across the re-dispatch. A re-dispatched T keeps its retry count, which is fine.
- One edge: a handoff to a coder while test-writer is still pending runs the coder first. The BO-2000e-2 guard then blocks it as `halt` when `hasTestRequirements` is false. That fails closed and is acceptable. Mention it in the ops note.

**FINDING 1 (decide in the implementation): `verdict.verified` alone does not prove the target acted.**
- `adjudicatePhaseAgainstRecord` (`build-feature.js:861`) verifies a phase when its LATEST entry is passing. A target that already signed off before the handoff (the BO-3000a test shape: test-writer ok, python-coder hands off to test-writer) is verified by its OLD entry even if the re-dispatch wrote nothing.
- The driver would then continue, while `isHandoffResolved` (791-844) at completion needs a target entry AFTER the handoff entry and would report the handoff unresolved. So the two checks disagree, and the ticket burns phases before being refused at the end.
- The recast "unresolved" test could also pass for the wrong reason: if `record: false` is per agent and not per dispatch, the FIRST test-writer dispatch is already unverified.
- Fix: record the target's sign-off entry count when the handoff is accepted, `signoffEntriesFor(phaseRecord, T).length` from H's read-back, which is already in scope. Treat the target as confirmed only when `verdict.verified && verdict.entries > thatCount`.
- This is the same read-back and no new reader, so BO-400e-1-i holds. It is exactly "a target the record cannot confirm" (F1), so no decision is reopened.
- The harness stub for the recast test must therefore make the SECOND test-writer dispatch write no entry, with the first writing one. Check how `record: false` is scoped in `unit_tests/prompt_assembly/_driver_harness.py`.

**FINDING 2: AC-4 needs an explicit halt.**
- In the normal loop an unverified phase is only pushed to `unverifiedPhases` and the drive carries on (`build-feature.js` ~2490-2497). The ticket's "halt exactly as today" does NOT come for free.
- In the `!verdict.verified` branch, when this phase was dispatched as a handoff target, return the old `blocked` / `cross_agent` object with `handoff_target` and `failing_phase` set to H, and no `handoff_result`. Add the same condition for the freshness test in Finding 1.
- `test_bo_3000_handoff_routing.py`'s default stub has no `readable: true`, so it lands here and keeps halting.

**FINDING 3: the test text for `test_resolved_handoff_with_handing_phase_still_needed_reruns_it` is garbled.**
- Its order `[tw, pc, tw, pc, pr-reviewer]` only happens when python-coder (H) hands off to test-writer (T, already done) and stays needed. T runs ok and is confirmed; H re-runs and is ok.
- As written ("test-writer hands off to python-coder"), the de-dup removes the pending python-coder copy and gives `[tw, pc, tw, pr-reviewer]`. Test-writer must fix the `asserts:` direction before writing the test. This does not change the code design.

**FINDING 4: handoff chains.**
- If A hands off to B and B hands off to C, B's own "handed off by A" context must survive until B completes. Otherwise A is never re-queued and the record shows A still needed.
- Do not delete `handoffFrom[T]` on dispatch. Delete it only when T completes verified, after the H re-queue check. Capture `const from = handoffFrom[phaseName]` once at the top of the outer iteration, so a mechanical retry still carries the sentence.
- Append the "RE-DISPATCHED ... Handoff message" sentence only on the dispatch where T was freshly queued by a handoff.

**Twin parity.** The two drivers agree structurally. The drift that exists is cosmetic or epic-only:
- indent and quote style;
- `worktreeTicketPath` (feature) vs `ticketPath` (ticket);
- the "re-run /build-feature" vs "/build-ticket" wording;
- the BO-3700 vs BO-3701 comment labels;
- `depends_on` in the feature-only read-back schema;
- `deferredPhases` is `["pull-request"]` for an epic member in feature and always `[]` in ticket.

None of this blocks a shared implementation:
- Refusal (e) can be one line in both, `deferredPhases.includes(T)`, with no epic-only branch in the ticket driver.
- Refusal (d) must read the plan's `orderedPhases` (`build-feature.js:1879` / `build-ticket.js:1508`), which lists EVERY key of the agents map including `not_needed`. Do not use `neededPhases` (the frozen opening set) or `plannedPhaseNames`.
- Refusal order: (a), (b), then (c), (d), (e). A self-name is in `phaseOrder`, so (c) is reachable.
- Only the epic scenario test (AC-6) is feature-only.

**File-size ratchet: it does NOT fit inline. Plan the budget first.**
- The rule is `new_length <= previous - gross_added`, so removed lines must be at least 2x added lines, per file.
- The deleted inline block gives 36 lines (2353-2388), so up to 18 added lines are affordable from that alone. A direct implementation is about 45-50 added lines:
  - refusals c-e ~10;
  - cap check and the `handoff_loop` return ~10;
  - unshift helper and call ~4;
  - maps and the `from` capture ~3;
  - prompt sentence ~3;
  - H re-queue ~6;
  - AC-4 halt ~10.
- So each file needs about 55-60 more removed measured lines.
- Cheapest real savings, measure each against `resolve_added_measured_lines` before committing:
  1. Collapse cases (a) and (b), which are two near-identical 14-line `return {...}` objects, plus the new (c)-(e), into one small local `refuse(message)` helper that builds the `{status, message, ticket_path, failing_phase, blocker_detail, classification: "halt"}` object. Keep each message text exactly as-is, since existing tests pin the wording. Saves about 10-12 lines per file net.
  2. Use a single `handoffChain` array of `"A->B"` strings instead of the `handoffPairs` map. Pair count is `chain.filter(...)`, ticket count is `chain.length`, and the halt message names the chain. Push BEFORE the cap check so the fourth, rejected step is named (test 4 wants all four).
  3. The `//` prose blocks count as measured lines; `/* */` content does not. The 22-line BO-3000/BO-3000a history comment above the branch (2278-2299 / 1904-1926) and the long BO-1900d-1 pointer-block rationale (~2150-2170) can be condensed into a short `/* */` block. The history lives in BO-3000a.yaml. It is a legal measured reduction, but pr-reviewer should confirm no unique rationale is lost.
  4. The red-baseline gate return objects and other long duplicated `return {...}` shapes are candidates only if the above is not enough. Do not touch behaviour.
- Do NOT move the decision into Python through an `agent()` command call. ADR-030 allows no filesystem in the workflow body, and a status-checker round trip for a pure sync decision adds latency and a failure mode, and runs against the fail-closed intent.
- Test ratchet: `harness_build_ticket_guard.mjs` is 873 / 1000, so the two opt-in keys (about 10-15 lines) fit. `test_bo_3000a_3700_dispatch_defects.py` is 633 / 400: the recast must come out shorter than the lines it adds.

**Binding-decision check.** Nothing in section 1a or F1 is impossible in the code. The wording-level adjustments are Findings 1, 2 and 3, and the no-op task above.

**Implementation guidance (coder)**
1. Both twins in one commit. Add near `attemptedPhases`: `const handoffChain = []`, `const handoffFrom = {}`, and the two cap constants. Add at the top of the outer iteration: `const from = handoffFrom[phaseName]`.
2. Handoff branch after (b): compute `why` for self / not-in-`orderedPhases` / deferred and `refuse(...)`. Push `H->T` onto the chain. If the pair count is over 1 or the chain length is over 3, return `blocked` with `classification: "handoff_loop"` naming the chain. Otherwise set `handoffFrom[T] = {from: H, message, seen}` (seen = T's entry count in H's read-back), put T at the head with the helper, and `break`. Keep the log line.
3. Dispatch prompt: append the existing "RE-DISPATCHED ... Handoff message" sentence when `from` is set. Leave the pointer block untouched.
4. Verification point: in the `!verdict.verified` branch, and when `verdict.entries <= from.seen`, return the cross_agent halt when `from` is set (Finding 2).
5. After `completedPhases.push` (verified, fresh): if `from`, read H from the same `phaseRecord`. If H is in `needed_phases` or `failed_phases`, put H at the head with the helper. Then delete `handoffFrom[phaseName]`.
6. Run `python scripts/build.py`, stage the mirrors, and run `check-file-size` on both drivers before the commit.
7. Test-writer: fix the `asserts:` direction of test 2 (Finding 3). Make the recast test stub write no entry on the second test-writer dispatch only (Finding 1). Add a case where the target's old entry is stale and the re-dispatch writes nothing, and assert the cross_agent halt. Add a chain case A to B to C (Finding 4) if budget allows.

### 2026-10-06 16:55 — test-writer (status: ok)

feedback-id: (submit-failed)

completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "harness_build_ticket_guard.mjs phase stubs writing real sign-off entries (with handoff_target: and the self-flip) into the on-disk ticket record"
    consuming_side: "build-feature.js and build-ticket.js: the record read-back, the handoff branch and the completion decision, driven unmodified"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "templates/workflows-js/build-feature.js and build-ticket.js top-level bodies executed under harness_build_ticket_guard.mjs (and run_workflow_under_e2 for the gate case) via _driver_harness.TWIN_DRIVERS"

Wrote `unit_tests/workflows/test_bo_3000c_handoff_continuation.py` (28 parametrised cases over TWIN_DRIVERS; epic cases build-feature.js only), added the two opt-in keys `record_handoff_target` and `flips_signed_off` to the .mjs harness (873 -> 876 measured lines), and recast the BO-3000a case in `test_bo_3000a_3700_dispatch_defects.py` as the unresolved case (633 -> 622 measured lines; no new tests added there).

Corrections applied from the architect-review comment:
- **Test 2 direction (finding 3).** `test_resolved_handoff_with_handing_phase_still_needed_reruns_it` is written the other way round from its `asserts:` text. python-coder (the handing phase) hands off to the already-done test-writer (the target) and stays needed. The order `[test-writer, python-coder, test-writer, python-coder, pr-reviewer]` follows from that. The ticket's wording, "test-writer hands off to python-coder", would give `[tw, pc, tw, pr-reviewer]` because the de-dup removes the pending python-coder.
- **Stale entry (finding 1).** The recast and the `stale_entry` variant of `test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase` make only the SECOND test-writer dispatch write no entry (the harness scopes `record: false` per dispatch through the result array). The target's old passing entry exists and must not confirm the handoff. They are tagged `angle: discrimination` and pass at baseline, so a driver that confirms on `verdict.verified` alone turns them red.
- **Finding 5.** No test for the "add handoff_loop to schema enums" task.
- **Chains.** `test_chain_a_to_b_to_c_requeues_every_handing_phase` pins A->B->C re-queueing B, then A.

Classification: n/a (new tests only; no failing existing test was repaired). Four BO-3700 tests and two BO-3000a tests in `test_bo_3000a_3700_dispatch_defects.py` fail under `AC_ENFORCE_STRICT=1` identically with and without my edits (checked against HEAD versions of the two files). They are not caused by this ticket; the two BO-3000a ones are the strict-mode "covers a not-done AC" report.

Strict run (`AC_ENFORCE_STRICT=1 python -m pytest ... -q -p no:cacheprovider`): every test that pins new behaviour fails with an AssertionError, none errors. Green at baseline (guards): the six `test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase` cases, and the recast test.

red_baseline:
  - test_name: test_resolved_handoff_with_handing_phase_signed_off_continues_in_order[both twins]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['architect-review', 'test-writer'] != [..., 'python-coder', 'pr-reviewer']"
  - test_name: test_resolved_handoff_with_handing_phase_still_needed_reruns_it[both twins]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'test-writer'] != [..., 'python-coder', 'pr-reviewer']"
  - test_name: test_chain_a_to_b_to_c_requeues_every_handing_phase[both twins]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'sql-coder'] != [... 7 entries]"
  - test_name: test_repeated_handoff_pair_halts_as_handoff_loop[both twins]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'test-writer'] != [..., 'python-coder']"
  - test_name: test_fourth_handoff_in_one_ticket_halts_as_handoff_loop[both twins]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'test-writer'] != [..., 'sql-coder', 'python-coder']"
  - test_name: test_handoff_to_agent_not_on_ticket_is_refused[both twins x not_on_ticket, not_needed]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'sql-coder'] != ['test-writer', 'python-coder'] (refused case) / != [..., 'sql-coder', 'python-coder'] (not_needed case)"
  - test_name: test_self_handoff_and_deferred_target_are_refused[self x2 twins, deferred x build-feature.js]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'python-coder'] != ['test-writer', 'python-coder'] (self); ['test-writer', 'python-coder', 'pull-request'] != [...] (deferred)"
  - test_name: test_handoff_to_python_coder_runs_red_baseline_gate_first[both twins x gate passes, gate fails]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: assert 'red-baseline-gate' in ['ticket-planner', 'architect-review', 'signoff-readback', 'python-coder']"
  - test_name: test_epic_ticket_whose_handoff_resolves_completes_in_same_run
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: assert not [{'ticket_path': '...01_first.md', 'status': 'blocked', ... re-run /build-feature ...}] (halted_tickets)"
  - test_name: test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase[6 cases]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "green_at_baseline (guard): passes today because the driver always halts cross_agent; goes red under a verified-only confirmation (stale_entry) or a missing fail-closed halt"
  - test_name: test_handoff_naming_a_known_agent_redispatches_exactly_that_agent
    file: unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py
    error: "green_at_baseline (guard): recast as the unresolved case; passes today (cross_agent halt after [test-writer, python-coder, test-writer])"

### 2026-10-06 17:40 — llm-expert (status: ok)

feedback-id: (submit-failed)

completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true

- `templates/skills/building-epics/SKILL.md`: extended the "two handoff readers" note with the continuation (target runs the normal loop, handing phase re-queued, chains, epic completes in the same run), refusals (c)-(e), fail-closed confirmation and the `handoff_loop` halt. Added a "Handoff continuation" row to the §4 caps table (1 per from-to pair, 3 per ticket), kept distinct from the §3.2 sibling-respawn cap.
- `templates/skills/build-feature-ops-notes/SKILL.md`: the file had no "re-run after a handoff" note, so added KI-8: old halt-then-re-run behaviour, new continuation, refusals, and how to read a `cross_agent` or `handoff_loop` halt.

### 2026-10-06 18:05 — python-coder (status: handoff)

feedback-id: (submit-failed)

handoff_target: test-writer

Handing to test-writer for ONE assertion-only fix; production is correct. `TestHandoffTargetResolvedFromRecord::test_handoff_routing_is_reachable_from_the_workflow_top_level_body` (`unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py`) still encodes the old halt-after-handoff behaviour: its re-dispatched test-writer writes a normal `ok` entry, so under binding decision F1 the handoff is confirmed and the ticket continues (observed order with an LF record: [test-writer, python-coder, test-writer, python-coder], then the second python-coder to test-writer step trips `handoff_loop`). Its recast sibling `test_handoff_naming_a_known_agent_redispatches_exactly_that_agent` is already right. Fix: make the SECOND test-writer dispatch write no entry (`record: false` scoped per dispatch via the result array), as the sibling does. (classification: test_drift)

Change (both twins, `templates/workflows-js/build-feature.js` and `build-ticket.js`, same change):
- Handoff branch: cases (a)/(b) collapsed into one `refuse(message, classification, extra)` closure (texts unchanged). New refusals (c) self handoff, (d) target not in `orderedPhases` (keeps not_needed keys, so a not_needed target is honoured), (e) target in `deferredPhases`. One `handoffChain` array, pushed BEFORE the cap check; MAX_HANDOFFS_PER_PAIR=1 / MAX_HANDOFFS_PER_TICKET=3; a breach halts `handoff_loop` naming the whole chain. `handoff_loop` is NOT added to CLASSIFY_SCHEMA (finding 5).
- Accepted handoff: `handoffFrom[T] = {from, message, seen}` with `seen` = T's entry count from H's own read-back (finding 1); `queuePhaseFirst` (one new pure helper, de-duplicated) puts T first; `break`. No inline agent() call any more, so T gets the pointer block, test guard, red-baseline gate (existing once-per-drive gate path), read-back and promotions.
- `from` captured once at the top of the outer iteration; the dispatch prompt carries the "RE-DISPATCHED ... Handoff message" sentence when set.
- Verification point, fail closed: `from && !(verdict.verified && verdict.entries > from.seen)` returns `blocked` / `cross_agent` with `handoff_target` = T and `failing_phase` = H; no later phase runs.
- After `completedPhases.push`: if H is in the read-back's needed_phases or failed_phases, `queuePhaseFirst(H)`; then `delete handoffFrom[T]` (so A to B to C re-queues B, then A).
- Epic completion needed no extra code: a resolved handoff no longer returns `blocked`, so the halted filter never sees it.
- `refuse` also replaced three duplicated return objects in the blocker adjudication (mechanical exhausted, design/halt, unknown). Long `//` history blocks in the driver loop were moved into `/* */` comments (content kept, requirement and AC ids kept) to pay the ratchet.

Ratchet (`_file_size_ratchet`, HEAD vs staged): build-feature.js 2958 -> 2768 (added 104, allowed <= 2854); build-ticket.js 1642 -> 1452 (added 98, allowed <= 1544). `check_file_size.py` on both drivers: PASSED. `node --check` on both: ok.

Strict results (`AC_ENFORCE_STRICT=1`; 98 driver-touching test files plus `test_bo_3000*`, `test_tq500f3ii_*` and `unit_tests/prompt_assembly`):
- Windows CRLF trap: `_driver_harness.write_ticket_record` writes CRLF, so the `.mjs` harness frontmatter regexes never match and every completion-dependent test fails on this machine at base too. Plain run: mine 133 failed / 656 passed; base 121 failed. The extra failures in mine are the new 3000c completion tests (CRLF; absent at base) plus the stale test above.
- With a local-only LF plugin (scratchpad `lfopen`, not committed): mine 31 failed / 704 passed; base 30 failed / 672 passed. The ONLY node failing in mine and not at base is the stale test above. All 28 cases of `test_bo_3000c_handoff_continuation.py` pass (including the 6 unconfirmed/stale_entry guard cases), as do `test_bo_3000_handoff_routing.py`, `test_bo_3000b_*` and the recast `test_handoff_naming_a_known_agent_redispatches_exactly_that_agent`.
- The known pre-existing local failures in `test_bo_3000a_3700_dispatch_defects.py` (4 BO-3700 + 2 body-section) are unchanged.

red_baseline_results:
  - test_name: test_resolved_handoff_with_handing_phase_signed_off_continues_in_order
    result: green
  - test_name: test_resolved_handoff_with_handing_phase_still_needed_reruns_it
    result: green
  - test_name: test_chain_a_to_b_to_c_requeues_every_handing_phase
    result: green
  - test_name: test_repeated_handoff_pair_halts_as_handoff_loop
    result: green
  - test_name: test_fourth_handoff_in_one_ticket_halts_as_handoff_loop
    result: green
  - test_name: test_handoff_to_agent_not_on_ticket_is_refused
    result: green
  - test_name: test_self_handoff_and_deferred_target_are_refused
    result: green
  - test_name: test_handoff_to_python_coder_runs_red_baseline_gate_first
    result: green
  - test_name: test_epic_ticket_whose_handoff_resolves_completes_in_same_run
    result: green
  - test_name: test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase
    result: green
  - test_name: test_handoff_naming_a_known_agent_redispatches_exactly_that_agent
    result: green

### 2026-10-06 19:10 — test-writer (status: ok)
feedback-id: (submit-failed)
Recast `test_handoff_routing_is_reachable_from_the_workflow_top_level_body` so the SECOND test-writer dispatch writes no entry (`record: False`); order [test-writer, python-coder, test-writer] and the `cross_agent` halt hold, sign-off count is now 1 (classification: test_drift).
File 622 -> 620 lines (ratchet OK); with the LF plugin both recast tests pass, 3 other failures in the file are the known pre-existing ones.

### 2026-10-06 22:10 — pr-reviewer (status: blocker)

feedback-id: (submit-failed)

Verdict: one high finding (ticket file hygiene, one-byte fix); the driver code is approved. Re-run pr-reviewer after the fix, or sign off directly.

High
- [H-1] 02_TICKET-20261006-HandoffContinuesTheTicket.md, heading "### 2026-10-06 19:10 ? test-writer (status: ok)" (about line 511): the dash is the single byte 0x97 (cp1252), not UTF-8 U+2014. The whole file, staged blob included, no longer decodes as UTF-8, and the comment parser regex rejects the heading. Fix: replace that byte with the UTF-8 em dash (e2 80 94), in a binary-safe way; an Edit-tool rewrite turns it into U+FFFD, which is just as bad.

Medium
- [M-1] build-feature.js:2552-2556 and build-ticket.js, same block after `completedPhases.push`: the handing-phase re-queue fires only when the target T completes and the handing phase H is still needed/failed. In a chain A->B->C where B signed off with its handoff (flips_signed_off) while A is still needed, B is not re-queued, so `handoffFrom[B]` never completes and A is never re-queued. Nothing double-dispatches and the completion check still fails closed on A being `needed`, but the ticket halts instead of continuing, contrary to F1. The chain test covers only the case where B stays needed. Suggest: when H is not open and `handoffFrom[H]` exists, carry on to H's origin.
- [M-2] build-feature.js (handoff branch, `seen: signoffEntriesFor(phaseRecord, target).length`): if H's own read-back was unreadable, `seen` is 0, so a target with an older passing entry that writes nothing is confirmed once the record is readable again. Needs an unreadable read-back at the handoff plus a readable one right after, so it is unlikely. Suggest `seen = Infinity` (or refuse) when `phaseRecord.readable !== true`. Same in build-ticket.js.

Checked and fine
- Confirmation `verdict.verified && verdict.entries > from.seen`: `seen` is the target's entry count (signoffEntriesFor) in H's own read-back taken right after H's dispatch. `entries` is always a number (0 when unreadable or empty), so the comparison can never be undefined and fails closed.
- refuse(): the mechanical-exhausted, design/halt and unknown returns have the same keys, key order and values as HEAD (status, message, ticket_path, failing_phase, blocker_detail, classification, suggested_action for design/halt only); `classification || "unknown"` kept.
- Scenarios walked, no double dispatch: resolved/H signed_off; resolved/H needed; A->B->C (B needed); repeated pair; 4th handoff (chain pushed before the check, so the refused step is named); self; target not on ticket; not_needed target (honoured); deferred target (feature only); unconfirmed target (no entry, stale entry, unreadable); handoff to a coder before the red-baseline gate (gate runs once, before the coder). `absorbPromotedPhases` skips attempted names and runs before the handoff unshift; `queuePhaseFirst` de-duplicates; `break` leaves the retry loop with retryLoop false; the mechanical retry reuses the outer `from`.
- Ratchet: all requirement and AC ids preserved (BO-3000a gains mentions, nothing lost); `node --check` passes on both twins; no executable lines joined. Rationale prose for cases (a)/(b) and the BO-3000 history was shortened (low, not reported further).
- Skill prose matches the code (caps 1 per pair / 3 per ticket, refusals c-e, new-entry confirmation, handoff_loop); the one overstatement is "Chains A->B->C re-queue B, then A", which holds only when B is still open (M-1).
- Tests drive the real twins; `record_handoff_target` and `flips_signed_off` are opt-in and leave other tests untouched.

Twin-parity differences (all non-behavioural except epic):
1. `ticketPath` vs `worktreeTicketPath` in `refuse`.
2. Message wording `/build-ticket` vs `/build-feature` (refusal c-e and unconfirmed-target messages).
3. Indent and quote style.
4. `deferredPhases` is `["pull-request"]` for an epic member in feature and always `[]` in ticket, so refusal (e) is reachable only in build-feature.
5. Position of the unconfirmed-target check and the H re-queue differs only in indentation; same logic.
6. Epic completion path (halted filter) exists only in build-feature.

### 2026-10-07 10:00 — python-coder (status: ok)

feedback-id: (submit-failed)

Review follow-up, both twins (`build-feature.js`, `build-ticket.js`), same change.
- M-1: after a target is confirmed, the re-queue now walks the chain. If the handing phase is open it is re-queued; otherwise its own `handoffFrom` link is resolved (deleted) and the walk continues to that link's origin. A chain A to B to C whose middle phase signed off with its handoff now re-queues A.
- M-2: `seen` is `Infinity` when the handing phase's own read-back is not readable at acceptance, so an older passing entry can never confirm the target; the drive stops `cross_agent`.
- `templates/skills/building-epics/SKILL.md` makes no chain claim that this fix contradicts; no change needed there.

Ratchet (HEAD vs staged): build-feature.js 2958 -> 2776 (added 112, allowed <= 2846); build-ticket.js 1642 -> 1460 (added 106, allowed <= 1536). `check_file_size.py` PASSED; `node --check` ok on both.

Tests (`AC_ENFORCE_STRICT=1 python -m pytest unit_tests/workflows/test_bo_3000*.py -p lfopen`, LF plugin): 3 failed / 54 passed. All `test_bo_3000c_handoff_continuation.py` cases pass, including the 4 new M-1/M-2 cases; the 3 failures are the known base failures in `test_bo_3000a_3700_dispatch_defects.py`.

## Escalation

Branch: none
Reason: no always-large trigger fired; 7 files exceed the file-count threshold, but the caller scoped this as a direct review and the deep analysis is above.

### 2026-10-06 05:56 — test-runner (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Scope: unit_tests/workflows/test_bo_3000*.py, then unit_tests/workflows + prompt_assembly + build_orchestration in full, all with AC_ENFORCE_STRICT=1. LF plugin note: lfopen (local-only, scratchpad, never copied into the repo) is needed because _driver_harness.write_ticket_record writes CRLF on this machine; Linux CI is unaffected.
- bo_3000 plain: 17 failed, 36 passed (14 subtests passed); every 3000c failure is the CRLF trap. bo_3000 with LF: 3 failed, 50 passed (all 3 in test_bo_3000a_3700_dispatch_defects.py, and all 3 also fail at base).
- Full three dirs with LF, this worktree: 82 failed, 1264 passed, 4 xfailed, 1 error. Base (119fca8e2, no tickets 01/02): 82 failed, 1231 passed, 4 xfailed, 1 error. Failing-node sets (FAILED, ERROR, SUBFAILED) are identical.
- Attributable to this ticket: 0. Pre-existing (fail identically at base): 82 failed + 1 error. Flakes: none observed (no node failed only here, so no serial re-run was needed; the two tq500f3ii failures are identical at base).
- Pass delta of +33 over base is the new test_bo_3000c file (3000c: 0 failures with LF).

### 2026-10-06 23:30 — test-writer (status: ok)
feedback-id: (submit-failed)
Review follow-up (pr-reviewer M-1, M-2): added two failing tests to `unit_tests/workflows/test_bo_3000c_handoff_continuation.py`, each parametrised over both twins, plus an opt-in harness key `unreadable_readback_after_phase` in `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` (one read-back of the record reports `readable: false`, later ones are normal).
red_baseline:
  - test_name: test_chain_whose_middle_phase_signs_off_with_its_handoff_requeues_the_origin[build-feature.js]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'sql-coder', 'test-writer', 'pr-reviewer'] != [... 'test-writer', 'python-coder', 'pr-reviewer'] (origin python-coder not re-queued after the target confirmed)"
  - test_name: test_chain_whose_middle_phase_signs_off_with_its_handoff_requeues_the_origin[build-ticket.js]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: ['test-writer', 'python-coder', 'sql-coder', 'test-writer', 'pr-reviewer'] != [... 'test-writer', 'python-coder', 'pr-reviewer'] (origin python-coder not re-queued after the target confirmed)"
  - test_name: test_unreadable_readback_at_handoff_does_not_confirm_an_old_target_entry[build-feature.js]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: assert 'ok' == 'blocked' (dispatched test-writer, python-coder, test-writer, python-coder, pr-reviewer; the old entry confirmed the target)"
  - test_name: test_unreadable_readback_at_handoff_does_not_confirm_an_old_target_entry[build-ticket.js]
    file: unit_tests/workflows/test_bo_3000c_handoff_continuation.py
    error: "AssertionError: assert 'ok' == 'blocked' (dispatched test-writer, python-coder, test-writer, python-coder, pr-reviewer; the old entry confirmed the target)"

### 2026-10-07 06:58 — pr-reviewer (status: ok)
feedback-id: (submit-failed)

Re-review of the fixes for my 2026-10-06 22:10 blocker. All three findings closed; no high or medium findings remain.
- H-1 closed: the file decodes as UTF-8 and every comment heading matches `### YYYY-MM-DD HH:MM — <agent> (status: ...)`.
- M-1 closed: the chain walk after confirmation terminates, because each pass deletes one `handoffFrom` entry or breaks. `queuePhaseFirst` de-dups, so a phase is never queued twice. A link is deleted only when its phase is no longer open. A mechanical retry mid-chain leaves `handoffFrom` untouched, because it is cleared only on a verified confirmation.
- M-2 closed: `seen` is `Infinity` on an unreadable read-back, so `verdict.entries > from.seen` always fails closed. Only the acceptance site and the one comparison read `from.seen`.
- Twin parity: the two fixes are identical in build-feature.js and build-ticket.js apart from indentation. `node --check` passes on both. check_file_size passes (build-feature.js 2776, build-ticket.js 1460).
- The harness key `unreadable_readback_after_phase` is opt-in and one-shot, so other tests are unaffected. The 3000c and 3000a tests pass except 4 `TestMidDrivePromotionIsDispatched` failures, which fail identically at HEAD (not caused by this diff).

### 2026-10-07 07:10 — commit (status: ok)
feedback-id: (submit-failed)

```yaml
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
```
Subject: fix(build-orchestration): continue the ticket after a confirmed handoff
