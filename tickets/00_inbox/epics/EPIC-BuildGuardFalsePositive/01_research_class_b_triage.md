---
title: "Research & triage: per-script deploy decisions for all 12 Class B scripts"
status: todo
components:
  - build_pipeline
  - bootstrap_installer
created: 2026-06-17
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Research & Triage — Class B Script Deploy Decisions

## Goal

In order to fix the build guard false positive correctly, we need a per-script
deploy decision for each of the 12 Class B scripts so that tickets 02 and 03
implement the right fix without allowlisting scripts that should be deployed to
consumers.

## Context

`_check_script_reference_guard()` in `scripts/build.py` flags 12 scripts as
"referenced by templates but not deployed by any build phase." These are Class B
references. Simply adding them to `EXTERNAL_DEPENDENCY_ALLOWLIST` would silence the
guard while the consumer install remains broken — the exact failure mode BP-900 exists
to prevent.

Each script needs an explicit decision:
- **deploy**: script is useful to consumers; needs a new or extended deploy phase
- **allowlist**: script is host-side tooling only; consumer projects never need it;
  add to `EXTERNAL_DEPENDENCY_ALLOWLIST` with written justification
- **guard-normalize**: the reference is a self-ref or directory ref that the guard
  should handle differently (e.g. `scripts/build.py` self-ref, `scripts/ac_store`
  directory ref)

Key files to read:
- `scripts/build.py` — `_check_script_reference_guard()`, `_get_source_deployable_scripts()`,
  `_run_phases()` (lines ~393–492 in the EPIC worktree)
- `scripts/build_propagation_audit.py` — `EXTERNAL_DEPENDENCY_ALLOWLIST`
- Each Class B script under `scripts/` in the package root
- `templates/agents/` and `templates/skills/` — which templates reference each script
- Evidence: `/tmp/bp900_refs.jsonl` (22 broken-ref lines with referencing template and
  suggested action per line)

## Acceptance Criteria

```gherkin
Scenario: per-script decision table produced (AC-1)
  Given the 12 Class B scripts listed in this ticket
  When python-coder reads each script and the templates that reference it
  Then a decision table is appended to ## Comments with columns:
    script_path | decision (deploy|allowlist|guard-normalize) | justification
  And every script has exactly one decision
  And no script is marked "allowlist" without a written justification
    explaining why the consumer project does not need it
  origin_agent: BrainCandy

Scenario: self-refs and directory refs identified separately (AC-2)
  Given that scripts/build.py references itself and agents/build-ac.md
    references the directory scripts/ac_store
  When the triage runs
  Then these are classified as guard-normalize (not deploy, not allowlist)
  And the triage recommends whether the guard should skip self-refs and
    directory refs or resolve them differently
  origin_agent: BrainCandy

Scenario: triage output is machine-readable for ticket 03 (AC-3)
  Given the decision table in ## Comments
  When ticket 03's implementer reads it
  Then every row unambiguously maps to an action in scripts/build.py or
    scripts/build_propagation_audit.py
  origin_agent: BrainCandy
```

## Implementation Tasks

- [ ] Read `/tmp/bp900_refs.jsonl` (or reproduce via `python scripts/build.py
  --target-dir /tmp/anydir --validate-only` from the EPIC worktree) to get the
  full list of 22 flagged references; extract the 12 Class B entries
- [ ] For each Class B script: read the script source; read the referencing template;
  determine deploy | allowlist | guard-normalize
- [ ] Produce the decision table in ## Comments (no code changes in this ticket)
- [ ] Flag any script where the decision is genuinely ambiguous with an OPEN QUESTION
  label so the implementer of ticket 03 can escalate if needed

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only analysis ticket.
- Reversibility? N/A — produces a decision document only, no code changes.

## Comments

_(Append-only log — leave blank when authoring.)_
