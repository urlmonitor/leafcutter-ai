---
title: "KI-ACD-20260831-agent-contracts-block-not-pipe-delimited — the generator writes the documentation-expert contract as prose, and `documentation-verifier` fail-closes on every generated ticket that has one, before it looks at a single doc"
description: "KI-ACD-20260831-agent-contracts-block-not-pipe-delimited — the generator writes the documentation-expert contract as prose, and `documentation-verifier` fail-closes on every generated ticket that has one, before it looks at a single doc"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-20260831-agent-contracts-block-not-pipe-delimited — the generator writes the documentation-expert contract as prose, and `documentation-verifier` fail-closes on every generated ticket that has one, before it looks at a single doc

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** the ticket generator's `## Agent Contracts` → `### documentation-expert` block
  (`generate_ticket_from_ac.py` / `goal_to_epic.py` output), read by
  `templates/agents/documentation-verifier.md` Step 2's parse contract
- **Id form:** date-slug; this register is still sequential to `KI-ACD-023`, but sequential
  numbering is retired (see `KI-KM-20260826-id-convention-diverged-across-registers`)

**Symptom.** Driving ticket 01 of `EPIC-TrustThatAGreenCheckActuallyChecked` to completion,
`documentation-verifier` returned `status: blocker` — not because a required doc was missing, but
because it could not parse the block naming which docs were required. Its own sign-off says the
doc it would have checked **is present in the diff**:

> "the `### documentation-expert` Agent Contracts block's only AC line (AC-1) is not
> pipe-delimited, so the required-docs list cannot be parsed. Per this agent's mandatory
> fail-closed posture, a parse failure emits (status: blocker), never (status: ok), **regardless
> of whether the referenced doc (`docs/architecture/components/commit-guardian.md`) actually
> appears in the diff**."

**Scale — this is not one ticket.** Measured by extracting each ticket's
`### documentation-expert` block and testing only the `- [ ] AC-N:` lines inside it:

```
parseable (all AC lines piped) :  0
malformed (>=1 AC line unpiped): 25
no AC-N lines at all           : 12
```

**Every applicable ticket carried the unparseable shape — 25 of 25, none correct.** The 12
without a block are exactly the tickets where `documentation-expert` is not in the agents map, so
their absence is correct. Each of the 25 would fail-closed at `documentation-verifier`, priority
11.9 — after the coder, tests, review and AC gates have all passed, immediately before `commit`.

> **Measurement caution, recorded because it caught the first attempt.** A whole-file
> `grep -l "AC-1: .*|"` reports 2 tickets as correct. Both are false: the pipe it matches is in
> `documentation-verifier`'s own blocker comment, which quotes the *expected* format as
> remediation advice. Any scan of this defect must be scoped to the `### documentation-expert`
> block, or the tool's own error message is counted as a fix.

**Resolved in this epic 2026-08-31** by rewriting all 25 lines to
`AC-N: <genre> | <path> | <constraint>`; re-measured 25/25 parseable. The generator is unchanged,
so the next generated epic will reproduce it — see
`KI-BP-20260831-generator-emits-unparseable-doc-contract` for the source-side entry.

**Cause.** The verifier's Step 2 expects
`- [x] AC-1: <doc-type> | <path> | <requirement>`. The generator emits the AC text as prose with
no delimiters, so the field split yields nothing and the required-docs list is empty. Fail-closed
is the *correct* posture for an unparseable contract — the defect is upstream, in the producer
writing a shape its documented consumer cannot read. Neither side is individually wrong; they
were never checked against each other.

**Why it survived.** The two formats have no shared schema and no test that round-trips generator
output through the verifier's parser. The failure also only surfaces at the very end of a full
ticket drive, which costs ~1.3M subagent tokens to reach — so it is expensive to discover and
trivially reproducible only in hindsight.

**Fix direction.** Fix the generator to emit the pipe-delimited form, since the verifier's
contract is the documented one and two tickets already comply. Then add a round-trip test: take
generator output and run the verifier's Step 2 parser over it, asserting a non-empty required-docs
list — that is the check whose absence let two components disagree silently. For the 35 tickets
already on disk, a mechanical rewrite of the AC-1 line is enough; they need no re-generation.
Consider also having the verifier name the *expected* format in its blocker text, which would have
made this diagnosable from the first sign-off rather than the second.

**Related.** `KI-ACD-022` (conditional phase agents written into the agents map without the
frontmatter fields they are conditional on — the same producer/consumer mismatch class).
`KI-ACD-016`, `KI-ACD-018`, `KI-ACD-021`, `KI-ACD-023` (the other generator-output defects).

**Pattern:** a producer and its documented consumer that were never run against each other, where
the consumer's correct fail-closed posture converts the mismatch into a universal block.

---
