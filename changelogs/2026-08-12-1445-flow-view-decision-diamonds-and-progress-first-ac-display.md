---
title: "Flow-view decision diamonds + progress-first AC display (UXP-596, UXP-591)"
date: "2026-08-12"
time: "14:45"
type: feature
components:
  - ux_prototyping
  - frontend_coding
  - testing_quality
summary: >
  The Atlas flows view now renders a flow's conditional branches as chained
  decision diamonds with labelled yes/no edges, and shows acceptance-criteria
  progress at a glance (a done/total pill per step plus a deduped feature-level
  rollup) with the individual ACs revealed on click.
description: >
  Two flows-view features on the shared graph/render layer (building on the
  mock-mode infra from PR #410). Decision diamonds (ADR-025, UXP-596): a step's
  branches are synthesised in buildFlowGraph into chained diamond nodes derived
  from existing branch data, rendered by a status-tinted FlowDecisionNode with
  yes/no edge labels. Progress-first AC display (UXP-591): the graph hides
  per-AC nodes by default, showing a status-tinted done/total pill per step and
  a deduped feature-level "N/M ACs done" rollup, with a persisted "Show ACs in
  graph" toggle and the drawer as the click-to-reveal path. Adds a vitest +
  @testing-library/react harness with 41 black-box tests written from the ACs.
  Backfilled ACs (UXP-596/597..601/606, UXP-602..605) are landed as
  work_status: in_progress — they are vitest-covered but the pytest-based
  proof-of-done oracle cannot yet see `// covers:` tags (a follow-up adds vitest
  support to the oracle, then they flip to done).
pr: 413
breaking: false
commits:
  - dbc6996c4
---

Flow-view decision diamonds + progress-first AC display. See ADR-025 and the
UXP-596 / UXP-591 acceptance-criteria families.
