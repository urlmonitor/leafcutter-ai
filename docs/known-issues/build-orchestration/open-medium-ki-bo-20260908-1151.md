---
title: "KI-BO-20260908-1151 — `documentation-verifier` parses one AC-line format and the producing template never mentions it, so a phase blocks on syntax while the documentation is present and correct"
description: "KI-BO-20260908-1151 — `documentation-verifier` parses one AC-line format and the producing template never mentions it, so a phase blocks on syntax while the documentation is present and correct"
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
  - documentation_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260908-1151 — `documentation-verifier` parses one AC-line format and the producing template never mentions it, so a phase blocks on syntax while the documentation is present and correct

> Found 2026-09-07 on `GE-122d-1`, with a second instance cross-referenced in another
> epic. Filed 2026-09-28 after re-confirming against `origin/main` at `89613071`: the
> pipe contract is still in force in `documentation-verifier.md`, and
> `documentation-expert.md` still contains the word "pipe" zero times.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 2 confirmed, in different epics
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-28 (re-verified present)
- **Where:** `templates/agents/documentation-verifier.md` Step 2 (~lines 147-169) ·
  `templates/agents/documentation-expert.md` (the producer, which never states the format) ·
  the `## Agent Contracts` → `### documentation-expert` block of generated tickets

**Symptom.** `documentation-verifier` halts with a Step 2 parse failure and the ticket cannot
reach `commit`. Its contract requires the target path to be the SECOND pipe-delimited field:

```text
- [ ] AC-1: how-to | docs/how-to/some-guide.md | must include a Verification section
              ↑ genre   ↑ target_path              ↑ content_constraint
```

`GE-122d-1` carried instead, on both AC lines:

```text
- [x] AC-1: [component-diagram] docs/architecture/components/commit-guardian.md — all three stages ...
```

Bracketed genre, em-dash constraint, **zero pipe characters**. The verifier is fail-closed on
a parse failure, so it stops before Steps 3-7 and reports the ticket blocked.

**The documentation was fine.** The verifier's own blocker comment records that the named file
exists and had in fact been updated. Nothing was missing; the ticket described what happened
in a syntax the reader could not parse. When the two lines were rewritten into the pipe form
and the verifier re-run, it signed off — and Steps 3-7 executed **for the first time**,
confirming against the real diff hunk that both content constraints held. So the blocked run
had never performed the checks the phase exists for; it had only failed to start them. A
parse failure at Step 2 is therefore not a small delay — it silently skips the entire
substance of the phase.

**It is systematic, not a one-off.** The verifier's own comment cross-references the identical
malformed shape blocking a sibling ticket in a different epic,
`EPIC-TrustThatAGreenCheckActuallyChecked/34_TICKET-20260825-GE-120e-3-ii.md`. Two epics, same
shape, same halt.

**Probable cause, and it points at a general fragility.** `documentation-expert`'s own sign-off
on `GE-122d-1` states that the `Agent` tool was unavailable in its session, so it authored the
Agent Contracts block DIRECTLY rather than dispatching its usual specialist. The pipe
convention lives only in the CONSUMER's template. Nothing on the producing side validates or
even mentions it — confirmed 2026-09-28: `grep -c "pipe" templates/agents/documentation-expert.md`
returns **0**. So the format is enforced once, at the end, by the agent least able to repair it,
and any degraded authoring path produces something the verifier will refuse.

**Countermeasure.** Stop making the format a convention two agents must independently agree on:

- State the pipe format explicitly in the PRODUCING template
  (`templates/agents/documentation-expert.md`) next to where the Agent Contracts block is
  authored, with the reason — the same WHAT/WHO framing used for `handoff_target` in
  `KI-BO-20260901-1052`, which is the identical failure class one field over.
- Better, make Step 2 report a malformed line as a REPAIRABLE finding routed back to
  `documentation-expert`, rather than a terminal halt. It already prints an exact remediation;
  nothing consumes it.
- Consider a lenient parse and reject it. On current evidence the fail-closed posture is what
  surfaced this at all, and a parser accepting both conventions would let the two formats drift
  apart indefinitely across epics. **Fix the producer, not the reader.**

**Pattern:** a format defined only in the consumer, produced by an agent that was never told
it, discovered when the consumer refuses. Three instances of this shape are now on file within
a fortnight, which suggests the class is worth a sweep rather than another point fix.

**Related.** `KI-BO-20260901-1052` (`handoff_target`: identical producer/consumer contract
split, resolved by stating the requirement in the producing templates).
`KI-BO-20260907-0851` (a third instance of one component's expectations being invisible to the
component that must meet them).
