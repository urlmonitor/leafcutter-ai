---
title: "The fast lane holds every guarding test to its named wrong versions before it commits"
date: "2026-10-15"
time: "23:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "Right before commit, the fast lane now asks the writer what wrong versions are owed, has the read-only test-breaker prepare them, and runs them through the shared runner via one new wrapper (wrong_version_gate.py finish). A surviving or unpreparable wrong version stops the lane before commit and PR. The writer's list step is also much faster (about 1 s instead of 5-80 s)."
description: "TQ-500g-1-v (fast lane, manually orchestrated). New scripts/build_orchestration/wrong_version_gate.py finish runs the writer's write step on the preparer's reply (stdin) and, only when a manifest was written, the runner with the same --base-ref; it prints {gate_passed, stopped_at, writer, verdict} verbatim. fast-lane-ship.js gains a thin, fail-closed block immediately before commit (after knowledge routing): recover on a resumed drive, writer list, test-breaker only when something is owed (owed list passed unchanged), finish with the reply in a quoted here-document with a unique delimiter; any halt releases the claimed ACs and opens no commit or PR. New shared reader _wvr_records (one pass over the AC store parsing only files that mention a wanted id; pruned covers-tag scan) makes list, write and the runner fast without a second reader; a prefix-id miss found in review (X-1 vs X-1-i) fixed test-first. Older fast-lane workflow tests gained passing wrong-version stubs."
commits:
breaking: false
---

## Entry

The fast lane used to commit as soon as its tests were green. Now, just before it commits, it
checks that each guarding test would actually catch the wrong versions its requirement names.
An independent read-only agent prepares those wrong versions, a small writer turns them into
alterations, and the shared runner tries each one. If a wrong version gets through, or cannot
be prepared, the lane stops and says which one.
