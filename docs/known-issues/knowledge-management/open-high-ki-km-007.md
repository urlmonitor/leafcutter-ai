---
title: "KI-KM-007 — Compound-prefix AC ids are invisible to the store's own parent/child tooling"
description: "KI-KM-007 — Compound-prefix AC ids are invisible to the store's own parent/child tooling"
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

# KI-KM-007 — Compound-prefix AC ids are invisible to the store's own parent/child tooling

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/ac_parent_id.py` (`derive_parent_id`), and its callers in
  `scripts/ac_store/scan_ac_store.py`
- **True home:** this is an `ac-store` defect. Recorded here because it was found here and
  it is what makes the `KM-ADM` tree's parent links non-enforcing. Move it when an
  `ac-store` known-issues file exists.

**Symptom.** `derive_parent_id` splits on the last hyphen-delimited segment, which assumes a
single-token prefix. For a compound prefix it strips the wrong segment:

```
derive_parent_id("KM-ADM-005")   -> "KM-ADM"    (expected "KM-ADM-100"-family root)
derive_parent_id("KM-ADM-100a")  -> "KM-ADM"    (expected "KM-ADM-100")
derive_parent_id("ACS-1100a")    -> "ACS-1100"  (correct — single-token prefix)
```

`"KM-ADM"` is not an AC id, so the lookup misses and the check treats the record as having
no parent to validate.

**Consequence.** For every compound-prefix family, `check-ac-parent-covered-by` never fires,
`check-ac-tree-limits` reads a populated parent as childless, and orphan scans report a
clean result over a set they cannot see. The hooks are silent, and their silence reads as a
pass. This is the AC-store analogue of KI-KM-004: tooling that looks live and is not.

**Verified by execution**, not by reading — the three calls above were run against
`scripts/ac_store/ac_parent_id.py` in this worktree on 2026-08-18.

**Blast radius beyond `KM-ADM`.** `KM-KGS` and `KM-VIS` use the same shape; `KM-KGS-100` has
carried the flaw since June. Any future `XX-YYY-NNN` family inherits it silently.

**Do NOT "fix" this by re-IDing.** AC ids never change — `KM-ADM-005` is cited by shipped
`# covers:` tags in the test suite, so renaming it breaks done-proof. The fix is in
`derive_parent_id`: support compound prefixes, or read an explicit `parent` field as a
fallback when derivation misses.

**Bearing on the 2026-08-18 reconciliation.** `KM-ADM-100` and its four L1s were authored
with correct `covered_by`/`parent` links. Those links are **documentation-grade**: a human
or an agent reading the store sees the tree, but no hook enforces it until this is fixed.

---
