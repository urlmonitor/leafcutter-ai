---
title: "Requirement Part Owners — Component Diagram"
description: "L3 component diagram of who writes which part of a requirement record: criteria (product-owner, business-analyst), routing and contracts, technical requirements, test intent and finding decisions (it-po), test design, file findings and the reference file of a marked record (test-designer), the rule-checked fields (requirement rule check) and the tests (test-writer). It also shows which owners may read source code: only test-designer and test-writer. The rule check and the pre-pass test only that paths exist."
type: architecture
flight_level: L3-Component
diagram_type: component
status: draft
parent: docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md
created: 2026-10-14
last_updated: 2026-10-14
source_ticket: "tickets/00_inbox/epics/EPIC-RightJobRightAgent/34_TICKET-20261012-ACD-2500c-5.md"
components:
  - ac_driven_dev
  - testing_quality
  - build_orchestration
related_diagrams:
  - docs/architecture/diagrams/c3-032-code-aware-test-design-sequence.md
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/adrs/ADR-009-itpo-no-source-code-access.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md
  - docs/architecture/diagrams/c3-030-requirement-rule-check-components.md
  - docs/reference/code-aware-step.md
  - docs/reference/requirement-rule-check.md
related_code:
  - templates/agents/it-po.md
  - templates/agents/test-designer.md
  - templates/agents/test-writer.md
  - scripts/ac_store/requirement_rule_check.py
  - scripts/ac_store/design_prepass.py
  - scripts/ac_store/_rc_edit.py
tags:
  - ac-driven-dev
  - plan-feature
  - test-design
  - source-access
  - ACD-2500c-5
---

# Requirement Part Owners — Component Diagram

A requirement record is written in parts, and each part has one writer. The split follows what
each writer can know. The technical planner cannot read source (ADR-009), so it decides what
needs proof but not how to prove it (ADR-071). The test designer can read source (ADR-072), so
it writes the test design and the file findings. The rule check is deterministic, so it repairs
only fields that have exactly one right answer.

```mermaid
C4Component
    title Requirement part owners — Component Diagram

    Container_Boundary(src_yes, "May read source code") {
        Component(td, "test-designer", "Sonnet agent, pre-approval, ADR-072", "Opens declared files, existing tests and reference candidates with Read, never searches the repo")
        Component(tw, "test-writer", "agent, build time", "Reads test_spec and the code under test")
    }

    Container_Boundary(src_no, "May not read source code") {
        Component(pb, "product-owner and business-analyst", "agents", "Customer value and behaviour")
        Component(itpo, "it-po (technical planner)", "agent, ADR-009", "No source access, architecture docs and registries only")
        Component(rc, "requirement_rule_check.py", "deterministic CLI", "Tests only that paths exist, never reads file contents")
        Component(pp, "design_prepass.py", "deterministic CLI, writes nothing", "Tests only that paths exist, never reads file contents")
    }

    Container_Boundary(rec, "Requirement record - AC YAML") {
        ComponentDb(crit, "Criteria", "criteria", "Gherkin outcome clauses")
        ComponentDb(route, "Routing and contracts", "assigned_agent, delivers_to, expects_from", "")
        ComponentDb(tech, "Technical requirements", "it_requirements, declared_files", "")
        ComponentDb(intent, "Test intent and finding decisions", "test_intent or test_required, file_findings[].decision", "")
        ComponentDb(design, "Test design", "test_spec, test_design_authorship, test_design_opened_files", "")
        ComponentDb(find, "File findings and reference file", "file_findings verdicts, file_findings_opened_files, reference_file_path of a marked record", "Clears hold_reason reference file pending")
        ComponentDb(rcf, "Rule-checked fields", "covered_by, components, readiness", "Repaired only when one right answer exists")
    }

    ComponentDb(repo, "Repository tree", "source and test files", "")

    Rel(pb, crit, "writes")
    Rel(itpo, route, "writes")
    Rel(itpo, tech, "writes")
    Rel(itpo, intent, "writes")
    Rel(td, design, "writes")
    Rel(td, find, "writes")
    Rel(rc, rcf, "repairs through _rc_edit")
    Rel(pp, td, "pre-pass report, embedded in the prompt")
    Rel(td, repo, "opens and reads files")
    Rel(tw, design, "reads")
    Rel(tw, repo, "reads source, writes tests")
    Rel(rc, repo, "path exists, no read")
    Rel(pp, repo, "path exists, no read")

    UpdateElementStyle(td, $bgColor="#2e7d32", $borderColor="#1b5e20")
    UpdateElementStyle(tw, $bgColor="#2e7d32", $borderColor="#1b5e20")
    UpdateElementStyle(itpo, $bgColor="#8d6e63", $borderColor="#5d4037")
    UpdateElementStyle(rc, $bgColor="#8d6e63", $borderColor="#5d4037")
    UpdateElementStyle(pp, $bgColor="#8d6e63", $borderColor="#5d4037")
```

