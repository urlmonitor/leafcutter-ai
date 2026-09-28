---
title: "KI-ACS-20260925-validate-ac-bare-directory-exits-0 — validate_ac.py still has the KI-ACS-001 no-op: given a directory it validates nothing and exits 0"
description: "high — the KI-ACS-001 fix landed in validate_ac_schema.py only; its sibling validate_ac.py, which it-po.md tells agents to run, skips a directory argument, prints 'No YAML files to validate.' and exits 0."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-27'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/ac-store/open-high-ki-acs-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-validate-ac-bare-directory-exits-0 — validate_ac.py still has the KI-ACS-001 no-op: given a directory it validates nothing and exits 0

- **Severity:** high. A validator that checked zero files reports success — the exact failure CLAUDE.md's "AC-store hygiene" section records as fixed.
- **Status:** open — **partially fixed**. The bare-directory no-op is fixed by PR #914 (merged as 2bf8cbae, AC ACS-100i-7-ii): a directory argument is walked recursively and a zero-file run exits non-zero, verified 2026-09-25 by a red/green/mutation-proof run. Still open (not re-verified 2026-09-27): `validate_ac.py` is in no deploy map, so the `it-po.md:359` call cannot find it in an adopter, and `backfill_readiness.py` still exits 0 on zero files.
- **Where:** `scripts/ac_store/validate_ac.py:338-353`; weaker form in `scripts/ac_store/backfill_readiness.py:156-158` (exits 0 on zero files).

## Symptom

```
$ python scripts/ac_store/validate_ac.py docs/acceptance-criteria/<component>
No YAML files to validate.        # exit 0
```

## Mechanism

The argument loop keeps only paths with a `.yaml`/`.yml` suffix; a directory fails the suffix check and is dropped
silently. Zero resolved files is treated as success.

## Fixed here, not there

KI-ACS-001 (resolved 2026-08-19) made `validate_ac_schema.py` walk directories recursively and exit non-zero on zero
files (`:315-319`, `:428`). The sibling `validate_ac.py` was not touched. `templates/agents/it-po.md:359` tells IT-PO
to run `validate_ac.py`, and the script is not in any deploy map, so in an adopter the call also fails to find it.

## Fix direction

Delete `validate_ac.py` and point `it-po.md` at the single validator, or make it a thin wrapper over the same
`validate_record()` entry point proposed in cluster 9 of the 2026-09-25 duplication analysis. Either way a
zero-file run must exit non-zero.
