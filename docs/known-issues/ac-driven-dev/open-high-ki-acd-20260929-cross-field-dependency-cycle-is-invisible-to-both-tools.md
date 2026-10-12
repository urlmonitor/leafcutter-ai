---
title: "KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY"
description: "KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY"
type: reference
category: reference
status: active
created: '2026-09-29'
last_updated: '2026-09-30'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY

- **Severity:** high
- **Status:** open
- **Occurrences:** 2 (both in the same AC tree: `TQ-600a-1-i`/`-1-ii`, then `TQ-600a-2`/`-5`)
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-29
- **Where:** `templates/scripts/commit_guardian/check_ac_circular_deps.py`
  (`_build_depends_graph`, `_extract_depends_on`); `scripts/ac_store/_gtfa_store.py`
  (`_build_ticket_depends_on`, `_expects_from_ac_ids`)

**Symptom.** `TQ-600a-5` declared `depends_on: TQ-600a-2`, while `TQ-600a-2`'s
`expects_from` named `TQ-600a-5` as its **sole** permitted routing input. Each record
therefore required the other to exist first, and neither could be generated honestly.
Nothing refused. `generate_ticket_from_ac.py` produced a ticket and reported **READY**
(with warnings), and the resulting ticket's own Implementation Notes forbade the only
approach its truncated `depends_on` left available.

**Two independent tools miss it, for two different reasons.**

1. **The cycle gate cannot see the edge.** `check_ac_circular_deps.py` builds its
   adjacency list purely from `depends_on` — `_extract_depends_on` is its only edge
   source and the file contains **zero** occurrences of `expects_from`. A cycle whose
   two halves live in different fields is not a cycle in the graph it constructs, so the
   gate is not failing to detect this cycle; it is structurally incapable of
   representing it.
2. **The generator drops the edge rather than refusing.** `_build_ticket_depends_on`
   classifies each candidate id, and an id with no co-located ticket is *dangling* and
   is dropped. The drop is not literally silent — it emits a WARNING naming the dropped
   id. The defect is the **verdict**, not the volume: dropping a record's only declared
   dependency is a change to what the ticket means, and the run still reports READY. A
   warning on the path to a green verdict is read by every automated caller, and most
   humans, as "generated fine."

**This gap was widened by a fix, not by neglect.** Before `KI-ACD-20260921-1615`,
`_build_ticket_depends_on` read `depends_on` only, and `expects_from` was inert for
ordering. That entry's fix made the candidate set the **union** of `depends_on` and
`_expects_from_ac_ids(...)` — correctly, since `expects_from` names a real producer.
But only the generator was taught this. The cycle gate still treats `expects_from` as
documentation. So the two tools now disagree about whether `expects_from` is an ordering
edge, and a cross-field cycle is precisely the shape that disagreement makes unreachable:
the tool that believes the edge exists has no power to refuse, and the tool that can
refuse does not believe the edge exists.

**Why it is a pattern and not an incident.** Second occurrence in a single AC tree
within two days — `TQ-600a-1-i`/`-1-ii` was the first. Both were found by a human
reading the two records side by side, which is the detection method
`KI-ACD-015` already described as the only one available ("found by diffing
`expects_from.ac_id` against `depends_on` across the tree by hand").

**What it costs.** The failure is not a crash or a blocked commit — it is a buildable
ticket that cannot be built correctly. An agent handed such a ticket has three bad
options: implement against the forbidden approach, stall, or invent a dependency that
was never declared. All three consume a full drive before anyone looks at the store.

**Workaround.** Read both fields for every pair before generating. Where a cycle exists,
one edge is spurious — decide which and delete it in the store, do not let the generator
choose. Fixed here in `92923a26` by dropping `TQ-600a-5`'s `depends_on` edge, `-5` being
the record whose dependency was incidental rather than contractual.

**Remediation.**

1. Give `check_ac_circular_deps.py` the same union of edge sources the generator already
   uses. One shared helper imported by both, not a second copy of
   `_expects_from_ac_ids` — the divergence above is what one-field-per-tool produced.
2. Make `_build_ticket_depends_on` refuse rather than warn when the dropped candidate
   was the record's **only** dependency edge. A partial drop can stay a warning; losing
   the last edge changes the ticket's meaning and should not reach READY.

**Related.** `KI-ACD-015` (epic ordering reads `depends_on` only — the same
two-fields-one-fact split, seen from the sequencer). `KI-ACD-20260921-1615` (the
generator fix that created this asymmetry; now half-landed across the toolchain).
`KI-ACD-021` (the separate, tracked case of parent edges being dropped from generated
tickets). `KI-ACS-013` is **not** the same defect: it concerns `delivers_to` and
`expects_from` being keyed on different things, so the forward half of that edge is not
traversable. Here both fields are correctly AC-keyed and individually readable; the
defect is that no tool reads them together.

**Pattern:** two tools that disagree about whether a field is load-bearing, where the
one that believes it cannot refuse and the one that can refuse does not believe it.

---
