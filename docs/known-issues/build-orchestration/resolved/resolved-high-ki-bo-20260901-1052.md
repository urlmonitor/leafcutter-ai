---
title: "KI-BO-20260901-1052 — `python-coder` signals a test handoff exactly as its template prescribes, and the driver rejects it for omitting a field the template never mentions — so the documented delegation path dead-ends every ticket that uses it"
description: "KI-BO-20260901-1052 — `python-coder` signals a test handoff exactly as its template prescribes, and the driver rejects it for omitting a field the template never mentions — so the documented delegation path dead-ends every ticket that uses "
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260901-1052 — `python-coder` signals a test handoff exactly as its template prescribes, and the driver rejects it for omitting a field the template never mentions — so the documented delegation path dead-ends every ticket that uses it

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (`6124e025`, PR #687, BO-3000a; verified 2026-09-25 by reading
  `python-coder.md` §"Test Delegation", the `PHASE_RESULT_SCHEMA` in both drivers, and running
  `TestHandoffTargetResolvedFromRecord` + `test_bo_3000_handoff_routing.py` — see Resolution)
- **Occurrences:** 1 (the only ticket in the batch that produced working production code)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/agents/python-coder.md` §"Test Delegation" (~:454-460) ·
  `templates/workflows-js/build-feature.js` (~:1595-1610)

**Symptom.** `GE-122d-1` was the one ticket in batch 1 that got real work done — a verified
77-line deploy-manifest fix in `scripts/build_phases.py`, checked against a live `build.py`
run. The drive then discarded the ticket with:

```text
Phase 'python-coder' returned 'status: handoff' but named no recognizable
handoff_target ('undefined'). Refusing to guess a re-dispatch target and refusing
to advance to the next phase in phaseOrder.
```

**The two sides define "handoff" differently, and neither references the other.**

`python-coder.md` §"Test Delegation" is unambiguous about the protocol, and the agent followed
it to the letter:

> 1. Add task items under the `### test-writer` section of `## Implementation Tasks`
>    describing what needs testing.
> 2. When signing off, use `(status: handoff)` instead of `(status: ok)` to signal that
>    test-writer must run next.
> 3. Do NOT create files under `unit_tests/` or any test directory.

