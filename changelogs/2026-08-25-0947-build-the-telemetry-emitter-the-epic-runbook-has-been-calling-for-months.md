---
title: Build the telemetry emitter the epic runbook has been calling for months
date: "2026-08-25"
time: "09:47"
type: manual
components: 
  - build_pipeline
summary: "Implements emit_event.py at the deployed path eight runbook call sites already invoke, so an epic drive finally records what it did."
description: "Implements BP-400a-1 and BP-400a-1-i. The building-epics runbook invokes .claude/skills/agent-telemetry/scripts/emit_event.py eight times per epic drive -- supervisor_dispatch, epic_halted, epic_complete -- and that script had never been written. Every call was a silent no-op behind its trailing '|| true', so no drive has ever produced telemetry. This is very likely the real cause of the incident recorded in CLAUDE.md's pre-drive checklist, where 23 submit-failed events went undetected and a retrospective was impossible; that was diagnosed as an unreachable sink, but a script that does not exist produces the same symptom. Adds templates/skills/agent-telemetry/ with SKILL.md and a stdlib-only emit_event.py that appends one JSON line per invocation with the keys the AC specifies (event_type, timestamp, agent_name, ticket_path, payload{phase, outcome, retry_count}), writing absent optionals as null rather than omitting them so every line has the same shape. Per BP-400a-1-i a write failure warns on stderr and still exits 0 -- a drive must not fail because the thing observing it failed. The script imports nothing from the package: it runs from the deployed layout, where a project import would need carrying by the deploy manifest, which is the failure class that has already produced several silent breakages here. Verified end-to-end from a real deploy target, not just the source tree. Also extends scripts/check_skill_refs.py to validate the FILE inside a skill bundle rather than only the bundle directory, since a directory-only check would pass a bundle whose script was never written -- the same defect one level in. build_referential_integrity.py is deliberately left alone: skill-bundled scripts are deployed by build_skills, not the scripts/ manifest, so folding them into that guard would demand manifest entries for correctly-deployed files, which is the false-positive class EPIC-BuildGuardFalsePositive already had to fix once."
breaking: false
---

## Entry
