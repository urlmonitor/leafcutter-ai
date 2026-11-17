---
title: "A test-free requirement record needs its own stated reason, and waived records leave the untagged-done count"
date: "2026-10-25"
time: "18:00"
type: manual
components:
  - ac_store
  - commit_guardian
  - knowledge_management
summary: "Wave 1 of the done-proof remedy (ADR-076). check-ac-schema now refuses a staged record with test_required: false and no test_rationale, using the done gate's own reason-present rule. It also refuses a reason identical, once normalised, to another test-free record's. The untagged-done ratchet stops counting records the done gate waives, so the mark drops from 240 to 209. The it-po template asks for a record-specific reason, and a new reference page explains test-free declarations."
description: >-
  BO-2500a-8-i/-v: new templates/scripts/commit_guardian/_ac_test_rationale_validators.py,
  wired into check_ac_schema.py. Only staged or changed records are refused, and it
  fails closed when the shared helper or the store index can't be read. The
  schema's test_rationale description states both meanings, with no if/then
  rule. KM-ADM-005-1: scripts/ac_store/untagged_done_count.py measures finished,
  tagged, untagged and excluded records, each exclusion with its ground
  (superseded; waived: declared test-free with a stated reason). Unreadable
  record files fail the ratchet. HIGH_WATER_MARK 240 -> 209. BO-2500a-8-ii:
  templates/agents/it-po.md presents test_required: false together with its
  test_rationale. The live with/without proof is an agent eval (it-po and
  it-po-without-reason-rule, scripts/evals). BO-2500a-8-iii:
  docs/reference/test-free-declarations.md. Also: ADR-076 (Proposed), the
  requirement records for wave 2 (BO-2500f) and two known issues.
breaking: false
---

## Entry
