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
| 02_01 | [02_01_checklist_architect_review.md](./02_01_checklist_architect_review.md) | Add `default_artifact_checklist` to architect-review | `[ ]` |
| 02_02 | [02_02_checklist_python_coder.md](./02_02_checklist_python_coder.md) | Add `default_artifact_checklist` to python-coder | `[ ]` |
| 02_03 | [02_03_checklist_test_writer.md](./02_03_checklist_test_writer.md) | Add `default_artifact_checklist` to test-writer | `[ ]` |
| 02_04 | [02_04_checklist_test_runner.md](./02_04_checklist_test_runner.md) | Add `default_artifact_checklist` to test-runner | `[ ]` |
| 02_05 | [02_05_checklist_documentation_expert.md](./02_05_checklist_documentation_expert.md) | Add `default_artifact_checklist` to documentation-expert | `[ ]` |
| 02_06 | [02_06_checklist_change_scope_reviewer.md](./02_06_checklist_change_scope_reviewer.md) | Add `default_artifact_checklist` to change-scope-reviewer | `[ ]` |
| 02_07 | [02_07_checklist_pr_reviewer.md](./02_07_checklist_pr_reviewer.md) | Add `default_artifact_checklist` to pr-reviewer | `[ ]` |
| 02_08 | [02_08_checklist_commit.md](./02_08_checklist_commit.md) | Add `default_artifact_checklist` to commit | `[ ]` |
| 02_09 | [02_09_checklist_pull_request.md](./02_09_checklist_pull_request.md) | Add `default_artifact_checklist` to pull-request | `[ ]` |
| 02_10 | [02_10_checklist_status_checker.md](./02_10_checklist_status_checker.md) | Add `default_artifact_checklist` to status-checker | `[ ]` |
| 02_11 | [02_11_checklist_sql_coder.md](./02_11_checklist_sql_coder.md) | Add `default_artifact_checklist` to sql-coder | `[ ]` |
| 02_12 | [02_12_checklist_frontend_coder.md](./02_12_checklist_frontend_coder.md) | Add `default_artifact_checklist` to frontend-coder | `[ ]` |
| 02_13 | [02_13_checklist_sql_query.md](./02_13_checklist_sql_query.md) | Add `default_artifact_checklist` to sql-query | `[ ]` |
| 02_14 | [02_14_checklist_adr_author.md](./02_14_checklist_adr_author.md) | Add `default_artifact_checklist` to adr-author | `[ ]` |
| 02_15 | [02_15_checklist_architecture_diagram_author.md](./02_15_checklist_architecture_diagram_author.md) | Add `default_artifact_checklist` to architecture-diagram-author | `[ ]` |
| 02_16 | [02_16_checklist_explanation_author.md](./02_16_checklist_explanation_author.md) | Add `default_artifact_checklist` to explanation-author | `[ ]` |
| 02_17 | [02_17_checklist_how_to_author.md](./02_17_checklist_how_to_author.md) | Add `default_artifact_checklist` to how-to-author | `[ ]` |
| 02_18 | [02_18_checklist_reference_author.md](./02_18_checklist_reference_author.md) | Add `default_artifact_checklist` to reference-author | `[ ]` |
| 02_19 | [02_19_checklist_user_surface_smoker.md](./02_19_checklist_user_surface_smoker.md) | Add `default_artifact_checklist` to user-surface-smoker | `[ ]` |
| 03 | [03_ticket_supervisor_manifest_validation.md](./03_ticket_supervisor_manifest_validation.md) | Add §2.3 manifest validation to ticket-supervisor: parse manifest, cross-reference checklist, reject ok+false parity violations | `[ ]` |
| 04 | [04_ticket_authoring_artifact_checklist.md](./04_ticket_authoring_artifact_checklist.md) | Update ticket-authoring skill to document optional `artifact_checklist:` in ticket frontmatter schema | `[ ]` |
| 05 | [05_building_epics_manifest_step.md](./05_building_epics_manifest_step.md) | Document manifest validation step in building-epics skill supervisor flow | `[ ]` |

## Dependency Graph

```
01 (signoff §2b format spec)
├── 02_01..02_19 (all 19 per-agent checklists, parallel — each depends only on 01)
├── 04 (ticket-authoring schema update — depends only on 01)
│
├── 03 (ticket-supervisor validation — depends on 01 + all 02_XX)
│   └── 05 (building-epics documentation — depends on 03)
```

## Notes

- All 19 phase agents derived from `config/agent_registry.json` (`is_ticket_phase: true`)
- Tickets 02_01–02_19 are fully parallel after ticket 01 completes
- Ticket 03 cannot start until all agent templates have their checklists (needs to know what to validate)
- Ticket 04 is independent of the per-agent work (only references format from 01)
