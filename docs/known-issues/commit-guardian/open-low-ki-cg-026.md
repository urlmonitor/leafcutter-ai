---
title: "KI-CG-026 — The unattributed-collision count is computed and then discarded by `pre-commit`"
description: "KI-CG-026 — The unattributed-collision count is computed and then discarded by `pre-commit`"
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

# KI-CG-026 — The unattributed-collision count is computed and then discarded by `pre-commit`

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — **the producing code is NOT on `main`** (it is PR #495's
  `check_identifier_uniqueness.py`), but the **consuming** half of the defect is: no hook in
  `commit_guardian.json` sets `verbose`, so this will reproduce exactly as described the
  moment the gate is registered
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (consuming half re-verified against
  `37655862`)
- **Where:** PR #495's `check_identifier_uniqueness.py` operator message;
  `templates/scripts/commit_guardian/commit_guardian.json` (the generated `pre-commit` config)

**Symptom.** GE-122a-1-i requires a visible count of reported-but-unattributed collisions, on
the stated grounds that *"a visible count is what makes the backlog shrink."* Run directly,
the gate emits it:

```
[check_identifier_uniqueness] 1 reported-but-unattributed contested number(s)
  with no claimant in the current change set (not blocking)
```

Under `pre-commit`, a **passing** hook's stdout is discarded. So on the non-blocking path —
the only path this message exists for — the operator never sees it.

**Evidence.** `grep -c verbose templates/scripts/commit_guardian/commit_guardian.json`
returns **0**. The generated config sets `verbose: true` on no hook at all, so this is not a
per-hook oversight but a property of every advisory message the hook family emits on its
passing path.

**Fix direction.** Set `verbose: true` on this hook's registration when `KI-CG-021` is
addressed. Worth a wider look while there: any other hook whose value is an advisory printed
on the passing path has the same problem today.

**Pattern:** same shape as `KI-CG-007`, one layer further out — computed correctly, then not
consumed.

---
