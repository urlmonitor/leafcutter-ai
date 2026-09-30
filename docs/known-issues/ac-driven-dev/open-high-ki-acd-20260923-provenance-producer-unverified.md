---
title: "KI-ACD-20260923-provenance-producer-unverified — a provenance-discriminator gate's entire safety property rests on prose, because nothing mechanically verifies a real producer sets the field it discriminates on"
description: "high — resolveGate() honours resume_answer.channel === \"person\" as proof a human answered, but no code path constructs that field; the only producer is a SKILL.md instruction telling an agent to set it honestly, and nothing checks that any real, non-test call site does."
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-005.md
  - docs/known-issues/README.md
---

# KI-ACD-20260923-provenance-producer-unverified — a provenance-discriminator gate's entire safety property rests on prose, because nothing mechanically verifies a real producer sets the field it discriminates on

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 observed (during `ACD-2100c-4`'s own build), structural — reachable
  on every `/plan-feature` gate resolution
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-23 (re-verified against current
  source before filing)
- **Where:** `templates/workflows-js/plan-feature.js` — `resolveGate()`'s
  `resume_answer.channel !== "person"` check (`:1671`); the only producer of that field
  is prose in `templates/skills/plan-feature/SKILL.md` §RS.3 (~:680-692)

**Symptom.** The incoming-provenance half of the `KI-ACD-005` fix (`ACD-2100c-4`) makes
`resolveGate()` honour an answer as the person's own decision only when
`resume_answer.channel === "person"`. That is the entire mechanism protecting every
`/plan-feature` approval gate from being resolved by something other than a human.
Nothing in the shipped system *produces* that field mechanically: `templates/commands/
plan-feature.md` is a one-line `Workflow("plan-feature", { userInput: $ARGUMENTS })`
dispatch with no resume/channel wiring, and the only construction site anywhere in the
repository is prose in `SKILL.md` §RS.3 instructing an agent to set `channel: "person"`
"only when genuinely relaying a real human's decision." No runtime check distinguishes
an agent that followed that instruction from one that fabricated the field to pass the
gate.

**Why the existing test does not cover this.** `unit_tests/workflows/
test_acd_2100c_4.py` (~:522-584) does assert something under the name "producer" —
but only that the SKILL.md file's *prose* documents the obligation. It is a grep-only
check on documentation, not a check that any real, non-test call site actually
constructs `resume_answer.channel: "person"`. A world where the instruction exists in
SKILL.md but no agent ever follows it, and a world where every gate is answered
honestly, both pass this test identically.

**Why it matters.** `resume_answer.channel` is exactly the shape of AC this repo has
learned to distrust by now: a discriminator whose *content* must not be inspected, only
its *provenance* — and here the provenance itself is unverified. During `ACD-2100c-4`'s
own build, `python-coder` and `test-writer` both correctly reasoned about the consumer
side and reclassified 16 newly-red sibling tests as `test_drift` — but nothing in
either agent's reasoning checked whether a producer existed at all, and the drive would
have shipped this way had it not independently stalled on an unrelated blocker first.
Any future agent (or a misbehaving/compromised one) can set `channel: "person"` on an
answer it invented itself, and `resolveGate()` has no way to tell the difference.

**Relationship to `KI-ACD-005`.** This is not a re-opening of that entry — the specific
defect it fixed (an agent's *refusal* being parsed as the user's cancel decision) is
genuinely fixed and stays fixed. This is a residual gap in the fix's own foundation,
first noted as an addendum on that resolved entry
(`docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-005.md`) and
promoted to its own open entry here because the gap is substantial enough — the entire
safety property of a provenance discriminator resting on undocumented-in-code agent
honesty — that it should not live only as a footnote on a closed issue.

**Fix direction.** Add a mechanical companion check: a reachability/producer-audit test
asserting at least one real, non-test call site in the shipped system constructs
`resume_answer.channel` before a ticket closing a provenance-discriminator AC is
allowed to sign off `ac-fulfillment-gate`. More generally, treat "the consumer side
tests green" as insufficient evidence for any AC whose Gherkin turns on a field's
provenance rather than its content — trace the producer, don't just grep for the
consumer's guard clause.

**Pattern:** a security-relevant discriminator field with exactly one producer, and that
producer is prose in a skill file rather than code — so "is this safe" and "is this an
unreachable accept path with a convention-only producer" predict identical test results.

**Related.** `KI-ACD-005` (the fix this gap sits underneath, see addendum there).
