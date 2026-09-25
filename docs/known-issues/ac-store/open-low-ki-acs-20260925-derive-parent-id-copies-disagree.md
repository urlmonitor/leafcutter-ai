---
title: "KI-ACS-20260925-derive-parent-id-copies-disagree — three copies of derive_parent_id give different parents for short ids"
description: "low — ac_parent_id.py uses [0-9]{3,}, scan_ac_store.py's private copy uses \\d+, check_ac_limits.py inlines a third; AB-12 -> AB vs None, AB-12a -> AB vs AB-12. Seven AC-id regexes exist in total."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/knowledge-management/open-high-ki-km-007.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-derive-parent-id-copies-disagree — three copies of derive_parent_id give different parents for short ids

- **Severity:** low. No current record hits the disagreeing shapes, but any fix to one copy (KI-KM-007) will not reach the other two.
- **Status:** open — no AC. Reproduced 2026-09-25 by calling both importable functions.
- **Where:** `scripts/ac_store/ac_parent_id.py:45,51,59` (canonical); `scripts/ac_store/scan_ac_store.py:832-882` (private copy); `templates/scripts/commit_guardian/check_ac_limits.py:453-477` (inline copy).

## Symptom

| Id | `ac_parent_id` | `scan_ac_store` |
|---|---|---|
| `AB-12` | `AB` | `None` |
| `AB-12a` | `AB` | `AB-12` |
| `KM-KGS-100a` | `KM-KGS` | `KM-KGS` (both wrong per KI-KM-007) |

## The wider grammar split

Seven independent AC-id patterns: `config/ac_store_schema.json:20` (canonical, compound-prefix aware),
`_ac_schema_validators.py:51` (`^[A-Z]{2,6}-[0-9]{3}$`, rejects every suffixed id in the no-jsonschema fallback),
`_presence_only_scanner.py:135` (`[A-Z]{2,5}`), `check_ac_coverage.py:41,44`, `check_test_ac_tags.py:46`,
`audit_ac_area.py:71`, `check_v2_ac_store_alignment.py:43`. Id **allocation** has no code at all — five prompt
copies (`product-owner.md:339`, `ac-tree-split/SKILL.md:86`, `quick-fix/SKILL.md:440`, `quick-fix.js:401`,
`business-analyst.md:246`), which is KI-ACD-008.

## Fix direction

One `ac_id` module (`PATTERN`, `parse`, `parent`, `next_free(store, prefix)`) derived from the schema's pattern;
delete the copies. Cluster 1/2 of the 2026-09-25 duplication analysis.
