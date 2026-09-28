---
title: "One red-baseline check refuses absence-only red, in the fast lane and in /build-feature"
date: "2026-09-27"
time: "21:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "A test that names wrong versions to catch (must_catch or angle: discrimination) no longer counts as red when it only fails because the code is missing. The same reader now runs in /build-feature and its build-ticket twin before the coder, fails closed on any unreadable reply, and refuses when test identity is ambiguous."
description: "TQ-500f-3-i and TQ-500f-3-ii (fast lane, manually orchestrated). verify_red_baseline gains --ac-root: a pytest plugin records each test's real exception type (absence vs assertion); a declared test whose only red is absence fails the whole gate (declared_test_refused_absence_only_red); undetermined kinds, missing declared tests, unloadable ACs and ambiguous test identities fail closed with their own reasons. New fast_lane.py heavy_lane_gate wraps the same reader for /build-feature: build-feature.js and build-ticket.js dispatch it before the first coder phase on every path (including resumed tickets), halt unless gate_passed is true, and record 'red-baseline reader not applicable: no source requirement' for tickets without a source AC. The deeper tag-to-test identity fix in done_proof is TQ-500f-3-iii."
commits:
breaking: false
---

## Entry

The red-baseline check used to accept any failing test as proof that a test guards the
code, even one that only failed because the code it imports did not exist yet. For tests
that declare the wrong versions they must catch, that is no longer enough: they must fail
by reaching the code. The same check now also runs in /build-feature before the coder,
instead of trusting the test writer's own report, and it stops rather than guesses when
anything about the run is unclear.
