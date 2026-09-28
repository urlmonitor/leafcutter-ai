---
title: "Phase agents are told to fill the reply fields directly, not to return JSON text"
date: "2026-09-25"
time: "14:30"
type: manual
components:
  - build_orchestration
summary: "The phase-dispatch prompts in build-feature.js and build-ticket.js no longer ask agents to 'return a JSON result'. They tell the agent to fill the reply tool's status, message and handoff_target fields directly, and never to pass the reply as a JSON string or inside an `input` field."
description: "Both drivers dispatch each phase agent with PHASE_RESULT_SCHEMA enforced through the reply tool, whose fields are the schema's properties. Their prompts nevertheless told the agent to 'Return a JSON result with at minimum { \"status\": \"ok\" | \"blocker\" | \"failed\" }', describing the reply as JSON text. An agent that took that literally serialised its JSON and passed it as one string: documentation-expert did so on all five retries in run wf_e1f3e873-096 on 2026-09-25, and ac-fulfillment-gate once in wf_ee4e9d81-680, and each time the retry cap halted the epic drive with the ticket's work already done. The prompts also left out `handoff` from the status values and never named `handoff_target`, the field the driver routes handoffs on. The main dispatch prompt and the handoff re-dispatch prompt in build-feature.js, and the same two in its twin build-ticket.js, now name the fields to fill, include `handoff`, name `handoff_target`, and forbid the string wrapper. Edited in place, so neither driver grows. AC BO-2000c-5; three tests in unit_tests/workflows/test_bo2000c5_phase_dispatch_reply_shape.py run the real drivers through the engine harness and check the prompt actually dispatched; reverting either driver turns them red. Mitigates KI-BO-20260925-1309, alongside BO-3000b; the 36 agent templates whose output contract still asks for a JSON value are the open part of that issue."
commits:
breaking: false
---

## Entry

Phase agents are now told to fill the reply tool's fields directly — `status`, `message`,
and `handoff_target` when handing off — and never to pass the reply as a JSON string. The
old wording asked for "a JSON result", which some agents serialised into a single string
field, halting the drive after five rejected retries.
