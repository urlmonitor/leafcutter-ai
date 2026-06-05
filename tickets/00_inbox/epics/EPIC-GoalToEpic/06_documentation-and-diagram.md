---
title: "Documentation and sequence diagram for ACD-1200 goal-to-epic features"
status: in_progress
components:
  - ac-driven-dev
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/02_readiness-gate.md
  - tickets/00_inbox/epics/EPIC-GoalToEpic/05_goal-detection-mode-switch.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
target_epic: EPIC-GoalToEpic
files_touched:
  - docs/how-to/goal-to-epic.md
  - docs/how-to/approval-gate.md
  - docs/how-to/build-ac-unified.md
  - docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md
agents:
  test-writer: skip
  documentation-expert: signed_off
  architecture-diagram-author: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
ac_coverage: 0/4
source_ac: ACD-1200a
---

# 06: Documentation and sequence diagram for ACD-1200 goal-to-epic features

## Actor / Goal

In order to let developers use the goal-to-epic feature correctly the first
time and understand the approval gate choices and the unified command behavior,
three how-to guides and one sequence diagram must be produced that document
the ACD-1200 feature family.

## Context

This ticket documents the completed behaviors from tickets 01, 02, and 05. It
runs last because the guides document implemented (not aspirational) behavior.

The four deliverables are independent and can be parallelized:
- `documentation-expert` produces the three how-to guides (any order).
- `architecture-diagram-author` produces the sequence diagram independently.

## AC References

- Implements ACD-1200a-4 (how-to guide for goal-to-epic workflow)
- Implements ACD-1200a-5 (sequence diagram of dispatch flow)
- Implements ACD-1200b-3 (how-to guide for approval gate)
- Implements ACD-1200e-3 (how-to guide for unified /build-ac leaf-vs-goal behavior)

## Agent Contracts

### documentation-expert

- [x] AC-1: A how-to guide at `docs/how-to/goal-to-epic.md` documents: how to invoke `/build-ac` with an L0 or L1 AC ID; what output to expect (epic folder name, ticket count, approval gate prompt); how the generated epic folder maps to `/build-feature` usage; cross-references the ACD-1200 feature family by ID; and follows the project's existing how-to guide format and conventions. <!-- signed: documentation-expert -->
- [x] AC-2: A how-to guide at `docs/how-to/approval-gate.md` documents: what the readiness report looks like and what readiness values mean; how to choose between "proceed with approved only" and "review-all"; what happens when IT PO v3 is dispatched for bulk review; how to cancel and return later; cross-references ACD-1200b by ID; follows existing how-to format. <!-- signed: documentation-expert -->
- [x] AC-3: A how-to guide at `docs/how-to/build-ac-unified.md` documents: the single entry point `/build-ac --ac <ID>`; how the system auto-detects leaf vs goal; what happens for a leaf target (single-ticket, ACD-700a behavior); what happens for a goal target (epic-generation mode); the L1-with-no-children edge case and remedial action; cross-references ACD-1200e by ID; references `docs/how-to/ac-driven-development.md` to avoid duplication; follows existing how-to format. <!-- signed: documentation-expert -->

**Delivers to:** User-facing documentation surface (`docs/how-to/`).

**Depends on ticket 01:** implemented goal-to-epic workflow to document.
**Depends on ticket 02:** implemented approval gate workflow to document.
**Depends on ticket 05:** implemented unified leaf/goal detection to document.

### architecture-diagram-author

- [x] AC-4: A sequence diagram at `docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md` uses Mermaid `sequenceDiagram` syntax consistent with existing diagrams in `docs/architecture/diagrams/`, shows the interaction between: user invoking `/build-ac` with a goal AC ID; the tree traversal step collecting leaf ACs; the readiness gate checking approval status; the ticket generation loop (one per leaf AC); the target_epic stamping step; and the epic folder assembly. The file includes frontmatter with `type`, `status`, `components`, and `related_docs` fields following project C4/architecture diagram conventions. <!-- signed: architecture-diagram-author -->

**Delivers to:** Architecture documentation surface (`docs/architecture/diagrams/`).

**Depends on ticket 01:** implemented goal-to-epic workflow to diagram.

## Acceptance Criteria

- [x] AC-1: `docs/how-to/goal-to-epic.md` exists, covers invocation/output/approval/folder mapping, cross-refs ACD-1200, follows existing how-to format
- [x] AC-2: `docs/how-to/approval-gate.md` exists, covers readiness report/choice options/IT PO dispatch/cancel path, cross-refs ACD-1200b, follows existing how-to format
- [x] AC-3: `docs/how-to/build-ac-unified.md` exists, covers auto-detection/leaf path/goal path/L1-no-children edge case, cross-refs ACD-1200e, references ac-driven-development.md, follows existing how-to format
- [x] AC-4: `docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md` exists, Mermaid sequenceDiagram, shows all 6 interaction steps, includes required frontmatter, consistent with existing diagrams

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| ACD-1200a-4 | | Created docs/how-to/goal-to-epic.md | ok — 2026-06-06 |
| ACD-1200a-5 | | Created docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md | ok — 2026-06-06 |
| ACD-1200b-3 | | Created docs/how-to/approval-gate.md | ok — 2026-06-06 |
| ACD-1200e-3 | | Created docs/how-to/build-ac-unified.md | ok — 2026-06-06 |

