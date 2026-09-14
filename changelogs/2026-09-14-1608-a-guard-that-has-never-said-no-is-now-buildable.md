---
title: "A guard that has never said no is now buildable"
date: "2026-09-14"
time: "16:08"
type: manual
components:
  - ac_store
  - commit_guardian
summary: "Ten acceptance-criteria records that define a check on whether protective gates actually refuse anything — rather than just existing and running — now have a test contract, so a builder can pick them up. Nothing was built, and nothing is approved yet."
description: "IT-PO enrichment only on the GE-120f subtree (nine leaves plus the parent): assigned_agent, estimated_complexity, it_requirements, test_spec, contracts and doc_links added; no criteria body touched; readiness stays draft on every record. No production code, no tests, no behaviour change."
commits:
  - 27ebece43
breaking: false
---

## Entry

### What this is not

Nothing here is built. This commit only adds a `test_spec` and `it_requirements` to ten
AC records that previously had neither, plus `assigned_agent`, `estimated_complexity`,
`contracts` and `doc_links`. Every record stays `readiness: draft`. Approval to build any
of it is the user's, not this commit's.

### Why it mattered that these ten couldn't be picked up before

`GE-120f` is the only tree in the store aimed at a specific phantom-done shape: a guard
that has never said no is not counted as protection. A protective check earns its place
by being handed something it must reject and being seen to reject it — one that has never
refused anything is UNPROVEN, not protective. Until this commit, all nine leaves carried no
`test_spec` and no `it_requirements`, so the scanner would not offer them to a builder and
they could not be honestly approved even if someone wanted to.

Nine leaves, sized: two L (`-1` builds the runner, record writer and declaration reader;
`-4` builds the registration gate and simultaneously declares, repairs, and exempts the
family that is already registered), two S, the rest M. Every leaf now carries a
`test_rationale`, an angle per descriptor, and at least one reachability descriptor and one
deployed descriptor.

### Three things worth noting before anyone builds this

**The boundary with `BP-1600a-2` is now something tests enforce, not something a note
describes.** `GE-120f` reads from the registration surface; `BP-1600a-2` walks the disk. A
check registered nowhere never touches the registration surface, so it is structurally
invisible to `GE-120f` — that split is now written into the contracts of two tests that
would FAIL a disk-walking implementation, including one requiring that a novel
`check_*.py` with no registry entry is reported by this gate not at all, in the same run
as a registration with no declaration that IS refused. This is deliberate: the family has
already had to unpick one accidental fork of the same census once, and the enrichment
exists to stop a second one.

**`GE-120f-5` moved from `documentation-expert` to `llm-expert` because of a live defect,
not a taxonomy preference.** `templates/skills/create-hook/SKILL.md` is the procedure that
actually writes a new hook registration, and its Inputs table has no field for the
declaration this gate will require at all — checked, zero matches. So on the day
`GE-120f-4`'s gate lands, an author who follows that procedure exactly would be refused by
a gate the procedure never mentions. `llm-expert` can write both markdown and a skill body;
`documentation-expert` cannot touch the skill body, so it cannot fix the actual defect.
Complexity moved S to M for the same reason.

**The script count this family would need is deliberately left unencoded.** Two different
counting rules over two different populations give four different numbers here: 57
registry entries and 72 recursively-discovered `check_*.py` scripts, against two existing
known-issue figures of 18 and 24. No single figure is written into any record in this
tree — the prohibition against hardcoding one is in the parent and every leaf, precisely
because the count keeps changing depending on how and what you count.

### Also worth knowing

The ruling that this tree overlaps `KI-TQ-007` rather than discharging it is recorded on
the L1 record. `KI-TQ-007` asks "what invokes this?"; `GE-120f` asks "can what is invoked
refuse?" A guard that is registered, invoked on every commit, and reachable, but has never
actually refused anything, would pass the first question's remedy and fail this tree's.

### Verification

None applicable — this is a store-only enrichment. AC store validation reported all 476
AC YAML files valid at the time of this commit; no test suite runs against `readiness:
draft` records.
