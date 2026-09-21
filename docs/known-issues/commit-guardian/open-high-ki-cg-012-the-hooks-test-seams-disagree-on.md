---
title: "KI-CG-012 — The hooks' test seams disagree on both variable name and separator, so verifying a hook the wrong way exits 0 having checked nothing"
description: "KI-CG-012 — The hooks' test seams disagree on both variable name and separator, so verifying a hook the wrong way exits 0 having checked nothing"
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

# KI-CG-012 — The hooks' test seams disagree on both variable name and separator, so verifying a hook the wrong way exits 0 having checked nothing

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered at merge, 2026-08-25: filed as `KI-CG-008`, now `KI-CG-012`.** `main`
> independently minted its own `KI-CG-008` (plus 009-011) while this branch was in flight.
> Same collision `KI-BO-016` records, in a second register on the same day.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-24
- **Where:** `scripts/commit_guardian/check_ac_limits.py:398,418` versus
  `scripts/commit_guardian/check_ac_schema.py`

**Symptom.** The commit-guardian hooks each provide an environment-variable seam so a
caller can hand them a file list instead of reading the git index. The seams are not the
same. `check_ac_limits` reads **`HOOK_TEST_FILES`** and splits on **newlines**;
`check_ac_schema` reads **`HOOK_TEST_STAGED_FILES`** and splits on **`os.pathsep`**. Use
the wrong name or the wrong separator and the hook does not error — it resolves the whole
list to one nonexistent path, finds no AC files to examine, prints nothing, and **exits
0**. The caller sees a clean run from a hook that inspected nothing.

**Evidence.** Found 2026-08-24 by an authoring agent verifying six new AC files. Passing
a colon-separated list to `check_ac_limits` via `HOOK_TEST_FILES` produced silence and
exit 0. Re-running the identical file set newline-separated produced the expected
`OVERRIDE ACTIVE` audit lines for `BO-2400c` (6/6) and `BO-2400f` (12/12) — so the hook
was working correctly the whole time and the first invocation had simply handed it
nothing.

**Why it matters more than a CLI quirk.** This is the verification path. Someone reaching
for the seam is, by definition, trying to confirm a hook would have blocked something —
and the failure mode returns exactly the answer they were hoping for. It is the same shape
as the `argv`-ignoring trap already recorded against these hooks in KI-CG-001 and in
`CLAUDE.md`'s "AC-store commits" section: *silence from an AC hook is not a pass, it may
mean the hook was never given your file*. Two seams with two names and two separators
multiplies the ways to get that silence.

**Fix direction.** One seam, one name, one separator, shared by every hook — and make it
**fail closed**: if the variable is set and resolves to zero existing files, exit non-zero
naming what could not be resolved, rather than exiting 0 having examined nothing. An
explicitly-provided list that matches nothing is a caller error, never a pass. Until then,
the reliable way to prove a hook saw your files is the one used here: re-run it with a
deliberately invalid file alongside the real ones and confirm it fails on the invalid one.
