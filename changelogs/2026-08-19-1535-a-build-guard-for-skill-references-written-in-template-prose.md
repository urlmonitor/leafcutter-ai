---
title: A build guard for skill references written in template prose
date: "2026-08-19"
time: "15:35"
type: manual
components: 
  - build_pipeline
summary: "Adds a checker that verifies every skill an agent is told to load actually exists, and records the six that do not."
description: "Adds scripts/check_skill_refs.py, which resolves every (.claude|templates)/skills/<name> path written in a template body against the real templates/skills/ directory set and fails on an unresolvable one. This closes a blind spot in the build's only existing skill-reference check: build_phases.py resolves the skills_invoked field of config/agent_registry.json, a machine-maintained declaration that is rarely wrong, while the form that actually rots is the hand-typed path inside Markdown prose, which nothing read. Six dangling references had accumulated in that gap across at least three epics and were reported from a consumer install as missing knowledge-capture skills: route-learning and capture-learning (loaded by the signoff section 7 knowledge-capture step and by PO/BA/IT-PO v3), agent-telemetry (eight emit_event.py invocations in the building-epics runbook), and import-scanner / find-context-candle / trade-analysis (routing rows inherited when research-agent was copied in from a trading-system project). None was ever committed, and every call site treats skill-not-found as a pass, so all six were silent runtime no-ops -- the post-execution half of the knowledge system has never run and the epic runbook has never emitted a telemetry event. The checker distinguishes imperative references (Load ..., python ..., invoke via Bash), which fail, from descriptive mentions, which do not, and strips DECISION HISTORY comment blocks so an accurate record of a deleted skill is not treated as a defect. Also records the defect as KI-BP-007 in docs/known-issues/build-pipeline.md. The checker is not yet wired into CI or build.py, and the six dangling references are not yet resolved -- both are named as follow-up in the known-issues entry."
breaking: false
---

## Entry
