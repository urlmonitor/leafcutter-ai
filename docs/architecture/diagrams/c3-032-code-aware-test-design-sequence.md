---
title: "Code-Aware Test Design — Sequence Diagram"
description: "L3 sequence diagram from the technical planner's test intent, through the requirement rule check, the deterministic pre-pass, the code-aware test-designer (test design and file findings in one step), the approval-hold report, the hand-back of undecided findings to the planner and the approval gate, to the build where the test writer consumes the design. It shows the test design pending branch at the gate and at the test writer."
type: architecture
flight_level: L3-Component
diagram_type: sequence
status: draft
parent: docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md
created: 2026-10-14
last_updated: 2026-10-22
source_ticket: "tickets/00_inbox/epics/EPIC-RightJobRightAgent/33_TICKET-20261012-ACD-2500c-4.md"
components:
  - ac_driven_dev
  - testing_quality
  - build_orchestration
related_diagrams:
  - docs/architecture/diagrams/c3-033-requirement-part-owners-components.md
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md
  - docs/architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md
  - docs/architecture/diagrams/c3-030-requirement-rule-check-components.md
  - docs/reference/code-aware-step.md
  - docs/reference/requirement-rule-check.md
related_code:
  - templates/workflows-js/plan-feature.js
  - scripts/ac_store/design_prepass.py
  - scripts/ac_store/approval_hold_report.py
  - scripts/ac_store/_approval_holds.py
  - scripts/ac_store/_file_findings.py
  - templates/agents/it-po.md
  - templates/agents/test-designer.md
  - templates/agents/test-writer.md
tags:
  - ac-driven-dev
  - plan-feature
  - test-design
  - file-findings
  - ACD-2500c-4
  - ACD-2500d-4
---

# Code-Aware Test Design — Sequence Diagram

The technical planner (`it-po`) cannot read source (ADR-009), so it records only which
outcomes need a test (`test_intent`). The test design is written later, before approval, by
`test-designer`. That agent may open source and existing tests (ADR-072). This page shows that
path in `/plan-feature` and then into the build, where `test-writer` uses the design. It also
shows where a record with intent but no design stops (ADR-071).

The order follows `templates/workflows-js/plan-feature.js`. The `itpo` stage gate is `auto`,
and one stage is appended: `{agent: "test-designer", stage: "test-design", gate: "final"}`. This
diagram also covers the superseded ACD-2500d-4. The file-aware checks of ACD-2500d (file
findings and the reference-file choice) run in the same `test-designer` dispatch as the test
design. They are not a separate step.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant PF as plan-feature.js
    participant ITPO as it-po (technical planner)
    participant RC as requirement_rule_check.py
    participant PP as design_prepass.py
    participant TD as test-designer
    participant HR as approval_hold_report.py
    participant AA as approve_acs.py
    participant TW as test-writer (build)

    PF->>ITPO: stage itpo (gate auto)
    ITPO-->>PF: records with it_requirements and test_intent (no test_spec)
    PF->>RC: rule-check-itpo --changed-since HEAD
    RC-->>PF: verdict
    Note over PF: auto gate approves and commits the itpo stage, so HEAD is the designer's before-state
    PF->>PP: design-prepass --ids (all ids of the run)
    PP-->>PF: report per record: declared_files state, test_dirs, reference_files
    alt no readable report
        Note over PF,TD: stage fails, test-designer is not dispatched
    else report has no records
        Note over PF: stage passes, nothing to design
    else records to design
        PF->>TD: stage-test-design-author, pre-pass report verbatim
        Note over TD: opens with Read only the files the report names, never searches the repo. Group 1 test design (test_spec, mark, opened files). Group 2 file findings (verdict per declared file, reference-file choice, opened files)
        TD-->>PF: status ok or blocked, per record (routing only, success is judged from disk)
    end
    PF->>RC: rule-check-test-design --before-ref HEAD
    RC-->>PF: verdict (test design grounding, file findings consistency)
    PF->>HR: approval-holds (all ids)
    HR-->>PF: approved ids, held [id, file, reason]
    loop round 1 to 2, while the check passed and a record is held as file finding undecided
        opt round 1
            PF->>PF: commit test-design-handback (the test design, before-state of the hand-back check)
        end
        PF->>ITPO: it-po-findings-round-N (undecided ids)
        ITPO-->>PF: acs_written (decision per finding: reassign, split or assignment stands)
        PF->>RC: rule-check-itpo-handback --stage itpo-handback
        RC-->>PF: verdict
        Note over PF: failed commit or failed check: the run stops before the final gate (fail-closed)
        PF->>HR: approval-holds
        HR-->>PF: held
    end
    PF->>User: final-gate: each approvable record's criteria next to its test_spec, held records listed with reason and no approve option
    Note over PF,User: held reasons, first match wins: test design pending (intent with no design, or a needs_test clause no entry proves), reference file pending (marker), file finding undecided (still undecided after round 2)
    alt rule check not passed
        User->>PF: any answer except cancel becomes edit
        PF->>TD: re-dispatch once with the check summary as feedback
    else approve
        User-->>PF: approve with priority
        PF->>AA: approval-holds: approve_acs.py --ids (all ids) --dry-run --json, right before the write
        AA-->>PF: approved, already_approved, held
        PF->>AA: approval-apply: approve_acs.py --ids (released ids only) --priority p --json
        Note over AA: sets readiness approved. Held records stay reviewed. Skipped when no id is released
        AA-->>PF: approved, already_approved, failed
        alt approval failed
            Note over PF: returns an error before the commit. Nothing is committed
        else approval ok
            PF->>PF: commit plan-feature(TEST-DESIGN, final)
        end
    end
    Note over PF,TW: build: /build-ac takes approved records only
    TW->>TW: reads test_spec, writes one test per entry, named by the entry
    alt record has test_intent and no test_spec
        Note over TW: writes no test, halts with test design pending (status blocker)
    end
