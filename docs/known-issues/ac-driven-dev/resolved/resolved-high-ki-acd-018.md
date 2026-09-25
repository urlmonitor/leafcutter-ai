---
title: "KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle"
description: "KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (88c6b58e, PR #765, TKT-017; carried through the module split
  in fb07b48d, PR #844; verified 2026-09-25 by generating a real three-ticket chained epic
  on both `--ac` and `--ids` routes and running the real `ticket_frontmatter_guard` over it).
  See "Resolution" below. Before the fix, the data was corrected by hand on 2026-08-25 and
  again on 2026-08-31.
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

## Resolution (verified 2026-09-25)

**Fix.** Commit `88c6b58e` (PR #765, TKT-017, 2026-09-14) found the cause. The translation
helper `_translate_ticket_depends_on()` already existed, but only `build_epic_from_ids()`
(the `--ids` route) called it. `run()` (the default `--ac` route) did not. The commit added
the missing call to `run()`. Commit `fb07b48d` (PR #844, 2026-09-21) split `goal_to_epic.py`
into modules and kept the fix. In `scripts/ac_store/epic_pipeline.py`, `run()` now calls
`_wire_epic_depends_on(epic_folder, topo_order, dep_graph, _epic_filename_map(...))` after
assembly. `_epic_filename_map` (`scripts/ac_store/epic_phases.py`) builds the post-move
`NN_` names using the same prefix rule as assembly. The Master_Plan comes out right as a
side effect. `generate_master_plan` runs after the wiring step and reads each ticket's
`depends_on` from the ticket frontmatter, so its "Depends On" column picks up the translated
names.

**Evidence, from running the code rather than reading it:**

- `python -m pytest unit_tests/ac_store/test_tkt_017_epic_depends_on_resolves.py -q` gave
  3 passed. These tests cover both routes. Each one asserts that every dependency is a file
  that exists and that at least one dependency was checked.
- A scratch probe seeded a goal with a three-leaf chain (`a <- b <- c`). It ran
  `scripts/goal_to_epic.py` on `--ac` and on `--ids`, then passed every generated ticket
  through the real `ticket_frontmatter_guard.validate()`. Both routes exited 0. Both
  produced `01_`/`02_`/`03_` tickets, left no loose inbox tickets, and had 3 edges with
  0 guard `depends_on` errors. For example, `03_...-900c.md` had
  `depends_on=['01_...-900a.md', '02_...-900b.md']`. The Master_Plan "Depends On" column
  listed the same `NN_` filenames.
- The guard does reject the stale form. `_check_depends_on` returns
  `'depends_on' references missing file: 'TICKET-A.md'` when only `01_TICKET-A.md` exists,
  and returns no error for `01_TICKET-A.md`. So the clean result above is not vacuous.

The Fix direction asked for a regression test that runs the real guard over the output.
The committed test does not do that. It asserts that each referenced file exists, which is
the same fact the guard checks. The probe above did run the real guard.

---
