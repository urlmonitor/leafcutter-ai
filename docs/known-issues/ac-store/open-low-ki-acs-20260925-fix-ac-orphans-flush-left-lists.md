---
title: "KI-ACS-20260925-fix-ac-orphans-flush-left-lists — fix_ac_orphans.py inserts indented items above a column-0 covered_by list, producing YAML that no longer parses, and returns True"
description: "low (latent) — the Case 3 branch finds the list end with ^\\s+-\\s, which requires indented dashes; 165 store records use column-0 lists. The script has no callers today."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/ac-store/resolved/resolved-blocker-ki-acs-017.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-fix-ac-orphans-flush-left-lists — fix_ac_orphans.py inserts indented items above a column-0 covered_by list, producing YAML that no longer parses, and returns True

- **Severity:** medium (indexed low). Destructive and self-reporting success, but the CLI currently has no callers, so the risk is latent until someone wires it up — which the "stage the parent" guidance invites.
- **Status:** open — no AC. Reproduced 2026-09-25 on a scratch record (sub-agent probe).
- **Where:** `scripts/ac_store/fix_ac_orphans.py:45` (`_patch_covered_by`), Case 3 at `:109-118`, `yaml.dump` fallback `:120-137`.

## Symptom

Given a parent whose list is serialised the way `yaml.safe_dump` writes it:

```yaml
covered_by:
- XX-100a
- XX-100b
```

the patch inserts `  - XX-100c` (indented) **above** the existing column-0 items. The result fails `yaml.safe_load`;
the function returns `True`.

## Mechanism

The end-of-list search uses `^\s+-\s`, which needs at least one leading space — the PhantomDoneFilesTouched
column-0 lesson (CLAUDE.md "Real-artifact behavioral spot-check") not applied here. There is no re-parse after
writing.

## Fixed here, not there

KI-ACS-017 added "re-parse and restore on failure" to `approve_acs.py` only; this writer, `_xref_apply` and
`epic_assembly` still write without verifying.

## Fix direction

Route through the shared `ac_record.set_field` proposed in KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key,
which must handle both list shapes and verify by re-parse.