## Implementation Tasks

### documentation-expert tasks

- [x] Read `docs/how-to/` for an existing guide to establish format conventions
- [x] Write `docs/how-to/goal-to-epic.md` (ACD-1200a-4)
- [x] Write `docs/how-to/approval-gate.md` (ACD-1200b-3)
- [x] Write `docs/how-to/build-ac-unified.md` (ACD-1200e-3)
      — include cross-reference to `docs/how-to/ac-driven-development.md`

### architecture-diagram-author tasks

- [x] Read existing diagrams in `docs/architecture/diagrams/` to establish
      Mermaid syntax and frontmatter conventions
- [x] Write `docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md`:
      ```
      sequenceDiagram
        User->>build-ac: /build-ac --ac ACD-050
        build-ac->>scan_ac_store: traverse_ac_tree(ACD-050)
        scan_ac_store-->>build-ac: [ACD-050a-1, ACD-050a-2-i, ACD-050b-1]
        build-ac->>goal_to_epic: classify_readiness(leaf_ids)
        goal_to_epic-->>build-ac: {approved: [...], unapproved: [...]}
        build-ac->>User: readiness report + prompt
        User-->>build-ac: yes / review-all / cancel
        build-ac->>goal_to_epic: generate_tickets(included_ids)
        goal_to_epic->>generate_ticket_from_ac: --ac <id> (x N)
        generate_ticket_from_ac-->>goal_to_epic: ticket_paths
        goal_to_epic->>goal_to_epic: resolve_dependencies + toposort
        goal_to_epic->>goal_to_epic: assemble_epic_folder(EPIC-ValidateApiInputs)
        goal_to_epic->>goal_to_epic: stamp_target_epic(included_ids)
        goal_to_epic-->>build-ac: EPIC folder path
        build-ac-->>User: "Epic ready: tickets/00_inbox/epics/EPIC-ValidateApiInputs/"
      ```
      _(Adjust based on actual implemented call sequence after tickets 01–05 land.)_

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only. How-to guides are new files; the
  sequence diagram is a new file. No existing files are modified.
- Reversibility? High — delete the four files to revert.

## Sign-offs

- [x] documentation-expert — 2026-06-06 14:00
- [x] architecture-diagram-author — 2026-06-06 14:00
- [x] pr-reviewer — 2026-06-06 14:10
- [x] commit — 2026-06-06 14:30
- [ ] pull-request

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-06 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-05_eb6b2689
completion_manifest:
  goal_to_epic_guide_created: true
  approval_gate_guide_created: true
  build_ac_unified_guide_created: true
  cross_references_included: true
  existing_format_followed: true
Created three how-to guides: docs/how-to/goal-to-epic.md (ACD-1200a-4), docs/how-to/approval-gate.md (ACD-1200b-3), docs/how-to/build-ac-unified.md (ACD-1200e-3). All guides follow existing how-to format conventions, cross-reference ACD-1200 family by ID, and reference ac-driven-development.md to avoid duplication.

### 2026-06-06 14:00 — architecture-diagram-author (status: ok)
feedback-id: fb_2026-06-05_458fe2a2
completion_manifest:
  diagram_created: true
  flight_level_correct: true
  cross_links_added: true
Created docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md with Mermaid sequenceDiagram showing all interaction steps: mode detection, tree traversal, readiness gate, ticket generation loop, dependency wiring, EPIC folder assembly, and target_epic stamping. Frontmatter includes type, status, components, and related_docs following existing diagram conventions.

### 2026-06-06 14:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_e27b6332
completion_manifest:
  high_confidence_findings: true
  contract_validation_pass: true
  ac_coverage_table_filled: true

Review Report
Base: HEAD
Diff size: 4 new files (docs/how-to/goal-to-epic.md, docs/how-to/approval-gate.md, docs/how-to/build-ac-unified.md, docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md)

High-Confidence Findings: No high-confidence findings.

Suppressed: 0 low-confidence nits, 0 medium findings dropped.

Escalation
Branch: none
Reason: not escalated — no medium findings (threshold > 3).

All four ACs satisfied: goal-to-epic.md covers invocation/output/approval/folder mapping; approval-gate.md covers readiness report, choice options, IT PO dispatch, and cancel path; build-ac-unified.md covers auto-detection, leaf/goal paths, L1-no-children edge case, and references ac-driven-development.md; c2-005-goal-to-epic-dispatch.md uses Mermaid sequenceDiagram with all required interaction steps and correct frontmatter.

### 2026-06-06 14:30 — commit (status: ok)
feedback-id: fb_2026-06-05_e5746ec0
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Staged 5 files (4 new docs + ticket sign-off). Renamed diagram from seq-goal-to-epic-dispatch.md to c2-005-goal-to-epic-dispatch.md to satisfy check-diagram-naming pre-commit hook. All references updated.
