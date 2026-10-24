---
title: "The fast lane reads a wrong-version step's answer past a log line"
date: "2026-10-24"
time: "10:00"
type: manual
components:
  - build_orchestration
summary: "The fast lane halted at the wrong-version list step on every AC with derived names, because the agent that ran the command relayed the writer's own log line before the answer. It now reads the answer out of the relayed text, as /build-feature, the single-ticket route and /build-epic already do, and a reply that holds no single answer still halts."
description: "KI-BO-20261023-fast-lane-step-reader-rejects-relay-noise, now resolved. wrong_version_writer.py list logs 'base ref HEAD: N names declared, M derived' to stderr (_wvw_list.py:77); command-step-runner's shell tool merges stderr into the stdout it relays, so the list reply was '<log line>\\n<json>' and fast-lane-ship.js's wvStep read it with a whole-text JSON.parse, got null and halted with 'Wrong-version list step did not pass: null'. TQ-500f-3-v had fixed build-feature.js, build-ticket.js and build-epic.js and left the fast lane out. wvStep now returns parseStepJson(reply.stdout); the helper is the one in templates/workflows-js/_shared/workspace-answer.js, already filled into fast-lane-ship.js between its WORKSPACE-ANSWER markers, so nothing was copied and the file is one line shorter. wvStep serves the recover, list and finish steps; all three are fixed. Every caller still fails closed on null. Two behavioural tests in unit_tests/workflows/test_wv_fast_lane_relay_noise.py drive the real template under the E2 harness and pair each noisy answer with six no-answer cases that must still halt; with the change stashed both fail with the live halt, with it both pass. The other three routes needed no change: their deployed copy under .leafcutter was older than the TQ-500f-3-v fix. _wvw_list.py:77 stays at INFO."
commits: []
breaking: false
---

## Entry
