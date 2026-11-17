---
title: "KI-ACS-20261025-test-design-rule-check-demotes-approved-records — a later stage's rule check rewrites readiness approved back to reviewed on records that stage did not change"
description: "low — requirement_rule_check.py --stage test-design --before-ref HEAD, run by a test-designer on one record, rewrote readiness from approved to reviewed (BO-2500f: to draft) on 17 other records just approved at the /plan-feature-style final gate. The rewrites were working-tree edits only and did not reach the commit. Seen 2026-10-25 on ac-authoring/done-proof-verification."
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

# KI-ACS-20261025-test-design-rule-check-demotes-approved-records — a later stage demotes records it didn't touch

> Filed 2026-10-25 while authoring the done-proof remedy (BO-2500f, BO-2500a-8). Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The rewrites were working-tree edits and were not committed. But a commit made
  right after such a run would have quietly undone the user's final-gate approval of 17 records.
- **Status:** open, no AC. Filing it was user-approved on 2026-10-25.
- **Occurrences:** 1 · **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where:** `scripts/ac_store/requirement_rule_check.py`, the readiness repair applied by the
  rule families when a stage is not the owner of a changed field.

## What happened

The final gate approved 23 records at priority high with `approve_acs.py --ids`. A test-designer
then designed one remaining record, BO-2500f-3-iii, and ran
`requirement_rule_check.py --changed-since HEAD --stage test-design --before-ref HEAD` as its
template requires. At that moment the approvals were staged but not yet committed. HEAD still held
the records at reviewed, so the check read the readiness change as a test-design-stage edit of a
protected field. It "repaired" each record by writing readiness back to reviewed, and BO-2500f to draft.

## Fix direction

- A readiness change made by the approval step (`approve_acs.py`) is not a stage-owned edit; the
  protected-fields family should recognise it. One way: compare against the index instead of
  HEAD when approvals are staged. Another: let the approval step record its own amended_by marker
  that the check honours.
- Until then: commit the approvals before any later-stage rule check runs.
