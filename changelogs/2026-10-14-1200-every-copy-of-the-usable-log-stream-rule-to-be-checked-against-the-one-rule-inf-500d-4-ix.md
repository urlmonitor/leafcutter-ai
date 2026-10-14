---
title: "Every copy of the usable-log-stream rule to be checked against the one rule (INF-500d-4-ix)"
date: "2026-10-14"
time: "12:00"
type: manual
components: 
  - infrastructure
  - agent_telemetry
  - knowledge_system
summary: "New draft requirement: the five copies of 'is this declared log stream usable, and is its enduring root live' must give the same verdict as the canonical rule. A copy that drifts must fail a check, not surface in production."
description: "One content commit (4ce127149), acceptance criteria only. Adds INF-500d-4-ix, a draft L3 under INF-500d-4, and adds it to INF-500d-4's covered_by. ADR-069's usable-stream and stale-root rule lives canonically in sink_resolution.py and is restated in five places: the standard-library inline copies in emit_event.py and inline_work_guard.py, the telemetry command plan-feature.js dispatches, and the pre-drive probe snippets in building-epics section 1.0 and epic-supervisor check 7. Only emit_event is pinned by a parity test today. The new criteria require all five to agree with the canonical rule on one table of declarations and layouts: absent, empty, unparseable, no root, relative root, missing or relative stream, a stream outside or nested under the root, a fresh install, and a vanished enduring root, in both layouts. The shell copies must be executed as written, not grepped. A canonical change that one copy does not follow must fail a check naming that copy. readiness stays draft until BrainCandy approves."
commits: 
  - 4ce127149
breaking: false
---

## Entry

ADR-069's rule for "is this declared log stream usable, and is the enduring root that holds
it still live" has one canonical home, `scripts/knowledge/sink_resolution.py`. It is also
restated in five other places. Only one of them, `emit_event.py`, is checked against the
canonical rule. The architect-review on tickets 03 and 05 of
EPIC-OneDurableLogRootForEveryWorkspace flagged that the rest can drift without anyone
noticing.

- **INF-500d-4-ix added** (draft, `origin_agent: BrainCandy`). Every copy must give the
  canonical verdict on one table of declarations and filesystem layouts. On usable rows each
  copy must report the same location. On unusable rows no copy may create anything. The
  table must contain exactly the expected usable rows, so copies can't pass by all agreeing
  on the same wrong answer.
- **The shell copies are run, not grepped.** These are the plan-feature telemetry command
  and the two pre-drive probes. Each is executed exactly as deployed against the same
  layouts, following the repo rule that gate behaviour is verified behaviourally.
- **Drift fails loudly.** A canonical change that one copy doesn't follow fails the check,
  and the failure names the copy, the row and both verdicts. A copy the check can't find
  also fails, and every run reports how many copies and rows it compared.
- **Placement.** It is an L3 under INF-500d-4 because INF-500d is already at the 5-L2 cap.
  INF-500d-4's `covered_by` now lists it.

No code changes. No new ADR.
