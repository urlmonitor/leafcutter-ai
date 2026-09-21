---
title: "KI-ACD-20260914-0657 — Every `Master_Plan.md` the generator writes is rejected by the ticket frontmatter gates, so no generated epic can be committed without a hand patch"
description: "high — it blocks the commit of every epic the generator produces"
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

# KI-ACD-20260914-0657 — Every `Master_Plan.md` the generator writes is rejected by the ticket frontmatter gates, so no generated epic can be committed without a hand patch

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — it blocks the commit of every epic the generator produces
- **Status:** open
- **Occurrences:** 1 confirmed by execution (2026-09-14, BO-400e); by inspection of
  `generate_master_plan()` the defect is unconditional and affects both the `--ac` and
  `--ids` routes
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/goal_to_epic.py` — `generate_master_plan()`, the frontmatter block
  (`f"source_ac: {goal_ac_id}\n"` and the lines around it)

**Symptom.** `goal_to_epic.py` emits a `Master_Plan.md` carrying exactly five frontmatter
fields: `epic_name`, `created`, `status`, `components`, `source_ac`. The file is written under
`tickets/`, and both gates that guard that tree validate everything there against the ticket
schema. Neither knows an epic plan is not a ticket, so both refuse it:

- `check-doc-frontmatter` (pre-commit): `Missing required field: 'title'`,
  `Missing required field: 'depends_on'`.
- `ticket_frontmatter_guard` (PostToolUse hook, fires on any edit): `'requires_diagram':
  field missing`, `'requires_adr': field missing`, `Missing required field:
  'change_target'`, `Missing required field: 'risk_surface'`.

Ten fields short in total. The commit cannot proceed until a human adds all ten by hand.

**Evidence.** Generating the BO-400e epic on 2026-09-14 and staging it produced the
`check-doc-frontmatter` failure above; adding `title` and `depends_on` to satisfy it then
produced the `ticket_frontmatter_guard` failure, which took two further edits to clear. The
epic landed in `1f3a2ac5b` only with a hand-completed plan.

**Why it has not been noticed before.** Master plans already in the store come in two shapes.
The older ones (`EPIC-DispatchPreflightGate`, 2026-07-08) have the same five-field generated
shape and sit in the tree untouched — they were committed before the gates required these
fields, and nothing re-validates a file that is not being staged. The newer ones
(`EPIC-TruthfulProjectRecord`, 2026-09-09) carry the full ticket-shaped set — they were
hand-authored or hand-repaired, not generated. So the store looks like it contains conforming
plans, and it does; none of them came out of the generator that way.

**Detection.**

```bash
# Any generated plan: count its frontmatter fields. Five means unpatched.
python scripts/goal_to_epic.py --ac <L1-ID> --store-root docs/acceptance-criteria \
  --inbox-dir tickets/00_inbox --approved-only
grep -c ":" tickets/00_inbox/epics/EPIC-*/Master_Plan.md   # generated == 5-ish, conforming == 15
```

**Fix direction.** Emit the full set from `generate_master_plan()` rather than patching each
artifact. The conforming shape is `EPIC-TruthfulProjectRecord`'s: `title`, `type: epic`,
`status`, `components`, `created`, `depends_on: []`, `priority`, `roadmap_phase`,
`advances_current_outcome`, `requires_diagram`, `requires_adr`, plus `change_target` and
`risk_surface`. Most of these are derivable from the records the generator has already
loaded — `title` from the goal AC's title, `priority` and `roadmap_phase` from the goal AC,
`change_target` and `risk_surface` as the union over the leaf children, `depends_on: []`
because a plan depends on nothing. Only `requires_diagram` / `requires_adr` need a judgement,
and `documentation_triggers` on the goal AC already answers the first.

Worth deciding at the same time, because it is the actual root cause: whether
`Master_Plan.md` should be subject to the ticket schema at all. It is an index, not a unit of
work, and `change_target` / `risk_surface` on an index are close to meaningless — the
alternative fix is to exempt `Master_Plan.md` in both gates and leave the generator's output
as it is. Either is defensible; what is not is the present state, where the generator writes
one shape and the gates demand another.

**Pattern:** the third defect found in `run()`'s epic-assembly path in a week, after `TKT-016`
(absolute `implemented_by` back-references) and `TKT-017` (unresolvable `depends_on`). All
three share a shape — the generator produces an artifact that no gate sees until a human
tries to commit it, so the generator's own tests pass and the defect surfaces one commit
attempt at a time. A test that generates an epic and runs the real frontmatter validators
over the result would have caught all three at once. **Related:** `TKT-016`, `TKT-017`,
`KI-ACD-20260831-agent-contracts-block-not-pipe-delimited` (same family: generated ticket
content that a downstream gate fail-closes on).
