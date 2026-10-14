---
title: "A check now proves every copy of the usable-log-stream rule agrees with the canonical one (INF-500d-4-ix)"
date: "2026-10-14"
time: "14:10"
type: manual
components: 
  - infrastructure
summary: "Every duplicate of the rule that decides whether a log location can be used is now checked against the one authoritative rule, so a copy that drifts fails a test instead of misbehaving in production. With that done, the work to give every workspace one durable log location is complete."
description: "One commit (a19e78f6b). Adds a parity check under unit_tests/feedback/ that runs the canonical sink_resolution.py and five copies from the deployed install (emit_event, the inline-work guard, the plan-feature telemetry command, and the pre-drive probes in building-epics section 1.0 and epic-supervisor check 7) over a 14-row table of declarations and layouts; shell copies are executed with bash. Includes verdict and location parity tests, non-vacuity and drift-detection tests, all marked shared_layout_reader. On the deployed layout it reports copies_compared=5 rows_compared=14 with no disagreements. INF-500d-4-ix is marked done with covered_by and implemented_by, and composite INF-500d-4 is marked done because -ix was its last open child. Also adds the generated ticket with its phase sign-offs."
commits: 
  - a19e78f6b
breaking: false
---

## Entry
