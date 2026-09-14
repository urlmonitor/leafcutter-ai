---
title: "An epic plan names the goal it came from, and the BO-400e epic is assembled"
date: "2026-09-14"
time: "07:00"
type: manual
components:
  - ac_driven_dev
  - build_orchestration
summary: "The plan a generated epic ships with was crediting the wrong acceptance criterion — a loop variable added last week shared its name with the parameter holding the goal the caller asked for, so by the time the plan was written that name held whichever leaf happened to sort last, and every epic published since claimed to have been derived from one of its own children. Renaming the loop variable fixes it; the BO-400e epic is then generated against the corrected pipeline and lands with its five tickets, serving as the first real-artifact proof that this week's two earlier back-port fixes both hold."
description: "goal_to_epic.py run(): the TKT-017 depends_on translation loop was written as `for ac_id in topo_order`, shadowing run()'s own ac_id parameter. Statement-level loop targets outlive their loop in Python, so the Master_Plan block ~100 lines later read the last leaf id instead of the goal, writing source_ac: BO-400e-5 and a Goal paragraph claiming derivation from leaves beneath a childless record. Renamed to leaf_ac_id with an explanatory comment; the adjacent dict comprehension binding the same name is safe (comprehension scoping) and that asymmetry is what hid the bug. Covered by test_ac_route_master_plan_credits_the_goal_not_the_last_leaf, proven red ('ZZDEP-900' != 'ZZDEP-900c') then green. Also generates EPIC-WorkIsOnlyEverMarkedFinishedThroughThe (5 tickets, BO-400e-1..5) and files KI-ACD-20260914-0657 for a third defect in the same family: generate_master_plan() emits five frontmatter fields where the ticket gates guarding tickets/ demand fifteen, so every generated plan needs a hand patch before it can be committed."
commits:
  - b4751c94c
  - 1f3a2ac5b
breaking: false
---

## Entry

### A name reused a hundred lines apart

`TKT-017` shipped on 2026-09-13 to fix generated epics whose tickets declared
dependencies on files that did not exist. The fix was correct. The loop that carried
it was written as:

```python
for ac_id in topo_order:
```

`ac_id` is `run()`'s own parameter — it holds the goal AC the caller named on `--ac`.
Python's statement-level loop targets outlive their loop, so from that point on the
name held whichever leaf sorted last in topological order. About a hundred lines
further down, the `Master_Plan.md` block reads `ac_id` to record where the epic came
from.

Every epic generated through the `--ac` route since then published a plan that
credited a leaf instead of the goal: `source_ac` named a child, and the Goal paragraph
announced that the tickets were "generated from the leaf ACs beneath" a record that
has no leaves beneath it at all. The BO-400e epic named `BO-400e-5` — its own last
ticket — as the thing it was built from.

The dict comprehension immediately above the loop binds the same name and is entirely
harmless, because comprehension targets are scoped to the comprehension. That
asymmetry is the reason this survived review: the two constructs sit adjacent, look
alike, and behave differently.

### Why the existing tests did not see it

`TKT-017`'s suite walks every ticket in the generated epic and asserts each declared
dependency resolves to a file that exists. It passes on the clobbering version,
because the damage does not land in a ticket — it lands in `Master_Plan.md`, which
that suite's loop explicitly skips.

The new case asserts on the plan directly: `source_ac` must equal the goal id, and the
Goal paragraph must not attribute the epic to any leaf. Proven red against the shipped
code with the failure naming the mechanism exactly — `'ZZDEP-900' != 'ZZDEP-900c'`,
the goal versus the last leaf — and green after the rename. The two pre-existing tests
pass either way, which is what establishes that the new one is carrying the coverage
rather than duplicating it.

### The epic, and what generating it proved

`EPIC-WorkIsOnlyEverMarkedFinishedThroughThe` is now assembled from `BO-400e`'s five
approved children, in dependency order: derive the demanded step set from the ticket's
own record; refuse read-only while any step is unaccounted for; make the checking
mechanism the only writer of the finished state; give identical tickets in one run the
same strict answer; and draw the close path so the number of doors is readable at a
glance. It closes the split-outcome defect recorded as `KI-BO-20260831-1932`.

Generating it was also the point of the exercise, because it is the first real artifact
produced since two back-port fixes landed, and both were verified against it rather
than against fixtures:

- **`TKT-016`** — all five `implemented_by` back-references are worktree-relative. No
  absolute path appears anywhere in the epic folder or the AC records.
- **`TKT-017`** — every `depends_on` entry names a prefixed filename that exists in the
  epic folder: 02 on 01, 03 on 01-02, 04 on 01-03, 05 on 01-04.

Both fixes hold. Neither defect reproduced.

### A third one, filed rather than fixed

Committing the epic surfaced the next instance of the same family, now recorded as
`KI-ACD-20260914-0657`. `generate_master_plan()` writes five frontmatter fields;
`Master_Plan.md` lives under `tickets/`, and both gates guarding that tree validate
everything there against the ticket schema. Neither knows an epic plan is not a
ticket, so between them they demand ten more fields — `title`, `depends_on`,
`requires_diagram`, `requires_adr`, `change_target`, `risk_surface` and the rest. No
generated epic can be committed without a human filling them in.

The plan in this commit is hand-completed for that reason, and the commit message says
so. The fix belongs in the generator — or, arguably, in exempting an index file from a
schema written for units of work — and that decision is recorded in the register
rather than taken here, so the epic drive is not held behind a fourth fix cycle.

Worth noting why nobody had hit this: the store's older plans carry the same five-field
generated shape and simply predate the gates; the newer conforming ones were
hand-authored. The store looks like it contains valid plans, and it does — none of them
came out of the generator that way.

### Verification

- `test_tkt_017_epic_depends_on_resolves.py` — 3 passed, including the new case proven
  red first
- `test_tkt_016_epic_backref_is_relative.py` — 1 passed
- `ruff check` on both changed files — clean
- AC store — `OK: all 37 AC YAML files are valid.` for the BO-400 folder
- Real artifact — zero absolute paths across the epic folder and AC records; every
  `depends_on` entry resolved against the folder contents

`check-build-drift` and `check-output-drift` were skipped on both commits. Both resolve
their project root from `__file__` through this worktree's `.leafcutter` symlink and so
audit the workspace parent rather than the worktree — every path they report is prefixed
`leafcutter-ai/`, a directory this worktree does not contain. The drift is pre-existing
state in a separate clone, was reproduced with everything else stashed, and neither
changed file is a build source. Every other hook ran and passed.
