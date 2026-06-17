---
title: "Class B resolution: deploy or allowlist each undeployed-but-referenced script"
status: todo
components:
  - build_pipeline
  - bootstrap_installer
created: 2026-06-17
depends_on:
  - 01_research_class_b_triage.md
  - 02_fix_class_a_manifest.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Class B Resolution — Deploy or Allowlist Each Undeployed-But-Referenced Script

## Goal

In order to ensure that consumer installs receive every script their deployed
agents/skills reference, we need to implement the deploy-or-allowlist decision
for each Class B script from the ticket 01 triage, so that the build guard passes
for legitimate reasons rather than being silenced.

## Context

After ticket 02 the guard still exits 1 for the 12 Class B scripts. These are
referenced by deployed agent/skill templates but are NOT deployed by any build phase.
Simply adding them to `EXTERNAL_DEPENDENCY_ALLOWLIST` would silence the guard while
the install remains broken.

The correct resolution per script (final decisions come from ticket 01):

**Likely deploy candidates** (script is useful to consumer projects):
- `scripts/set_ticket_status.py` — used by ticket lifecycle agents
- `scripts/ticket_prioritizer.py` — used by ticket lifecycle agents
- `scripts/knowledge_query.py` — used by knowledge-query skill
- `scripts/setup_ticket_worktree.py` — used by worktree-agent
- `scripts/add_component.py` — used by workflow agents
- `scripts/scaffold/new_arch_doc.py` — used by documentation agents
- `scripts/knowledge/harvest_learnings.py` — used by knowledge-harvester
- `scripts/inline_adr/append_entry.py` — used by ADR agents

**Likely allowlist candidates** (host-side tooling, consumer never needs):
- `scripts/epic_lock.py` — epic branch lock, host-side orchestration
- `scripts/list_sql_helpers.py` — project-specific host tooling
- `scripts/build.py` self-reference — guard should normalize, not deploy build.py
- `scripts/ac_store` directory reference — guard should resolve to manifest entries

**Guard-normalize candidates**:
- `scripts/build.py` self-ref — the guard scanning its own invocation script
- `scripts/ac_store` directory ref (from agents/build-ac.md) — already covered by
  the ac_store manifest entries; guard may need to handle directory refs differently

Key files:
- `scripts/build_propagation_audit.py` — `EXTERNAL_DEPENDENCY_ALLOWLIST` (add entries here)
- `scripts/build.py` — `_check_script_reference_guard()` (for guard-normalize changes)
- `build_phases.py` — add new deploy phases here for any "deploy" decisions
- Decision table from ticket 01 `## Comments`

## Acceptance Criteria

```gherkin
Scenario: Class B real-gap detection preserved (AC BP-900-Fix-3)
  Given a template that references scripts/some_undeployed_script.py
  And that script is NOT added to EXTERNAL_DEPENDENCY_ALLOWLIST
  And no build phase deploys it
  When the guard runs
  Then it reports that reference as broken and exits non-zero
  origin_agent: BrainCandy

Scenario: allowlist entries have written justification (AC BP-900-Fix-5)
  Given each script added to EXTERNAL_DEPENDENCY_ALLOWLIST in this ticket
  When the allowlist entry is read
  Then it has an inline comment or docstring explaining:
    - why the script is host-only or external
    - why the consumer project does not need it
  origin_agent: BrainCandy

Scenario: deployed scripts reach consumer install (AC-3)
  Given a script classified as "deploy" in the ticket 01 triage
  When a clean build runs against a fresh temp dir
  Then the script is present at the expected path under .leafcutter/ or scripts/
    in the consumer project
  origin_agent: BrainCandy

Scenario: guard exits 0 after all Class B scripts resolved (AC-4)
  Given the unmodified package with tickets 01+02+03 applied
  When python scripts/build.py --target-dir <fresh-temp-dir> runs
  Then it exits 0
  And zero broken-reference JSONL lines are emitted to stderr
  origin_agent: BrainCandy
```

## Implementation Tasks

- [ ] Read the decision table from ticket 01's ## Comments
- [ ] For each "deploy" decision: add a deploy phase or extend an existing phase in
  `build_phases.py` so the script reaches the consumer install; update the manifest
  in `_get_source_deployable_scripts()` if the new phase is not auto-covered by ticket 02
- [ ] For each "allowlist" decision: add the script path to
  `EXTERNAL_DEPENDENCY_ALLOWLIST` in `build_propagation_audit.py` with an inline
  comment justifying the host-only classification
- [ ] For each "guard-normalize" decision: update `_check_script_reference_guard()`
  to skip self-refs (`scripts/build.py`) and resolve directory refs
  (`scripts/ac_store`) to their constituent manifest entries
- [ ] Run a clean build against a fresh temp dir and confirm exit 0

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Adding deploy phases is additive and reversible. Allowlist entries
  are config-only. Guard-normalize changes are localized to one function.
- Critical risk: do NOT allowlist scripts that consumer projects need. If uncertain,
  prefer "deploy" over "allowlist" — a script deployed but unused is harmless;
  a script allowlisted but needed breaks every consumer that invokes the agent.

## Comments

_(Append-only log — leave blank when authoring.)_
