---
title: "KI-CG-20260909-gate-doc-links — `check-doc-links` returns 0 unconditionally, so registering it adds a gate that cannot fail"
description: "KI-CG-20260909-gate-doc-links — `check-doc-links` returns 0 unconditionally, so registering it adds a gate that cannot fail"
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

# KI-CG-20260909-gate-doc-links — `check-doc-links` returns 0 unconditionally, so registering it adds a gate that cannot fail

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low.
- **Status:** open — no AC.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_doc_links.py` — `main()` returns 0 on every path.

**The numbers.** Population is 117 files (798 of 915 `.py` excluded by `EXCLUDED_DIRS` = tests, unit_tests, templates, debugging, alembic, legacy — note that excludes **all** of `templates/`). 13 warnings in 9 files today.

**The decision this needs.** Only 13 violations, so unlike the others there is no grandfathering problem — it could enforce almost immediately. The session's real question is whether the `EXCLUDED_DIRS` scoping is right: excluding all of `templates/` means the canonical source of every deployed script is exempt from doc-link traceability, which is likely backwards for this repo.

**Definition of done.** Either it enforces (13 fixed, non-zero exit wired) or it is deliberately documented as advisory and registered as such. A gate that silently cannot fail is the worst of the three states.

---
