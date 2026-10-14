---
title: "Requirement Rule Check — Component Diagram"
description: "L3 component diagram of the requirement rule check: the /plan-feature authoring stages that run it, the CLI and its rule families (which repair and which only report), the one writer, the rule source, the surface-to-specialist map and the existing store record check it calls. A failed check keeps the stage from being reported complete."
type: architecture
flight_level: L3-Component
diagram_type: component
status: draft
parent: docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md
created: 2026-10-14
last_updated: 2026-10-14
source_ticket: "tickets/00_inbox/epics/EPIC-RightJobRightAgent/18_TICKET-20261012-ACD-2500a-4.md"
components:
  - ac_driven_dev
  - ac_store
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/reference/requirement-rule-check.md
  - docs/reference/ac-schema.md
  - docs/architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md
related_code:
  - scripts/ac_store/requirement_rule_check.py
  - scripts/ac_store/_rc_report.py
  - scripts/ac_store/_rc_records.py
  - scripts/ac_store/_rc_changed.py
  - scripts/ac_store/_rc_record_schema.py
  - scripts/ac_store/_rc_edit.py
  - scripts/ac_store/_rc_backlinks.py
  - scripts/ac_store/_rc_components.py
  - scripts/ac_store/_rc_readiness.py
  - scripts/ac_store/_rc_contracts.py
  - scripts/ac_store/_rc_doc_triggers.py
  - scripts/ac_store/_rc_declared.py
  - scripts/ac_store/validate_ac_schema.py
  - scripts/ac_store/assignment_quality.py
  - templates/workflows-js/plan-feature.js
tags:
  - ac-driven-dev
  - ac-store
  - plan-feature
  - requirement-rule-check
  - ACD-2500a
---

# Requirement Rule Check — Component Diagram

The requirement rule check decides whether a `/plan-feature` authoring stage is complete. The
stage agent's own report does not decide it. A script checks the records the stage changed,
repairs the three faults that have exactly one right answer, and prints one JSON report. The
workflow reads that report and the exit status, never prose (ACD-2500a-1 to ACD-2500a-3).

This page shows the parts and what each one reads. Flags, report fields and dispositions are
listed in the [requirement rule check reference](../../reference/requirement-rule-check.md).

```mermaid
C4Component
    title Requirement rule check — Component Diagram

    Container_Boundary(pf, "plan-feature.js workflow") {
        Component(stages, "Authoring stage loop", "JS, for step of pipeline", "po, ba and itpo stages: author dispatch, then the after_po, after_ba or final gate")
        Component(rrc, "runRuleCheck", "JS helper", "Builds the command; reads exit_code and the JSON report fail-closed")
        Component(commit, "commitStageOutput", "JS, commit agent", "Commits the stage's records plus records_to_commit")
    }
    Component_Ext(wta, "worktree-agent", "shell-permitted agent", "Runs the command; relays stdout and exit code")

    Container_Boundary(chk, "Requirement rule check - scripts/ac_store") {
        Component(cli, "requirement_rule_check.py", "Python CLI", "FAMILIES registry; pass 1, repairs, reload, pass 2; exit 0 passed, 1 failed")
        Component(load, "_rc_records and _rc_changed", "Python", "Loads the checked records, the store id index and the readiness before-state")
        Component(repair, "Repairing families - REPAIRS", "_rc_backlinks, _rc_components, _rc_readiness", "Back-link, component list, readiness; needs a decision when no single right answer")
        Component(report, "Report-only families - REPORT ONLY", "_rc_record_schema, _rc_contracts, _rc_doc_triggers, _rc_declared", "needs a decision, failed or not evaluated; never write")
        Component(edit, "_rc_edit", "Python, the only writer", "Edits one of covered_by, components, readiness; proves every other field unchanged")
        Component(rep, "_rc_report", "Python", "Dedupe, sort, verdict, family_counts; one JSON document on stdout")
    }

    Container_Boundary(src, "Existing store checks and rule sources - read only") {
        Component(vas, "validate_ac_schema.py", "existing store record check", "_validate_file per record, load_ac_store_schema")
        ComponentDb(rules, "Rule source", "JSON and Python", "config/ac_store_schema.json, docs/components.json, MIGRATION_MAP")
        ComponentDb(smap, "Surface-to-specialist map", "config/surface_craft_map.yaml", "Read through assignment_quality.resolve_craft_in")
        Component(seams, "Store seams", "declared_files.py, ac_parent_id.py", "get_declared_files, derive_parent_id")
    }
    ComponentDb(recs, "Requirement records", "docs/acceptance-criteria/**/*.yaml", "Records the stage changed, and their parents")
    System_Ext(git, "git", "", "diff and ls-files for --changed-since; cat-file for --before-ref")

    Rel(stages, rrc, "1. after the author writes; at the gate on resume")
    Rel(rrc, wta, "2. rule-check-STAGE: --changed-since HEAD --before-ref HEAD")
    Rel(wta, cli, "3. runs")
    Rel(cli, load, "4. load scope")
    Rel(load, git, "5. changed files, readiness at HEAD")
    Rel(load, recs, "reads")
    Rel(cli, rules, "loads; unreadable is failed")
    Rel(cli, repair, "6. evaluate_record, both passes")
    Rel(cli, report, "6. evaluate_record, both passes")
    Rel(report, vas, "calls _validate_file; one finding per subject")
    Rel(vas, rules, "reads")
    Rel(report, smap, "specialist versus surface")
    Rel(report, seams, "get_declared_files")
    Rel(repair, seams, "derive_parent_id")
    Rel(cli, edit, "7. applies each pass-1 repair")
    Rel(edit, recs, "atomic replace of one field")
    Rel(cli, rep, "8. findings of both passes")
    Rel(rep, wta, "9. JSON report and exit code")
    Rel(rrc, stages, "10. not passed: approve or defer becomes edit; retries used up: status error with failed_check")
    Rel(stages, commit, "11. only when passed: written ids plus records_to_commit")

    UpdateElementStyle(repair, $bgColor="#2e7d32", $borderColor="#1b5e20")
    UpdateElementStyle(report, $bgColor="#8d6e63", $borderColor="#5d4037")
    UpdateRelStyle(rrc, stages, $textColor="#c62828", $lineColor="#c62828")```

