---
title: "KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`"
description: "KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`"
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

# KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open, **partially fixed** (verified 2026-09-25). **Fixed: the generator.**
  TKT-016 (`4711c9c7`, #759, 2026-09-08) relativises both halves of the back-reference pair.
  The code now lives in `scripts/ac_store/epic_phases.py::_relativise_backref_pair` /
  `_apply_epic_backrefs`, after the #844 split (`fb07b48d`), and it warns when a path cannot be
  relativised. **Remaining: legacy data and a guard.** 10 store records on `main` still carry
  `/home/henzeh/...` `implemented_by` entries. There are 8 under
  `build-orchestration/BO-1900-dispatch-preflight/` (`BO-1900b-1`, `-b-1-i`, `-b-1-ii`, `-b-2`,
  `BO-1900c-1`, `-c-1-i`, `-c-1-ii`, `-c-2`) and 2 under
  `build_pipeline/BP-1400-web-app-ci-gate/` (`BP-1400c-1`, `BP-1400c-1-i`). All 10 predate the
  fix: they were written by the scaffold commits `12b01120` (#261, 2026-07-10) and `69c63293`
  (#371, 2026-07-21). Nothing in the store rejects an absolute entry either.
  `check_ac_governance.py` has no such check. `_gtfa_implemented_by.py` only normalises a
  legacy absolute entry when that AC is regenerated. No other KI tracks this leftover.
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

**2026-09-25 — verification note.** The generator half of this entry is fixed, and the
"generator unchanged" status was stale. The fix direction above was implemented by TKT-016
(`4711c9c7`, #759), including the regression test
`unit_tests/ac_store/test_tkt_016_epic_backref_is_relative.py`. The `--ac` entry path is
tracked separately as `KI-BO-014`. This run of
`python -m pytest unit_tests/ac_store/test_tkt_016_epic_backref_is_relative.py
unit_tests/ac_store/test_acd_1200a_12.py unit_tests/ac_store/test_acd_1200a_13.py -q` gave
**6 passed**. The store sweep `grep -rl "^- /home/" docs/acceptance-criteria/` now finds
**10** files, down from 60. All 10 predate the fix, and they are listed in the Status line.
This entry stays open for two things:

- rewrite those 10 records to repo-relative;
- add a store-level check that rejects an absolute `implemented_by` entry. Without it, a
  hand edit or another generator could reintroduce one unnoticed.

---
