---
title: "KI-CG-20260929-output-drift-scans-gitignored-cache — `check-output-drift` reports a GAP on a gitignored runtime cache, and its own stated remedy can never clear it"
description: "high — blocks the next commit after any README edit, with a remedy line that does not work."
type: reference
category: reference
status: active
created: '2026-09-29'
last_updated: '2026-09-29'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260929-output-drift-scans-gitignored-cache — `check-output-drift` reports a GAP on a gitignored runtime cache, and its own stated remedy can never clear it

> One known issue, filed on sight during the GE-127f-2 build (ticket 07 of
> EPIC-FilesStayWorkable). Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the original
> grading is the `**Severity:**` line below.

- **Severity:** high — it blocks a commit outright, and the printed remedy does not resolve it.
- **Status:** open — no AC yet.
- **Occurrences:** observed twice in one session, `9104af22` → `0374b637`. · **First seen:** 2026-09-29 · **Last seen:** 2026-09-29
- **Where:** `templates/scripts/commit_guardian/check_output_drift.py` (the deployed-file census); the offending path is `.claude/.cache/readme_markers/fallback-<n>.json`; the ignore rule is `.gitignore:15` (`.claude/.cache/`).

**What happens.** Commit, and the gate exits 2 with:

```
UNCOMPARABLE: GAP .claude/.cache/readme_markers/fallback-280953.json action=run build.py to register it
check-output-drift: RESULT verified=495 uncomparable=6 exempt=5 gaps=1 drifted=0 missing=0 unreadable=0
```

Note `drifted=0`. Nothing has actually drifted. The single `gap` is enough to fail the hook.

**Why the remedy does not work.** The file is a runtime marker cache written by a
hook *during the commit attempt itself* — its content is a single mapping from an
absolute worktree path to a SHA-256 of `templates/scripts/commit_guardian/README.md`:

```json
{
  "/home/henzeh/.../templates/scripts/commit_guardian/README.md": "6a0b2d8b…"
}
```

It is not a build output, so `build.py` has nothing to register it *from*. Running
`build.py` — the action the hook prints — leaves `gaps=1` unchanged. Confirmed: built
twice, re-ran the census, identical result both times.

**Why it should never have been scanned.** `.claude/.cache/` is gitignored at
`.gitignore:15`, confirmed with `git check-ignore -v`. The drift census exists to
compare *deployed, build-determined* files against the manifest. A gitignored runtime
cache is neither deployed content nor build-determined, and its filename carries a
process-dependent suffix (`fallback-280953`), so no manifest entry could be stable
anyway.

**When it bites.** The cache is keyed on the README's hash, so it is written whenever
a commit touches `templates/scripts/commit_guardian/README.md`. That makes the failure
land on the commit *after* a README edit — which is why it presented as "the second
commit fails" rather than as a property of any one change. Deleting the file lets the
commit through; the next README edit recreates it.

**Two candidate fixes, both small.** Either exclude gitignored paths from the census
(the general fix — ask git, rather than walking the tree), or exclude `.claude/.cache/`
specifically the way the five `EXEMPT` entries already in the output are handled. The
first is preferable: the census currently has no notion of "the repository does not
track this", and any other gitignored runtime state added later will reproduce the bug.

**Related.** The `EXEMPT` ground strings already in this census all justify *tracked*
files whose content is human-owned rather than build-determined. This is a different
category — an untracked file that should not be in the census population at all — so
adding another `EXEMPT` entry would be treating the symptom.
