---
title: "The fast lane refuses work it cannot build, before it charges you for the run"
date: "2026-08-25"
time: 2359
type: manual
components: 
  - build_orchestration
summary: "A run whose resolved set contains a member no phase can produce now ends in a named refusal before it claims anything or dispatches a build agent, instead of jamming at the finish gate after the test-writer and the coder have both been paid for."
description: "Implements BO-2400f-12, BO-2400f-12-i and BO-2400f-12-ii. fast_lane.py gains compute_producibility_verdict plus a check_producibility CLI subcommand; fast-lane-ship.js dispatches it between the Resolve step and the claim step, so every later phase is unreachable on a refusing verdict. The check is positive-declaration-only: a member is unproducible when it declares test_required false, or names an assigned_agent no phase dispatches. Silence is not a declaration, and readiness, priority, req_status and status are never read, so this cannot become a second approval gate. The read is fail-closed by the same plain-falsy pattern the red-baseline gate uses: a missing key, a null or an unparseable reply refuses. A refusal writes nothing to the store and releases nothing, because it precedes the claim and so holds none. Reviewer-caught defect fixed before merge: the roster first shipped as python-coder, sql-coder and frontend-coder, but this lane dispatches only python-coder from the Coder phase and test-writer from the Test Writer phase. Listing the other two would have judged 29 real not-done frontend-coder records producible and handed them to the wrong agent, reproducing the very failure the guard exists to pre-empt. The roster is now python-coder and test-writer, pinned by a regression test that asserts both directions in-process and through the CLI in a fresh process."
breaking: false
---

## Entry
