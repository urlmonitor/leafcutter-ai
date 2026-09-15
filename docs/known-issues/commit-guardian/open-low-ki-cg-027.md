---
title: "KI-CG-027 — `main()` derives the project root from `Path.cwd()` while the canonical resolver sits unused beside it"
description: "KI-CG-027 — `main()` derives the project root from `Path.cwd()` while the canonical resolver sits unused beside it"
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

# KI-CG-027 — `main()` derives the project root from `Path.cwd()` while the canonical resolver sits unused beside it

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495. The
  shared resolver it should adopt (`_resolve_root.py`) **is** on `main` and is imported by 27
  sibling files.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `check_identifier_uniqueness.py` `main()`; against
  `templates/scripts/commit_guardian/_resolve_root.py`

**Symptom.** Under `pre-commit` the cwd happens to be the repo root, so it works **by luck**.
From any nested directory it does not:

```
$ env --chdir=<consumer>/docs python3 .../check_identifier_uniqueness.py
BLOCKING: ... acceptance-criteria, decisions, diagrams, work-items      exit 1
```

All four namespaces unresolvable, so with the `KI-CG-007` fail-closed fix in place it
hard-blocks. Any agent or manual invocation from a subdirectory is affected.

**Fix direction.** Adopt `_resolve_root.py` (git-toplevel first). The resolver exists, is
already the convention, and is in the same directory — this is a one-import change, not a
design question.

---
