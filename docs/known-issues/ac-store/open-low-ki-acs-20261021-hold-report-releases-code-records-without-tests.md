---
title: "KI-ACS-20261021-hold-report-releases-code-records-without-tests — the approval-hold report releases a code record with test_required false, which the commit-time schema check then refuses once it is approved"
description: "medium — APPROVAL_HOLD_CHECKS (scripts/ac_store/_approval_holds.py) holds only test design pending, reference file pending and file finding undecided. check-ac-schema (_ac_schema_validators.py, validate_test_contract) refuses an approved code AC with test_required false. The final gate therefore approves records that cannot be committed. Hit 2026-10-21 on ACD-2500c-2-ii and ACD-2500e-1-ii. Also seen: on Windows approve_acs.py writes CRLF line endings."
type: reference
category: reference
status: active
created: '2026-10-21'
last_updated: '2026-10-21'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20261021-hold-report-releases-code-records-without-tests — the gate approves what the commit refuses

> Filed 2026-10-21 during the EPIC-RightJobRightAgent follow-up epic's final gate. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing wrong lands, because the commit refuses it. But the gate tells the
  user that records are approvable when they are not, and the approval has to be undone by hand.
- **Status:** open, no AC.
- **Occurrences:** 1 · **First seen:** 2026-10-21 · **Last seen:** 2026-10-21
- **Where:** `scripts/ac_store/_approval_holds.py` (`APPROVAL_HOLD_CHECKS`), versus
  `templates/scripts/commit_guardian/_ac_schema_validators.py` (the "test_required: false on a code AC"
  refusal, about L629).

## What happened

The approval-hold report released all 31 records of the follow-up epic, none held. After
`approve_acs.py --ac` set them to approved, check-ac-schema refused two of them:
ACD-2500c-2-ii and ACD-2500e-1-ii. Both are python-coder records with `test_required: false`. They were
taken out of the commit, given `test_required: true` and a test design, and approved afterwards.

## Fix direction

- Add a hold to `APPROVAL_HOLD_CHECKS` for a code record with `test_required: false`, with a reason
  that is a member of HOLD_REASONS. It must use the same code-record test as the schema rule, so the
  two cannot drift apart.
- Separately: on Windows, `approve_acs.py` rewrote each file with CRLF line endings. Git normalised
  them on add, but the write should keep the file's own line endings.