Parent: [AC Authoring Pipeline — Sequence Diagram](c2-002-ac-authoring-pipeline.md)

See also: [Code-Aware Test Design — Sequence Diagram](c3-032-code-aware-test-design-sequence.md)
(the order in which these writers run) and [AC-Driven Development](../components/ac-driven-dev.md).

## One writer per part

| Part | Fields | Writer | Every other owner |
|---|---|---|---|
| Criteria | `criteria` | product-owner, business-analyst | Reads only |
| Routing and contracts | `assigned_agent`, `delivers_to`, `expects_from` | it-po | test-designer must leave them unchanged (ADR-072 §2) |
| Technical requirements | `it_requirements`, `declared_files` | it-po | test-designer writes only the `reference_file_path` key, and only on a marked record |
| Test intent | `test_intent` or `test_required: false` | it-po | test-designer never edits it, not even an all-false intent |
| Test design | `test_spec`, `test_design_authorship`, `test_design_opened_files` | test-designer | it-po never writes `test_spec`. test-writer reads it only |
| File findings | `file_findings` (all keys except `decision`), `file_findings_opened_files` | test-designer | it-po writes only `decision` and never edits a verdict, reason, line range or `found_in` |
| Finding decisions | `file_findings[].decision` (`choice`, `reason`, `by: it-po`) | it-po | Written in the hand-back rounds of `/plan-feature` |
| Reference file | `it_requirements.reference_file_path` on a record marked `hold_reason: reference file pending` | test-designer | Chosen only from pre-pass candidates. The marker is cleared after the path is filled |
| Rule-checked fields | `covered_by`, `components`, `readiness` | requirement rule check | `_rc_edit` refuses any other field. Every authoring agent's `readiness: approved` is restored |
| Tests | test files in the repository | test-writer | Not a record field |

`design_prepass.py` writes nothing. It only gives the test designer its file facts.

## Who may read source code

Green owners may read source code. Brown owners may not.

- **test-designer** may open source, existing tests and reference candidates, but only with
  Read and only the files the pre-pass report and the record name. It may not use `find`,
  `grep -r`, `rg` or `git grep`. ADR-072 allows this single pre-approval agent.
- **test-writer** reads the code under test at build time and writes the tests.
- **it-po** may not read source (ADR-009). It works from architecture docs and registries.
  When a duty needs the code, it is left to the test designer.
- **requirement rule check** and **design pre-pass** are deterministic scripts. They test only
  that a path exists, and the pre-pass also lists the file names in a directory. Neither ever
  reads file contents. Both read requirement records and their own config.
- **product-owner** and **business-analyst** write customer-language criteria and do not read
  source.

## Note on the reference-file marker

The marker `hold_reason: reference file pending` is cleared by the test designer. Today no
built agent sets it. `it-po.md` says it never sets `hold_reason`, and the planner's side of
the marker is not in this group.
