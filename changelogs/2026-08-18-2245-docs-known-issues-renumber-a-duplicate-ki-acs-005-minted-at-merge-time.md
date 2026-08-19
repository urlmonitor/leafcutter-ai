---
title: "docs(known-issues): renumber a duplicate KI-ACS-005 minted at merge time"
date: "2026-08-18"
time: 2245
type: manual
components: 
  - ac_store
  - build_pipeline
summary: "Two different known issues were filed under the same number. Renamed the second one and wrote down why it happened, because it is the third time the same way in two days."
description: "PR #497 landed a KI-ACS-005 that duplicated the KI-ACS-005 added by PR #496 three minutes earlier. Renumbered to KI-ACS-007 and updated the KI-BP-006 cross-reference that pointed at it. Verified: no duplicate KI id remains in any register. The entry now records the mechanism instead of hiding the churn — the number was verified free at authoring time and taken by merge time, which is the same failure already filed as KI-ACS-003 (the AC store has no id-uniqueness gate) and KI-ACD-008 (id allocation reads a stale view of what is taken). Third instance of one mechanism in two days, and the known-issues registers have the same hole with no gate at all. The property that matters is uniqueness AT MERGE; checking free-ness at authoring cannot establish it, so the fix is one gate over the merged tree rather than more care while writing."
breaking: false
---

## Entry
