---
title: "KI-ACS-20260925-v2-alignment-flat-lookup-misses-feature-folders — check_v2_ac_store_alignment.py looks ACs up at <component>/<id>.yaml and cannot see the 92% of records that live in feature folders"
description: "high — ac-validator step 2c relies on this script; its flat lookup and truncating id regex miss 3,889 of 4,229 store records, so the alignment check passes by not finding them."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-ACS-20260925-v2-alignment-flat-lookup-misses-feature-folders — check_v2_ac_store_alignment.py looks ACs up at <component>/<id>.yaml and cannot see the 92% of records that live in feature folders

- **Severity:** high. A validator used on the commit path of every ticket (`ac-validator` step 2c) inspects a small minority of the store and reports clean.
- **Status:** open — no AC. Counted 2026-09-25 (sub-agent): 4,229 records, 3,889 under feature folders.
- **Where:** `templates/scripts/commit_guardian/check_v2_ac_store_alignment.py:43,152,165`; root resolution at `:294`.

## Mechanism

- Lookup path is `<component>/<id>.yaml` — no recursion into `<component>/<FEATURE>/`.
- The id regex truncates suffixed ids, and the "prefix" is taken as everything before the last `-`, so compound
  prefixes (`KM-ADM-…`) and deep ids resolve to the wrong component.
- Root resolution is `__file__.resolve().parent.parent.parent` if it has `.git`/`templates/`, else cwd — one of the
  six strategies in KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent.

## Fixed here, not there

Every other store reader walks recursively (`rglob`), and the shared cached index
`commit_guardian/_ac_store_index.get_ac_index` exists; this script uses neither.

## Detection

Run it against a ticket whose ACs live in a feature folder; the ACs are reported missing or not checked, and the
run still exits 0.

## Fix direction

Look records up through the shared store index by `id` field, and the id grammar through the single `ac_id`
module (see KI-ACS-20260925-derive-parent-id-copies-disagree). A lookup miss must be a failure, not a skip.
