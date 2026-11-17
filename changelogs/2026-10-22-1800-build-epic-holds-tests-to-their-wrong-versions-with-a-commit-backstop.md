---
title: "/build-epic holds every guarding test to its named wrong versions, with a pre-commit backstop that refuses ungated ticket commits"
date: "2026-10-22"
time: "18:00"
type: manual
components:
  - testing_quality
  - build_orchestration
  - commit_guardian
summary: "The ticket-supervisor now runs the red-baseline reader and the wrong-version sequence before every commit spawn on /build-epic, and a new blocking pre-commit hook (check-build-epic-gate-verdicts) refuses a ticket commit unless fresh red-baseline and wrong-version verdicts for that ticket's own requirements are on record. build-epic.js recovers once at the drive head, opens a per-ticket marker, and builds a batch one ticket at a time whenever a ticket owes wrong-version runs."
description: "TQ-500g-1-vii, TQ-500g-1-viii, TQ-500f-3-iv (one change). Supervisor: building-epics SKILL.md §5.10 and ticket-supervisor.md run input check, serial check, heavy_lane_gate (--record; once before the wrong-version steps when a resumed drive spawns no coder), list -> test-breaker -> wrong_version_gate.py finish (--record) under the commit lock before every commit spawn, with quoted commands and fail-closed parses. Backstop: scripts/build_orchestration/gate_verdict_records.py (atomic records under <git-dir>/leafcutter/gate-verdicts/<ticket-key>/; the marker snapshots the ticket's own source_ac at open) and templates/scripts/commit_guardian/check_build_epic_gate_verdicts.py (registered, autofix rule, docs): records must match the marker's source_ac, not-applicable blocks when runs are owed, staged code paths are checked for staleness, unattributed code commits are refused without offering a way to close the marker. --record added to wrong_version_runner.py run, wrong_version_gate.py finish (clears the old record first) and fast_lane.py heavy_lane_gate. build-epic.js: be-wv-recover at the drive head, per-ticket marker open/close, one ticket per chunk when runs are owed (user decision). Review findings H-1, H-2 and path normalisation fixed test-first."
commits:
breaking: false
---

## Entry

Epic builds now get the same guard as the fast lane and single-ticket builds: before each
ticket commits, its tests are tried against the wrong versions they promise to catch. On top
of that, a pre-commit check refuses any ticket commit from an epic drive that does not have
fresh, matching verdicts on record, so the guard cannot be skipped by a supervisor that leaves
a step out.
