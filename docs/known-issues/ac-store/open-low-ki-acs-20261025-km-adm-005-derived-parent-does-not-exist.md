---
title: "KI-ACS-20261025-km-adm-005-derived-parent-does-not-exist — the requirement rule check derives parent KM-ADM for KM-ADM-005, a record that does not exist"
description: "low — requirement_rule_check.py's parent-to-child back-links family derives the parent of KM-ADM-005 from its id as KM-ADM, which is not a record. The record's explicit parent is KM-ADM-100a. Any stage run that changes KM-ADM-005 therefore ends with verdict failed ('needs a decision'). Hit 2026-10-25 when KM-ADM-005-1/-2 were added under it."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20261025-km-adm-005-derived-parent-does-not-exist — the rule check derives a parent that does not exist

> Filed 2026-10-25 while authoring the done-proof remedy (BO-2500f, BO-2500a-8, KM-ADM-005-1/-2). Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The finding stops a stage's rule check, but the real tree is sound: the explicit
  `parent: KM-ADM-100a` is valid, and check-ac-parent-covered-by and check-ac-tree-limits pass.
- **Status:** open, no AC. Filing it was user-approved at the BA gate on 2026-10-25.
- **Occurrences:** 1 · **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where:** `scripts/ac_store/requirement_rule_check.py`, the parent-to-child back-links family. The
  flat id `KM-ADM-005` does not follow the `<ROOT>-<n><letter>-…` pattern the id-derived parent
  assumes.

## What happened

The BA stage added KM-ADM-005-1 and KM-ADM-005-2 and set KM-ADM-005's `covered_by` to them. Because
KM-ADM-005 was now changed, the rule check examined it. It derived the parent `KM-ADM` from the id and
reported "needs a decision: parent KM-ADM does not exist". The finding existed before; it only shows up
when the record is changed.

## Fix direction

- When a record carries an explicit `parent:`, the back-links family should use it rather than an
  id-derived parent, or at least fall back to it when the derived parent is missing.
- The same applies to every other flat-id family (KM-ADM-*). Check for them when fixing.
