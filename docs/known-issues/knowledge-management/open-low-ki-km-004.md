---
title: "KI-KM-004 — `check_ac_coverage.py` exists on disk but is registered nowhere, so `covered_by` test entries are never read"
description: "KI-KM-004 — `check_ac_coverage.py` exists on disk but is registered nowhere, so `covered_by` test entries are never read"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-004 — `check_ac_coverage.py` exists on disk but is registered nowhere, so `covered_by` test entries are never read

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_ac_coverage.py`

**Symptom.** A hook script that looks like a live coverage gate is not in
`commit_guardian.json`'s `hooks_manifest`, so it never runs. Nothing in the repo reads
the test entries in an AC's `covered_by` field. The `ac-tested` edge (AC → Test) is
therefore unenforced despite a plausible-looking enforcement script sitting next to the
registered hooks.

**Evidence.** Zero matches for `check_ac_coverage` or `ac-coverage` in
`templates/scripts/commit_guardian/commit_guardian.json`. The `ac-tested` edge is rated
`enforcement: "none"` in the graph JSON on exactly this ground — the demotion that
`KM-ADM-001` was authored to produce.

**Why it stays dangerous while it sits there.** The next person to ask "is AC→Test
enforced?" finds a script named `check_ac_coverage.py` and reasonably assumes yes. Either
register it or delete it; leaving it is the trap.

**Workaround.** Use the reverse edge `test-covers` (`# covers: <AC-ID>` in test files),
which **is** enforced by `check-done-proof` — subject to KI-KM-002's diff scope.

---
