---
title: "KI-ACD-021 — Every `depends_on` edge pointing at an AC's own parent is dropped from the generated ticket, while the Master_Plan still draws it"
description: "KI-ACD-021 — Every `depends_on` edge pointing at an AC's own parent is dropped from the generated ticket, while the Master_Plan still draws it"
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

# KI-ACD-021 — Every `depends_on` edge pointing at an AC's own parent is dropped from the generated ticket, while the Master_Plan still draws it

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open (data corrected by hand 2026-08-25; generator unchanged)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` — the ticket-frontmatter `depends_on` write, against
  the same file's `_render_master_plan()` dependency block

**Symptom.** In the epic generated from `GE-122d`, three tickets were written with
`depends_on: []` in their frontmatter while the Master_Plan's own Dependencies block, in the
same run, correctly recorded an edge for each:

| Ticket | Master_Plan says | Frontmatter says |
|---|---|---|
| `GE-122d-3-i` | `-> GE-122d-3` | `[]` |
| `GE-122d-3-ii` | `-> GE-122d-3` | `[]` |
| `GE-122d-6-i` | `-> GE-122d-6` | `[]` |

Each edge is present in the source AC YAML — `GE-122d-3-i.yaml:39-40` reads
`depends_on: [GE-122d-3]`. So the generator read the edge, rendered it in one output, and
omitted it from the other.

**The rule, which is what makes this predictable rather than random.** Every dropped edge
points at the AC's **own parent by id shape**; every retained edge points at a sibling or
cousin. `GE-122d-2 -> GE-122d-1`, `GE-122d-4 -> GE-122d-1, GE-122d-2`,
`GE-122d-5 -> GE-122d-2, GE-122d-3` and `GE-122d-6 -> GE-122d-1, GE-122d-3-ii` were all
written correctly. `GE-122d-6 -> GE-122d-3-ii` is the one that settles it: a Roman-suffixed
AC is fine as a dependency *target*. It is being the **source** of an edge to its own parent
that loses it. The generator appears to treat a parent reference as the `covered_by` tree
relation and filter it out, which is defensible for a tree link and wrong for `depends_on` —
the author wrote it in the build-order field, and for the Roman-suffix
technical-constraint pattern the base AC genuinely is a build predecessor.

**Consequence.** `build-feature` reads frontmatter `depends_on`, not the Master_Plan prose.
Three tickets were therefore machine-readable as unblocked and could be dispatched before the
base AC they constrain. In this epic that is not cosmetic: `GE-122d-3-ii` scaffolds the
namespace roots that `GE-122d-6` registers a commit-time check against, and registering
before scaffolding makes every commit in every fresh install fail closed on an unresolvable
root.

**Distinct from `KI-ACD-018`, and the pair is worth reading together.** That entry is about
edges that are *written but stale* — the pre-move filename. This one is about edges that are
*not written at all*. They have opposite detection properties, which is the useful part:
a stale edge is caught by `check_doc_frontmatter`, because a name that resolves to nothing is
an error. A **missing** edge resolves vacuously — `depends_on: []` is valid frontmatter — so
no gate fires, and the Master_Plan table reads correctly to a human reviewer either way.
Between the two, `goal_to_epic.py` produced an epic in which four of the eight declared edges
were wrong and only the loud half was caught.

**Fix direction.** Write `depends_on` from the same resolved edge set the Master_Plan
dependency block is rendered from — the divergence exists because two renderings compute the
edge list separately, and one of them applies a parent filter. If parent references really
should be excluded from build order, exclude them from *both* outputs and say so; a
generator that draws an edge it does not wire is worse than one that does neither.

The regression test must assert **frontmatter against the Master_Plan** for the same run,
not either against an expected literal. A test that checks only that "some `depends_on` was
written" passes here, since five of the eight edges were correct.

**Pattern:** one fact rendered twice by two code paths, agreeing in the surface a human reads
and disagreeing in the surface a machine reads.

---