Three steps, all performed. The target is named — in the ticket body section and again in the
returned `message` ("handed off to test-writer via a new `## Implementation Tasks` /
`### test-writer` section with the exact fix"). What the template never asks for, anywhere, is
a `handoff_target` key in the JSON return. The driver reads exactly that key and nothing else:

```js
const handoffTarget = phaseResult.handoff_target;   // undefined
```

So the agent communicated the target through the two channels its template defines — ticket
body and prose — and the driver looked in a third channel it was never told to populate.

**Why the driver's refusal is right and still produces the wrong outcome.** Refusing to guess
a re-dispatch target is correct; guessing would be worse. The defect is upstream of the
refusal: the contract the agent was given cannot produce the field the driver requires. A
fail-closed check is only as good as the contract it closes against, and here it fails closed
on conformant output.

**This is the documented happy path, not an edge case.** §"Test Delegation" exists because
`python-coder` is forbidden from writing tests: "You MUST NOT write or modify unit test files
directly." Any coder run that discovers its tests need adjusting — which the same template
makes *mandatory* for bug fixes ("every bug fix requires a regression test... add the test
requirement to the `### test-writer` section") — is routed into `status: handoff`. So the
prescribed route for a common, template-mandated situation terminates the ticket.

**What it cost.** `GE-122d-1`'s fix was complete and verified; 4 of its 6 red-baseline tests
remained red for a diagnosed test-fixture path bug (the fixture assumed a bare
`<target>/hooks/`, contradicting ADR-004's shim design) that `python-coder` correctly
classified as `test_drift` and correctly declined to fix itself. That is the system working
as designed right up to the moment the handoff was dropped. The work survives only because it
was left staged — nothing committed it, and nothing recorded that it exists.

**Countermeasure.** Make the two ends agree, in whichever direction is cheaper:

- **Have the driver accept the template's channel** — read the handoff target from the
  ticket's `## Implementation Tasks` subsection heading when `handoff_target` is absent,
  before refusing. The information is already on disk in a structured, parseable place.
- **Or add the field to the template contract** — state in §"Test Delegation" that the JSON
  return must carry `handoff_target: "test-writer"`, and add it to the result schema so a
  missing value is caught at authoring time rather than at dispatch time.

Either fixes it; doing neither leaves the delegation path unusable. The first is preferable
because it makes the *record* authoritative, consistent with how every other phase decision
in this driver is taken from the ticket read-back.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a contract split across two
components with no shared definition and no test spanning both. The agent template and the
workflow are versioned together and deployed together, and still disagree.

**Related.** `KI-BO-20260901-1000` (same run, same driver, also a dispatch decision that
ignores what the ticket record already says). Both are instances of the driver's dispatch
logic and the ticket record having drifted apart; the record is right in both cases.

## Resolution (verified 2026-09-25)

Fixed by `6124e025` (PR #687, BO-3000a), on main. It took the **second** countermeasure: it added
the field to the template contract and the result schema. It did not take the preferred one
(inferring the target from the ticket body). An early version of that commit did infer the
target from the body. That fallback was then removed on purpose, because
`## Implementation Tasks` often names several agents, and because a targetless handoff is also
how python-coder's contract-shrinkage guard asks the user for authorization. The rationale
comment sits above the handoff branch in both drivers.

- **Template side:** `templates/agents/python-coder.md` §"Test Delegation" step 2 (:458) now
  says "use `(status: handoff)` … AND return `handoff_target: "test-writer"` in your JSON result".
  The `test_drift` classification path (:602) and the frontmatter behaviour line (:142) say the
  same thing. `test-writer.md` (:530) returns `handoff_target: "python-coder"`/`"sql-coder"`.
  `signoff` SKILL (:763) and `building-epics` SKILL (:662-670) make the field mandatory for every
  phase agent on the machine-parsed path.
- **Schema side:** `PHASE_RESULT_SCHEMA` in `build-feature.js` (:292-341) and `build-ticket.js`
  (:104-151) declares `handoff_target`, and an `if status == "handoff" then required` clause
  makes it required. So the field is now visible when the agent writes its result, not first
  noticed at dispatch.
- **Driver:** with a named, known target, the driver re-dispatches exactly that agent. It
  still refuses when the target is absent or unknown, which is the intended fail-closed
  behaviour (`build-feature.js` :2019-2070, `build-ticket.js` :1640-1690).
- **Tests run (2026-09-25, main @ `d2fe85a1`):**
  - `pytest unit_tests/workflows/test_bo_3000_handoff_routing.py`: 5 passed.
  - `TestHandoffTargetResolvedFromRecord`: 5 passed, including
    `test_handoff_naming_a_known_agent_redispatches_exactly_that_agent`,
    `test_handoff_with_no_target_refuses_and_dispatches_no_agent` and
    `test_unknown_target_is_reproduced_in_the_refusal_and_never_substituted`.

**Residuals (not this defect; recorded so nobody re-files it):**

- Two tests in the same class fail on their own fixture preconditions: the ticket body did not
  keep the expected `## Implementation Tasks` sections, so they never reach their real
  assertion. They are `test_ticket_body_agent_sections_do_not_supply_a_handoff_target` and
  `test_deliberate_targetless_halt_does_not_respawn_a_body_named_agent`. That is a test-harness
  gap, not a return of this defect.
- Nine other test failures in the same run (`TestMidDrivePromotionIsDispatched` and
  `test_bo_3701_build_ticket_dispatch.py`) concern BO-3700 mid-drive promotion, which is the
  sibling `KI-BO-20260901-1000`.
- Only `python-coder` and `test-writer` spell out `handoff_target` in their own template. The
  other phase agents list `handoff` as a possible status and get the requirement only through
  the `signoff` skill.
- The schema comment notes that the engine's enforcement of JSON-Schema `if`/`then` is still
  unverified.

---
