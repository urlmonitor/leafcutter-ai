---
title: "EPIC: Completion Manifest Signoff"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
---

# EPIC: Completion Manifest Signoff

Add structured completion manifests (artifact checklists) to the agent signoff system. Every phase agent must output a `completion_manifest:` YAML block in its sign-off comment, explicitly confirming each expected artifact as true/false. This forces agents to self-reflect on each deliverable before declaring success, and gives the supervisor machine-parseable validation data. The checklist is hybrid: each agent defines default items in its frontmatter, tickets can override, and the supervisor validates manifest parity before accepting an `ok` status.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_signoff_skill_manifest_section.md](./01_signoff_skill_manifest_section.md) | Add §2b to signoff skill: completion_manifest format, validation rules, and malformed-manifest retry | `[ ]` |
| 02 | [02_agent_default_checklists.md](./02_agent_default_checklists.md) | Add `default_artifact_checklist` frontmatter to all phase agent templates | `[ ]` |
| 03 | [03_ticket_supervisor_manifest_validation.md](./03_ticket_supervisor_manifest_validation.md) | Add §2.3 manifest validation to ticket-supervisor: parse manifest, cross-reference checklist, reject ok+false parity violations | `[ ]` |
| 04 | [04_ticket_authoring_artifact_checklist.md](./04_ticket_authoring_artifact_checklist.md) | Update ticket-authoring skill to document optional `artifact_checklist:` in ticket frontmatter schema | `[ ]` |
| 05 | [05_building_epics_manifest_step.md](./05_building_epics_manifest_step.md) | Document manifest validation step in building-epics skill supervisor flow | `[ ]` |
