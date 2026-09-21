---
title: "KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket"
description: "KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket"
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

# KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `## Agent Contracts` →
  `### documentation-expert` emitter

**Symptom.** `documentation-verifier` (priority 11.9, immediately before `commit`)
parses each `- [ ] AC-N:` line under `### documentation-expert` as three pipe-delimited
fields, `<genre> | <target_path> | <content_constraint>`, and emits `(status: blocker)`
on any line without them. The generator emits no pipes at all:

```
- [ ] AC-1: [(unspecified genre)] templates/agents/ac-fulfillment-gate.md — <criterion text>
```

So the verifier fail-closes at Step 2 on **every** generated ticket whose source AC
carries `doc_links`, and the documentation phase is never actually verified. Because the
blocker is correctly classified `cross_agent` (it names the ticket generator as the
responsible sibling), the phase is *skipped* — and the build still reports `status: ok`.

A second defect sits in the same line: `target_path` is populated from the AC's
`doc_links` **`describes`** entries, which point at whatever the AC references —
frequently an agent template or a Python module, not a documentation file. Even with
pipes added, the path named is often not a doc.

**Evidence.** `TICKET-20260818-ACD-1900b-5-i.md:262` carried exactly one such line,
naming `templates/agents/ac-fulfillment-gate.md` as the documentation target. The
verifier blocked with "Agent Contracts line is malformed (no pipe-delimited
target_path)". Repaired by hand on that branch — naming the two docs
`documentation-expert` actually wrote — so the phase could run; the generator itself is
unchanged and will reproduce this on the next generated ticket.

**Occurrence 2 — 2026-08-26, `TICKET-20260825-BP-900g-8.md:263`, during PR #578.** The
generator reproduced the malformed line exactly as predicted above, and the drive played
out precisely as the first occurrence describes: `documentation-verifier` fail-closed,
the blocker was classified `cross_agent`, and the phase was skipped. Repaired by hand on
that branch again. Two things this occurrence adds:

**A third defect in the same line: the contract is emitted even when the AC says no
documentation exists.** `_resolve_doc_genres` (`:1841-1849`) reads the parent L1's
`documentation_triggers`; when that list is **empty** it logs a WARNING and returns the
`["(unspecified genre)"]` marker — then the caller emits the contract line anyway. But an
empty `documentation_triggers` is not a missing value. It is the AC store's way of saying
*this change requires no documentation*, and `BP-900g.yaml:23-24` says exactly that, with
a written rationale that the change introduces no user-facing surface. So the generator
takes a deliberate "no docs" declaration, converts it to a marker meaning "genre unknown",
and emits a documentation obligation the parent AC explicitly disclaims.

That turns the malformed-line defect into a compounding one. `documentation-verifier`
blocks on the missing pipes; repair the pipes and it blocks again, this time demanding a
document the governing AC states must not exist. There is no form of the line that both
parses and is satisfiable. On BP-900g-8 the only correct resolution was to record the
verifier as `not_needed` — verified against its own dispatch condition
(`requires_documentation_verification`, absent from the ticket) rather than against the
line it was choking on.

**The warning is real but goes nowhere.** Unlike the pipe defect, this one *does* log at
WARNING naming the AC. It is emitted at ticket-generation time, into the generator's
stderr, hours or days before the drive that trips over it — nothing carries it forward to
the drive, and no gate reads it. A warning whose only consumer is a human watching a
one-off command is, in practice, silence.

**Fix direction.** Three changes, in increasing order of value:

1. Emit the pipe-delimited format the verifier documents.
2. Source `target_path` from the docs the change *requires* (the `creates`/`modifies`
   doc_links, or the `requires_documentation` types) rather than from `describes`
   back-references.
3. **Distinguish "no documentation required" from "genre unknown."** An empty
   `documentation_triggers` on the parent should suppress the `### documentation-expert`
   subsection entirely — and, correspondingly, should stop the generator marking
   `documentation-expert: needed` in the agents map. Only a parent that is genuinely
   *unresolvable* warrants the `(unspecified genre)` marker. Distinguishing these is what
   stops the pipe fix from converting one blocker into another.

Whatever lands should be covered by a test that runs the generator and then runs the
verifier's Step 2 parser over the output — the two sides have disagreed silently, which is
the same producer/consumer divergence class as the `ac_traceability` shape mismatch that
`ACD-1900b-5-i` fixes. Add a second case for the empty-`documentation_triggers` parent,
asserting that **no** contract line is emitted at all.

---
