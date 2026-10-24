---
title: "The post-merge suite now runs every live-database test, and a database that is down can no longer look green"
date: "2026-10-23"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "After every push to main and on the heartbeat, the post-merge suite now runs the live-database tests against disposable Neo4j containers, and an unreachable database ends the run as \"did not complete\" instead of green or as false test failures."
description: "TQ-600a-13-xxi, -xxii, -xxiii, -xxv. Post-merge: tests/knowledge_live runs against disposable Neo4j containers identical to the PR Proof-of-done check, with one retry; a test failing twice turns the run red, and the live result is part of the one combined verdict. A database that never became healthy, or a live test skipped because the database was unreachable, gives \"did not complete\" (never green, never test failures); a skipped live test is never counted as passed, and a test that failed once then skipped on retry stays failing. The eight live test files share one skip reason (tests/knowledge_live/lane/_live_skip.py). The post-merge notice lists failing live-database tests in their own section. A pull request declaring a fix for a red live lane is proven against a started database (a skip is not proof), and the correctness lane is still proven whenever it is not green. A malformed LIVE_DB_STARTUP_LIMIT is reported as a clear configuration error. The PR Proof-of-done check is unchanged and still runs the live tests of the criteria a PR changes."
breaking: false
---

## Entry
