---
title: "KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY"
description: "KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY"
type: reference
category: reference
status: active
created: '2026-09-29'
last_updated: '2026-10-12'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-20260929 — a dependency cycle spanning `depends_on` and `expects_from` is invisible to the cycle gate, and the generator resolves it by dropping an edge and reporting READY

- **Severity:** high
- **Status:** open
- **Occurrences:** 3 (`TQ-600a-1-i`/`-1-ii` and `TQ-600a-2`/`-5`, both in the TQ-600 tree; then
  `ACD-2500c-3`/`-c-1` on 2026-10-12, see Occurrence 3)
- **First seen:** 2026-09-28 · **Last seen:** 2026-10-12
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

**Occurrence 3 — 2026-10-12, `ACD-2500c-3` / `ACD-2500c-1`, refused this time by the epic
sequencer.** `ACD-2500c-3` declared `depends_on: ACD-2500c-1`, while `ACD-2500c-1`'s
`expects_from` names `ACD-2500c-3` as the producer of the entry shape it consumes. Both records
had been committed to `main`. The commit hook let them through because it reads `depends_on`
only. Re-verified on origin/main `a104d934`: `check_ac_circular_deps.py` contains zero
occurrences of `expects_from`, and its only change since this entry was filed is the loader swap
in `f91b1cae`. This time the refusal came from `goal_to_epic.py --ids` on the 48-id ACD-2500 build
set, which exited 1 with:

```text
ERROR: Circular dependency detected: ACD-2500c-3 -> ACD-2500c-1 -> ACD-2500c-3
  ACD-2500c-3 -> ACD-2500c-1 (depends_on, parent-link: false)
  ACD-2500c-1 -> ACD-2500c-3 (expects_from, parent-link: false)
```

This was reproduced with `--dry-run` against a scratch snapshot of the store as it stood before
the fix (`a4ba3d37`). It was fixed in `e21501e3` by deleting `c-3`'s `depends_on` edge, which
pointed the wrong way.

**What has changed since this entry was filed: there are three readers now, not two.** Commit
`49d6139f` (2026-10-07, BO-2600a-5 AC-7/AC-8) moved the epic sequencer
(`scripts/ac_store/epic_dependencies.py` `_scan_edges`, `:86-116`) onto
`depends_on ∪ expects_from`, read through the shared `_gtfa_store._prerequisite_ac_ids`. It made
one exception: a child's `depends_on` on its own structural parent is dropped when the parent's
`expects_from` names that child (`:112`). The sequencer refuses on a cycle and names every edge
with its field and a parent-link flag (`_cycle_message`, `:369`). So the cycle hook reads one
field and cannot refuse a cross-field cycle. The generator reads two fields and drops edges. The
sequencer reads two fields, accepts the parent-to-own-child contract, and refuses on a real
cycle.

**That exception matters for Remediation 1.** IT-PO enrichment routinely writes an L2
`expects_from` that names its own L3 child, while the child's `depends_on` lists the parent.
ACD-2500 had four such pairs: `b-1`/`b-1-i`, `d-3`/`d-3-i`, `d-5`/`d-5-i`, and `d-1`, whose
`expects_from` named `d-3-i`. The sequencer orders all of them. On the same snapshot, with only
the `c-3` edge removed, `resolve_leaf_dependencies()` plus `topological_sort()` ordered all 48 ids
with no cycle. A hook given "the same union of edge sources" without the parent-yield rule would
refuse all four. The helper the hook shares should therefore be the sequencer's edge function,
yield rule included, not `_prerequisite_ac_ids` on its own.

**A cost of the gap, observed.** The untangle commit `e21501e3` also set `expects_from: null` on
those four L2s. Its message describes them as cycle-closing. No tool on this branch treats them as
a cycle: the sequencer accepts them as shown above, and the hook,
`scan_ac_store._drain_cycles` and `ticket_prioritizer.py` contain no reference to `expects_from`.
So the change deleted each consumer's statement of the contract it reads. The producer's
`delivers_to` still carries it. Whether to restore those four is a store decision. It is recorded
here because the refusal has two properties that invite over-correction. It reports only the
first cycle it finds (`_extract_cycle`, `:250`, returns one path per run). And it says nothing
about which edge is spurious, beyond flagging the field and whether the edge is a parent link.

---
