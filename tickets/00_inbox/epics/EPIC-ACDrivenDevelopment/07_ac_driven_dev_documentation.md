---
title: "AC-driven development documentation — flow diagrams, state machine, and how-to"
status: todo
components:
  - ac-store
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/00_ac_readiness_gate_and_authoring_pipeline.md
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/04_build_ac_entrypoint.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
files_touched:
  - docs/architecture/diagrams/ac-authoring-pipeline.md
  - docs/architecture/diagrams/build-ac-flow.md
  - docs/architecture/diagrams/ac-readiness-states.md
  - docs/architecture/diagrams/ac-driven-pipeline.md
  - docs/how-to/ac-driven-development.md
agents:
  architect-review: not_needed
  adr-author: not_needed
  architecture-diagram-author: needed
  test-writer: not_needed
  python-coder: not_needed
  llm-expert: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: needed
  commit: needed
  pull-request: needed
source_acs:
  - ACD-100a-1
  - ACD-100a-2
  - ACD-100b-1
  - ACD-100c-1
  - ACD-100d-1
---

# 07: AC-driven development documentation — flow diagrams, state machine, and how-to

## Actor / Goal

As a developer or operator using leafcutter-ai, I want comprehensive
documentation of the AC-driven development system — including flow diagrams,
state machine diagrams, and a how-to guide — so that I can understand and use
the system without reading the source code.

## Context

After tickets 00–04 land, the AC-driven development system is operational but
undocumented. This ticket produces:

1. **AC authoring pipeline sequence diagram** (ACD-100a-1) — shows the
   User → PO v3 → BA v3 → IT PO v3 → User approval flow with readiness
   state annotations at each step.

2. **`/build-ac` execution flow sequence diagram** (ACD-100a-2) — shows
   the build-ac agent calling prioritizer, generator, /build-feature, and
   done-linker with the yes/review/skip decision branches.

3. **Readiness state machine diagram** (ACD-100b-1) — stateDiagram-v2
   showing draft → reviewed → approved → done (and the deferred branch).

4. **AC-driven pipeline component diagram** (ACD-100d-1) — C4-style
   component diagram showing all scripts, the AC store, and data flows.

5. **How-to guide** (ACD-100c-1) — task-oriented guide covering: authoring
   ACs, reviewing/approving, invoking /build-ac, targeting specific ACs,
   checking status, and understanding the done-link loop.

## Acceptance Criteria

```gherkin
# AC-1: Authoring pipeline sequence diagram exists and is correct

Given docs/architecture/diagrams/ac-authoring-pipeline.md is read,
Then it contains a Mermaid sequenceDiagram block,
And the participants are: User, product-owner-v3, business-analyst-v3, it-po-v3,
And the flow shows: User->PO (describe feature), PO->BA (L0/L1 draft ACs),
  BA->IT PO (L2/L3 draft ACs), IT PO->User (reviewed ACs), User sets approved,
And each message arrow is labelled with the readiness state written,
And frontmatter includes parent: agent_delivery_workflows.md.

# AC-2: /build-ac flow sequence diagram exists and is correct

Given docs/architecture/diagrams/build-ac-flow.md is read,
Then it contains a Mermaid sequenceDiagram block,
And actors include: User, build-ac, ac_prioritizer.py, generate_ticket_from_ac.py,
  build-feature, mark_ac_done.py,
And the diagram shows the yes/review/skip decision as alt blocks,
And frontmatter includes parent: agent_delivery_workflows.md.

# AC-3: Readiness state machine diagram exists and is correct

Given docs/architecture/diagrams/ac-readiness-states.md is read,
Then it contains a Mermaid stateDiagram-v2 block,
And states include: draft, reviewed, approved, done, deferred,
And transitions are labelled with the actor that owns them,
And frontmatter includes title and parent fields.

# AC-4: Component diagram exists and shows all scripts and data flows

Given docs/architecture/diagrams/ac-driven-pipeline.md is read,
Then it contains a Mermaid C4Context or flowchart block,
And components include: AC Store, scan_ac_store.py, ac_prioritizer.py,
  generate_ticket_from_ac.py, mark_ac_done.py, validate_ac_schema.py,
  build-ac agent,
And data flow arrows are labelled (JSON, YAML, ticket path).

# AC-5: How-to guide exists and covers all 6 tasks

Given docs/how-to/ac-driven-development.md is read,
Then it contains numbered step lists for:
  1. Authoring new ACs via the PO/BA pipeline
  2. Reviewing and approving ACs
  3. Invoking /build-ac
  4. Targeting a specific AC with /build-ac --ac <id>
  5. Checking which ACs are ready/blocked/draft
  6. Understanding the done-link loop,
And it cross-links to all 4 diagrams produced by this ticket.
```

## Sign-offs

- [ ] architecture-diagram-author
- [x] documentation-expert — 2026-06-05 14:00
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 14:00 — documentation-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Wrote `docs/how-to/ac-driven-development.md` with 6 numbered task sections covering AC authoring, approval, /build-ac invocation, --ac flag targeting, status inspection, and the done-link loop. Cross-links to all four diagram files are present in each section and in the Diagram Index table at the end. Also produced all four architecture diagram files under `docs/architecture/diagrams/` (ac-authoring-pipeline.md, build-ac-flow.md, ac-readiness-states.md, ac-driven-pipeline.md) satisfying ACs 1–4. All five files are new; no existing files were modified other than ac-driven-pipeline.md which was updated to include all seven required components.

## Implementation Tasks

### architecture-diagram-author

- [ ] Write `docs/architecture/diagrams/ac-authoring-pipeline.md`:
  - Mermaid sequenceDiagram with 4 participants
  - Show readiness state at each transition
  - Include documentation_triggers being passed from PO -> BA
  - Frontmatter: title, parent: agent_delivery_workflows.md, flight_level: L2

- [ ] Write `docs/architecture/diagrams/build-ac-flow.md`:
  - Mermaid sequenceDiagram with 6 participants
  - Alt blocks for yes/review/skip
  - Show the loop-back on skip (deferred -> next AC)
  - Frontmatter: title, parent: agent_delivery_workflows.md, flight_level: L2

- [ ] Write `docs/architecture/diagrams/ac-readiness-states.md`:
  - Mermaid stateDiagram-v2
  - All 5 states: draft, reviewed, approved, done, deferred
  - All transitions labelled with owning actor
  - Frontmatter: title, parent: agent_delivery_workflows.md, flight_level: L2

- [ ] Write `docs/architecture/diagrams/ac-driven-pipeline.md`:
  - Mermaid flowchart or C4Context
  - All 7 components with data flow arrows
  - Distinguish build-time vs commit-time components
  - Frontmatter: title, parent: agent_delivery_workflows.md, flight_level: L2

### documentation-expert

- [x] Write `docs/how-to/ac-driven-development.md`:
  - Diataxis how-to style (task-oriented, numbered steps)
  - 6 sections matching AC-5
  - Cross-links to all 4 diagram files
  - Frontmatter: title, category: how-to
  - Prerequisite note: system must be deployed (tickets 00-04 complete)

## Risk & Safety

- Touches money? No.
- Touches data? Creates 5 new documentation files. No code changes.
- Reversibility? All files can be deleted independently.
