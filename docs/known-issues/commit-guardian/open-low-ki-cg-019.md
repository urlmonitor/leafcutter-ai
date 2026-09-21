---
title: "KI-CG-019 — the `templates/` copy of `check_ac_parent_covered_by` fail-opens on an import it can never satisfy, so verifying from `templates/` always passes"
description: "KI-CG-019 — the `templates/` copy of `check_ac_parent_covered_by` fail-opens on an import it can never satisfy, so verifying from `templates/` always passes"
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

# KI-CG-019 — the `templates/` copy of `check_ac_parent_covered_by` fail-opens on an import it can never satisfy, so verifying from `templates/` always passes

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py` — the
  `derive_parent_id` import guard

**Symptom.** Run from `templates/`, the hook prints a warning and exits 0 without checking
anything:

```
$ HOOK_ROOT=<worktree> HOOK_TEST_FILES=<a real AC record> \
    python <worktree>/templates/scripts/commit_guardian/check_ac_parent_covered_by.py
[check-ac-parent-covered-by] WARNING: cannot import derive_parent_id: ac_parent_id.py not
found via package import, script-relative, or project-root walk.; skipping check (fail-open)
exit: 0
```

The deployed copy under `.leafcutter/scripts/commit_guardian/` imports cleanly and runs.

**Root cause.** `ac_parent_id.py` lives in `scripts/ac_store/` and is placed next to the
hook only by `build.py`. In `templates/` that sibling does not exist, and none of the three
resolution strategies can find it — so the condition is not an environment accident but a
permanent property of that copy. The failure is guaranteed, and the response to a guaranteed
failure is to pass.

**Why it matters.** It is louder than `KI-CG-018` — it does print a warning — but it lands in
the same trap: anyone verifying AC parent back-links by running the hook out of `templates/`
gets exit 0 and a clean-looking result. That is a natural thing to do, because `templates/`
is where the source of truth for the hook lives and where an author editing it is already
working. The hook that exists to catch a stale `covered_by` is the one that silently
abstains.

Found while verifying `ACD-2100e`: a business-analyst hit the fail-open, noticed the warning,
re-ran the deployed copy, and additionally corroborated the invariant by reading the parent's
`covered_by` directly rather than trusting either exit code.

**Fix direction.** Fail **closed** when the import cannot be satisfied and the hook was given
files to check — the check exists to be blocking, and a blocking check that cannot load its
own dependency has not passed. If the `templates/` copy is genuinely not meant to be
executable in place, make it say that explicitly ("this copy is a build source; run the
deployed hook") and exit non-zero, rather than emitting a warning shaped like a skip.

Related: the deployed hook has no `parsed_files`-style diagnostic at all, so even a correct
run cannot state what it inspected. Adding one alongside the `KI-CG-018` fix would make both
hooks answerable to the same question.

---
