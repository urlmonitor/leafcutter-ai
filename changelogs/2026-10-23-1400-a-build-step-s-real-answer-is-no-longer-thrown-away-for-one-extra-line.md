---
title: "A build step's real answer is no longer thrown away for one extra line"
date: "2026-10-23"
time: "14:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "/build-feature, the single-ticket route and /build-epic halted on correct answers when the agent that ran a command step relayed one extra line with it: a passed red-baseline gate with 'exit: 0' after it, or the wrong-version writer's own log line before its list. They now read the answer out of the relayed text, and a reply that holds no single answer still halts exactly as before."
description: "TQ-500f-3-v. Found live on 2026-10-23: run wf_f982c0ab-e94 halted three of three tickets after ~4.2M tokens of correct work. The red-baseline gate had passed (gate_passed true, three red tests, verified true) but its executor relayed '<json>\\nexit: 0', and the whole-text JSON.parse rejected it as 'could not be verified'. wrong_version_writer.py logs 'base ref HEAD: N names declared, M derived' to stderr on every list call that derives names, the executor's shell tool merges stderr into the relayed stdout, and the list answer was read as null. New parseStepJson, one copy in templates/workflows-js/_shared/workspace-answer.js (the single source of the shell-step reply rules, inlined into every route between its WORKSPACE-ANSWER markers): the whole trimmed text if it is one JSON object, otherwise the one distinct line that is a JSON object on its own, otherwise null. Called by wvStep and the red-baseline gate in build-feature.js and build-ticket.js, and by gvStep in build-epic.js; each route template swaps its old parse line for the call, so no route grows. Every caller still fails closed on null (TQ-500f-3-ii). Three behavioural tests in unit_tests/workflows/test_step_json_relay_noise.py drive the real templates under the E2 harness and pair each noisy answer with six no-answer cases that must still halt; with the change stashed all three fail with the exact live messages. Neighbouring tq500f3* / tq500g1* tests and the shared-block route tests pass unchanged. TQ-500g-1-vi and -vii now point at the new reading rule. fast-lane-ship.js keeps its own strict parse (owned elsewhere); filed as KI-BO-20261023-fast-lane-step-reader-rejects-relay-noise."
commits: []
breaking: false
---

## Entry
