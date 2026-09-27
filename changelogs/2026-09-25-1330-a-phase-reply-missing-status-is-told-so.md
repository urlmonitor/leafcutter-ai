---
title: "A phase reply missing its status is told so, instead of being sent after handoff_target"
date: "2026-09-25"
time: "13:30"
type: manual
components:
  - build_orchestration
summary: "A phase agent whose reply lacks `status` is now rejected for the missing status alone. Before, the reply schema also demanded `handoff_target`, and retrying agents chased that field instead of fixing the reply."
description: "The phase reply schema in templates/workflows-js/build-feature.js, and its twin in build-ticket.js, required handoff_target through a conditional whose `if` checked only `properties: { status: { const: 'handoff' } }`. In JSON Schema `properties` passes when the property is absent, so a reply with no status at all satisfied the `if`, and the `then` reported a missing handoff_target alongside the missing status. In run wf_e1f3e873-096 on 2026-09-25, documentation-expert had wrapped its whole reply in a single `input` string; it followed that message, added handoff_target on retries 3 and 5 instead of removing the wrapper, exhausted the five-retry cap, and halted the epic drive with its work already done. The `if` now also requires `status`, so the conditional applies only when status is present and equals 'handoff'. Every reply that was valid before is still valid, and a handoff without a target is still refused. Folded into the existing line, so neither driver grows. AC BO-3000b; tests in unit_tests/workflows/test_bo_3000b_statusless_reply_schema.py, where reverting the change in either driver turns a test red. Recorded as KI-BO-20260925-1309, which this mitigates; the underlying conflict between the agent templates' output contract and the enforced schema remains open there."
commits:
breaking: false
---

## Entry

A phase agent that returns a reply without `status` is now told exactly that. Previously
the reply schema also reported a missing `handoff_target`, and retrying agents chased that
field until the retry limit halted the drive.