```

Parent: [AC Authoring Pipeline — Sequence Diagram](c2-002-ac-authoring-pipeline.md)

See also: [Requirement Part Owners — Component Diagram](c3-033-requirement-part-owners-components.md)
(who writes each field shown here, and who may read source),
[Requirement Rule Check — Component Diagram](c3-030-requirement-rule-check-components.md) (the
check in steps 3, 9 and 16) and [AC-Driven Development](../components/ac-driven-dev.md).

## Steps that need a note

| Step | What happens | Source of truth |
|---|---|---|
| 1 to 4 | The planner writes `test_intent` per outcome clause and never writes `test_spec` or `hold_reason`. Because the `itpo` gate is `auto`, the stage is committed without a pause, so the next rule check can compare against it with `--before-ref HEAD` | `it-po.md` §2.7; `plan-feature.js` pipeline |
| 5 to 6 | `design_prepass.py` reads each record once and only tests whether paths exist. It reads no file contents and writes nothing. Out-of-scope ids (not a leaf, or no intent, declared files or package surface) are skipped silently | `design_prepass.py` |
| alt after 6 | No report means no designer dispatch. A report with no records passes the stage with "nothing to design" | `dispatchTestDesign` |
| 7 to 8 | One dispatch writes both groups to separate fields. The agent's JSON only routes the stage. A `blocked` status fails it | `test-designer.md`; ADR-072 §2 |
| 9 to 10 | The stage check judges the written design and the findings against the tree | `requirement-rule-check.md` |
| 11 to 19 | An undecided finding is an approval hold, not a rule-check failure. Only `it-po` records the decision. A `split` creates records with intent and no design, and they are held as `test design pending`. Before round 1 the test design is committed as `test-design-handback`, so each round's check (`--stage itpo-handback`) compares against it. A failed commit or a failing check stops the run before the gate | `handBackFindings`; `_file_findings.undecided_findings` |
| 20 to 23 | The gate shows the holds from `approval_hold_report.py`. An unreadable report holds every id | `approvalHolds`; `_approval_holds.APPROVAL_HOLD_CHECKS` |
| 24 to 28 | Approval is one deterministic step, `approve_acs.py`. Its `--dry-run` reads the holds again right before the write, because records on disk may change during a pause. The apply gets only the ids it released. A failed run returns before the commit | `approveBatch` |

## When the gate is reached

The gate is always shown. A record is offered for approval only when all of its findings have a
recorded planner decision, it carries a design, and it has no `reference file pending` marker.
A record still undecided after round 2 appears at the gate as held, with its reason. It is never
offered for approval. The hand-back runs only on the live path, after a passing
`rule-check-test-design`. A failed hand-back dispatch ends the loop and leaves the records held.
A failing `itpo-handback` check stops the run before the gate.

## Test design pending in the build

The approval step (`approve_acs.py`) never writes `readiness: approved` on a held record, so `/build-ac` does not
pick it up. If a record with intent and no design reaches the test writer anyway, the test
writer writes no test. It halts with `test design pending`, names the AC id, and reports
`(status: blocker)`.

## Decision history

- 2026-10-22: ACD-300c-4 replaced the `status-checker` edit (`apply-approval`) with
  `approve_acs.py` (`approval-holds` dry run, then `approval-apply`), and the commit runs
  only after a successful approval. ACD-2500a-2-ix added the `test-design-handback` commit
  before hand-back round 1 and the fail-closed `itpo-handback` check after each round.
