---
title: "Changelog PR #424 — fix component registration (agent_telemetry, epic_retrospective, duplicate-key dedup) — 2026-08-13"
date: "2026-08-13"
time: "13:30"
type: manual
components: 
  - agent_telemetry
  - epic_retrospective
  - ac_driven_dev
  - build_orchestration
  - finalize
  - persona_management
  - stakeholder_delivery
  - ux_prototyping
summary: Fixed the internal map of system components so telemetry tooling points at real files and every components documentation link actually resolves.
description: "1 commit (67ef27b33), PR #424 — fix(ac-store): fix component registration. docs/components.json: agent_telemetry.primary_code pointed at .claude/skills/agent-telemetry/scripts/emit_event.py, which does not exist anywhere in the repo (its own architecture doc already recorded that entry point as retired); repointed to the two real files under scripts/agent-health/. scripts/retrospective/ had no owning component at all, so nothing in it could be attributed — registered a new component epic_retrospective with a new architecture doc at docs/architecture/components/epic-retrospective.md and a depends_on: [agent_telemetry] edge. docs/components.json also carried six duplicate top-level keys (ac_driven_dev, build_orchestration, finalize, persona_management, stakeholder_delivery, ux_prototyping); JSON last-wins meant every consumer was silently reading the impoverished second copy (detail_ref: null, and for four of them primary_code: []), leaving six real architecture docs effectively unreferenced. Deduplicated, keeping the richer values. Verified after the fix: 44 components (43 from main plus epic_retrospective), zero detail_ref or primary_code fields degraded, six detail_refs restored. The AC-store authoring work in the same PR (observability + gate-value AC trees under docs/acceptance-criteria/) is specification-only — readiness: draft, work_status: todo — and is exempt from this changelog as it ships no behaviour."
pr: 424
commits: 
  - 67ef27b33
breaking: false
---

## Entry
