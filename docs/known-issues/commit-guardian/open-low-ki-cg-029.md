---
title: "KI-CG-029 — `repair_work_item_duplicates.py` has no CLI, so a destructive repair can only be invoked from a test"
description: "KI-CG-029 — `repair_work_item_duplicates.py` has no CLI, so a destructive repair can only be invoked from a test"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-029 — `repair_work_item_duplicates.py` has no CLI, so a destructive repair can only be invoked from a test

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `templates/scripts/commit_guardian/repair_work_item_duplicates.py`

**Symptom.** The module is importable only. The live repair run against the real `tickets/`
tree therefore went through a throwaway operator harness in `/tmp` rather than a supported
entry point.

**Why it was left.** Nothing in the AC's `test_spec` required a CLI, and adding untested
surface for convenience was declined — the right call under the rules in force. Recorded
because the consequence outlives the decision: a repair that can only be invoked from a test
is awkward to re-run and hard to audit, and the `/tmp` harness that actually mutated the
tickets tree is not in version control.

**Fix direction.** If the branch lands, give it a CLI *with* a test, or record explicitly that
the repair is one-shot and closed.

---
