---
title: "KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle"
description: "KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle"
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

# KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open (data corrected by hand 2026-08-25 and again 2026-08-31; generator unchanged)
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **2026-08-31 recurrence:** `EPIC-SuppressionNarrowsNeverDisables`, eight references across
  seven tickets, every one dangling, plus the same names in `Master_Plan.md`'s dependency
  column. Caught by `check-doc-frontmatter` and repaired by hand. Same generator, same shape,
  third time — and this is the defect that would leave a driven epic with no build order at
  all if the guard ever stopped catching it.
- **Where:** `scripts/goal_to_epic.py` (`_translate_ticket_depends_on`, the epic-folder move,
  `_render_master_plan`) against `templates/hooks/ticket_frontmatter_guard.py`

**Symptom.** `goal_to_epic.py` writes tickets loose into `tickets/00_inbox/`, then moves
them into the epic folder under an ordinal prefix — `TICKET-20260825-GE-120b-2.md` becomes
`09_TICKET-20260825-GE-120b-2.md`. `depends_on` is translated **before** the move and never
re-pointed after it, so every reference names a file that no longer exists:

```text
❌ FRONTMATTER VIOLATION: '.../15_TICKET-20260825-GE-120b-4.md'
   depends_on 'TICKET-20260825-GE-120c-1.md' not found. Looked in:
     .../EPIC-TrustThatAGreenCheckActuallyChecked/TICKET-20260825-GE-120c-1.md
     .../EPIC-TrustThatAGreenCheckActuallyChecked/done/TICKET-20260825-GE-120c-1.md
```

**27 references across 20 of the 37 tickets — every inter-ticket edge in the epic.** The
Master_Plan's "Depends On" column carries the same stale names.

**The topological order is not affected, which is what makes this easy to miss.** The
ordinal prefixes encode the correct sequence: `c-1` really is at 12, ahead of `b-1` at 13
and `b-4` at 15. So the epic *looks* correctly wired in the Master_Plan table and reads
correctly to a human. What is broken is the machine-readable edge — the field
`ticket-prioritizer` and the supervisors use to compute a ready set. Left uncorrected, a
dependency-aware drive would treat all 37 tickets as unblocked.

**Contrast with KI-ACD-014, because together they localise the bug.** In the same run the
generator **did** correctly re-point `implemented_by` in the AC store to the post-move
`NN_`-prefixed path. So `goal_to_epic.py` knows the final filenames — it simply applies
that knowledge to the AC-store back-reference and not to the ticket-to-ticket references or
the Master_Plan table. This is one missing re-point pass over two surfaces, not a
path-tracking failure.

**It is caught, at least.** `ticket_frontmatter_guard` rejects the whole set at commit
time, which is why this is recorded as loud rather than silent. But it means
`goal_to_epic.py`'s output is uncommittable out of the box — the second such defect after
KI-ACD-012, whose Master_Plan frontmatter gap was confirmed again in this same run.

**Fix direction.** Move the tickets first, then translate `depends_on` and render the
Master_Plan against the final filenames — or re-point both surfaces after the move, reusing
whatever already re-points `implemented_by`. The regression test should generate a
two-ticket epic with one edge between them and run the real `ticket_frontmatter_guard`
over the result, for the same reason KI-ACD-012 gives: asserting a filename format is a
second copy of the rule that can itself fall behind.

**Second occurrence, 2026-08-25.** Reproduced by `goal_to_epic.py --ac GE-122d`: seven
dangling references across four of the nine tickets, plus the Master_Plan table. Repaired
by hand.

This occurrence sharpens the "easy to miss" claim above into something stronger. The
`GE-122d` epic exists specifically to make a scaffold ticket precede a registration ticket
— registering the commit-time check before the namespace roots exist would block every
commit in a fresh install. That ordering is carried **only** by `depends_on`. So the
generator's stale references do not merely degrade the build order here; they erase the
one constraint the epic was assembled to enforce, while the Master_Plan table still reads
correctly to a human reviewer. `ticket_frontmatter_guard` caught it, as before — but note
that it catches it only because it resolves each reference against disk. A check that
asserted `depends_on` was *present and non-empty* would have passed all four tickets.

**Pattern:** a producer that renames its artifacts after writing the references to them.

---