Parent: [AC Authoring Pipeline — Sequence Diagram](c2-002-ac-authoring-pipeline.md)

See also: [AC-Driven Development](../components/ac-driven-dev.md) (the component this check
belongs to) and [Plan-Feature Decision Gates](c3-008-plan-feature-decision-gate-sequence.md)
(the gates that act on the verdict).

## Rule families: which repair and which only report

Green in the diagram is the repairing node and brown is the report-only node. The names are the
`rule_family` strings in `_rc_report.py`, in `FAMILIES` order.

| Family | Module | What it does |
|---|---|---|
| record schema | `_rc_record_schema.py` | **Report only.** Calls the store's existing record check and keeps one finding per field |
| parent-to-child back-links | `_rc_backlinks.py` | **Repairs.** Appends the child id to the parent's `covered_by`. A parent missing from the checked records is `needs a decision` |
| non-empty graph component list | `_rc_components.py` | **Repairs** an empty `components` when `MIGRATION_MAP` gives exactly one registered id. Zero or several candidates, or a wrong non-empty list, is `needs a decision` |
| readiness never raised to approved by an authoring agent | `_rc_readiness.py` | **Repairs.** Restores `readiness` to its value at the before-ref (`draft` for a new record). Skipped for `--stage approval` |
| producer/consumer contract symmetry | `_rc_contracts.py` | **Report only** |
| documentation trigger to documentation requirement mapping | `_rc_doc_triggers.py` | **Report only.** L1 records only. An unmapped trigger is `failed` |
| specialist versus surface | `_rc_declared.py` | **Report only.** Uses the surface-to-specialist map. An unmapped path, or a record with no declared files, is `not evaluated` |
| declared files versus modifies links | `_rc_declared.py` | **Report only** |

A family never writes. A repairing family attaches `repair=(field, how)` to a `fixed` finding.
`requirement_rule_check.py` hands that repair to `_rc_edit`. `_rc_edit` refuses any field
outside `covered_by`, `components` and `readiness`. It also refuses an edit that changes
anything else in the record. A refused repair becomes a `failed` finding. One more name, `record
readable`, is not in `FAMILIES`: `_rc_records` reports it when a record file cannot be read.

## What the check reads

| Node | Read by | Notes |
|---|---|---|
| Rule source | the CLI, and the store record check | `config/ac_store_schema.json` (`--schema`), `docs/components.json` (`--components-registry`, passed explicitly because the deployed default has no registry), `_component_migration_map.MIGRATION_MAP` (`--migration-map`). An unreadable or empty source is `failed` |
| Surface-to-specialist map | the specialist-versus-surface family | `config/surface_craft_map.yaml` (`--surface-map`), read only through `assignment_quality`. The check holds no file-type table of its own |
| validate_ac_schema.py | the record-schema adapter; the components family reads its `components` messages | Called, not changed. The check extends this record check; it does not copy it |
| Store seams | the declared-files families; the back-link family | `declared_files.get_declared_files`, `ac_parent_id.derive_parent_id` |
| git | `_rc_changed`, `_rc_records` | `--changed-since HEAD` picks the records the stage changed. `--before-ref HEAD` gives the readiness before-state. A git failure is `failed` |

The rule source and the surface map are one node each. The check keeps no copy of either. The
trigger-to-specialist table is the exception. It is `TRIGGER_SPECIALISTS` inside
`_rc_doc_triggers.py`, not a config file (see that module's decision history).

## A failed check keeps the stage open

The verdict is `passed` only when at least one record was checked and pass 2 has no `needs a
decision` or `failed` finding. `runRuleCheck` treats the stage as passed only when the exit
code is 0, the report says `passed` and `records_checked` is above 0. Any other result counts
as not passed, including an unreadable reply or an exit code that disagrees with the report.

When the check has not passed, both gates turn **approve** and **defer** into **edit** (step 10).
The check's summary goes to the author as feedback and the stage runs again. When the edit
retries are used up, the workflow returns `status: "error"` with the report as `failed_check`.
`commitStageOutput` is never reached and the next stage never starts. **Cancel** still cancels.
Only a passed check reaches step 11. That commit includes `records_to_commit`, so a parent
repaired by the back-link family is committed too.

The CLI also accepts `--stage test-design`, but the workflow has no test-design stage yet.
