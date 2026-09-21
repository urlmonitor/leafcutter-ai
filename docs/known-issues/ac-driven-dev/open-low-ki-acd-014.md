---
title: "KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`"
description: "KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`"
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

# KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open (data corrected by hand 2026-08-25 and again 2026-08-31; generator unchanged)
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **2026-08-31 recurrence, with a store-wide count:** all 27 leaf ACs of
  `EPIC-SuppressionNarrowsNeverDisables` were stamped with
  `- /home/henzeh/projects/leafcutter/worktrees/safety-security/tickets/…` and corrected to
  repo-relative before the commit. A sweep of the whole store the same day found **60** records
  carrying an absolute `/home/henzeh` path — `grep -rl "^- /home/" docs/acceptance-criteria/` —
  so 33 predate this run and are still in the store on `main`. That is the number worth acting
  on: the generator keeps producing them, nothing rejects them, and each one is a path that
  resolves on exactly one machine.
- **Where:** `scripts/goal_to_epic.py` — the `implemented_by` back-reference write

**Symptom.** After generating the GE-120 epic, all 37 AC records carried a
machine-specific absolute path:

```yaml
implemented_by:
- /home/henzeh/projects/leafcutter/leafcutter-ai/tickets/00_inbox/epics/EPIC-.../15_TICKET-20260825-GE-120b-4.md
```

Every other path field in the store is repo-relative (`docs/…`, `tickets/…`,
`templates/…`). An absolute path baked into a tracked YAML file resolves only on the
machine that generated it, so the AC→ticket link is dead in CI, in any other clone, and in
any consumer install.

**Note what the tool got right, because it narrows the bug.** The tickets are first written
loose into `tickets/00_inbox/`, then moved into the numbered epic folder. The generator
correctly **re-pointed** every back-reference to the post-move location — the link targets
are accurate. Only their form is wrong. So the defect is a missing
`relative_to(project_root)` at the write, not a path-tracking error.

**Fix applied to the data.** All 37 rewritten to repo-relative; verified that each one
resolves to a file that exists.

**Second occurrence, 2026-08-25.** Reproduced by `goal_to_epic.py --ac GE-122d` on all
nine ACs of `EPIC-TheNumberingGuaranteeHoldsAtEveryStage`, rewritten to repo-relative by
hand again. This run was made **from a worktree**, so the embedded prefix was
`/home/henzeh/projects/leafcutter/worktrees/ge122-acs/…` — a path that does not exist even
on the machine that generated it once the worktree is removed. Worth stating because the
first occurrence's absolute path at least pointed at the main checkout and so looked
merely redundant; from a worktree the same defect writes a link that is dead everywhere,
including locally.

**Fix direction for the tool.** Make the back-reference relative to the project root at
the point of write, and assert repo-relativity in the same test that covers KI-ACD-013 —
both are "the generator writes store data the store's own conventions reject."

---
