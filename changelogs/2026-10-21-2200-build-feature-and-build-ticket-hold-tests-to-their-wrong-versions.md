---
title: "/build-feature and build-ticket.js hold every guarding test to its named wrong versions before each commit"
date: "2026-10-21"
time: "22:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "Both per-ticket routes now run the shared wrong-version sequence (writer list, read-only test-breaker, wrong_version_gate.py finish) immediately before every commit dispatch, including a re-dispatch after a remedy agent, and stop the ticket when a wrong version survives or cannot be prepared. /build-feature drives a batch one ticket at a time whenever a ticket owes wrong-version runs, so no run ever sees a sibling's unfinished code."
description: "TQ-500g-1-vi (fast lane, manually orchestrated). build-feature.js and build-ticket.js gain thin, fail-closed bf-wv-*/bt-wv-* blocks: recover once at the drive head on a resumed drive (build-feature.js) or after the Worktree Guard on every drive (build-ticket.js), never inside the per-ticket driver; list -> test-breaker (only when owed, list unchanged) -> finish with the reply in a quoted here-document, --base-ref HEAD; halt shape {gate, wrong_version_step, wrong_version_detail}; K3 recorded as wrong_version_outcome, never verified. User decision 2026-10-21: one ticket per chunk when any batch ticket has (or lacks a readable) source_ac; a ticket that finds ids in a parallel chunk halts before any wv step. Review fixes: every path and value is double-quoted and ids/work keys are checked against ^[A-Za-z0-9._-]+$ before any command is built (paths with spaces, e.g. 'Bybit-Trader Live', now work). command-step-runner's spawned_by gains both routes. Existing workflow tests get passing default wv replies from one shared harness module."
commits:
breaking: false
---

## Entry

Tickets built through /build-feature or a single-ticket build now get the same check the fast
lane got: just before each commit, the tests that promise to catch named wrong versions are
tried against those wrong versions, and the ticket stops if one gets through. Epics whose
tickets owe these runs build one ticket at a time, so each ticket's runs only ever see its
own change.
