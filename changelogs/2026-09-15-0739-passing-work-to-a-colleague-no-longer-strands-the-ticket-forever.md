---
title: "Passing work to a colleague no longer strands the ticket forever"
date: "2026-09-15"
time: "07:39"
type: manual
components:
  - build_orchestration
  - supervisor_system
summary: "When one agent finished by handing its work to a colleague, the system refused to ever call that work finished — not because anything was wrong, but because it only recognised two ways of saying 'done' and a handover was neither. The ticket could not close, and no amount of re-running helped, because nothing would ever ask that agent to speak again. A handover now counts as finished once the colleague it named has actually picked the work up — and still blocks when nobody did."
description: "POSITIVE_SIGNOFF_STATUSES was ['ok','signed_off'], so completionVerdictFromRecord reported any phase whose latest entry read 'handoff' as outstanding. Unresolvable: selectDispatchableByStatus dispatches only needed/failed phases, so a signed_off phase is never re-dispatched and can never append an 'ok'. New isHandoffResolved(record, agentName, latest) resolves the recipient named in the record and requires a passing entry strictly after the handover; a later hand-back naming the phase reopens it; an absent target fails closed. Required extending RECORD_READBACK_SCHEMA's signoffs[] item with an optional handoff_target and asking readTicketRecordBack() for it — the same move H-1 made for failed_phases — plus an additive handoff_target: body-line convention in harness_build_ticket_guard.mjs's parseRecord() and an optional third tuple element in _driver_harness.py so fixtures can express a recipient. Both twins changed together per BO-400a-2-ii. Six tests across both drivers; 154 passed / 152 subtests, up from 153/150. New AC BO-400e-1-i under BO-400e-1."
commits:
  - ee9d7fb6e
breaking: false
---

## Entry

### Two ways to say done, and a phase that used a third

The sign-off protocol gives a phase agent several ways to end its turn. Two of
them — `ok` and `signed_off` — were the only ones the completion write accepted
as finished. A third, `handoff`, is what an agent records when it completes its
own part and passes the remainder to a named colleague. The `signoff` skill's
own routing table calls it *"Phase completed and explicitly hands to a named
sibling."*

The drivers disagreed with that document, and the drivers decide the close.

### Why no amount of re-running helped

The refusal was not merely wrong, it was permanent. A phase is only re-dispatched
while its frontmatter reads `needed` or `failed`. A phase that handed work on is
`signed_off`, so it is never dispatched again — and therefore can never append
the `ok` the check was holding out for. The record was frozen in a state the
check would not accept and nothing could change.

Observed on ticket 01 of `EPIC-WorkIsOnlyEverMarkedFinishedThroughThe`: three
consecutive `/build-feature` runs refused the same ticket for the same reason.
Every other surface agreed the phase was finished — frontmatter `signed_off`,
Sign-offs checkbox ticked, the colleague it handed to completed twenty-five
minutes later, and a reviewer independently re-verified the work. Only the status
tag on one comment dissented, and that one tag was decisive.

### The one-line fix would have been worse than the bug

Adding `handoff` to the accepted set is a one-line change that makes all the
symptoms go away. It also means a **dangling** handover passes: work handed to a
colleague who never ran would read as accounted for, and the close would succeed
with real work missing. That is a silent phantom-done in place of a loud
deadlock — strictly the worse trade, and precisely what the BO-400e family exists
to prevent.

So the acceptance is conditional. A handover resolves only when the recipient
**named in the record** has a passing entry strictly **after** it. A later
hand-back naming that phase reopens it. An absent or unreadable target fails
closed: a handover whose recipient cannot be determined has not been shown to be
resolved.

Three of the six tests exist solely to make the one-line shortcut fail.

### A proxy that passed every test, and was still wrong

The first implementation could not resolve the recipient, because the read-back
schema carried only `{agent, status}` per sign-off. It substituted a proxy: the
record's globally-last entry being a pass by anyone other than the handing agent.

All five tests at the time went green. The hole survived anyway — an unrelated
later phase's `ok` would discharge a handover its recipient never touched — and
none of the counter-cases caught it, because all three placed the dangling
handoff last and nothing exercised what came after.

It was rejected and replaced by extending the schema, which is what this same
family had already done hours earlier when H-1 added `failed_phases` for exactly
the same reason. When the record cannot express what the decision needs, the fix
is to teach the read-back to report it, not to find something else lying nearby
that correlates.

The test harness followed: `parseRecord()` built sign-offs from the heading regex
alone, so no fixture could say "this handover named test-writer". It now reads a
`handoff_target:` body line, additively — an entry without one behaves exactly as
before.

### Proving the hole, rather than asserting it

The test that guards the rejected proxy passes against unmodified `main` too,
because unmodified `main` blocks every handover and so blocks that one as well —
for the wrong reason. Green told us nothing.

So the rejected predicate was restored into the real driver and the test re-run.
It failed, reporting:

```
ticket_completed: True, recorded_status: 'done'
```

A ticket recorded **done** while the handed-off work had never happened. That is
the phantom-done hole, observed rather than argued. The probe was reverted and
the suite confirmed green again.

### Verification

- Mutation proof against pristine main: both drivers stashed → 3 failed;
  restored → green.
- The rejected-proxy proof above, run against the real driver and reverted.
- `unit_tests/prompt_assembly`: 154 passed, 152 subtests — up from 153/150, the
  one new test and no regression. All under `AC_ENFORCE_STRICT=1`, without which
  a failing test covering a not-yet-done AC is masked as xfail.
- `node --check` clean on both drivers and the harness.

`check-file-size` was skipped. The two drivers were already 2.8× and 1.5× over a
limit introduced the previous day, and the prescribed sub-module split is
unavailable: workflow scripts are self-contained by the Workflow tool's contract,
and all eight contain zero imports. Nothing this change could honestly fix was
skipped — the new test files were split at authoring time and all pass the gate.
The oversized-workflow-body debt is real, predates this work, and still needs its
own piece of work.
