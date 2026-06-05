---
title: "AC Fulfillment Gate — verify and auto-fix AC store fields before commit"
status: todo
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/ac-fulfillment-gate.md
  - templates/skills/building-epics/SKILL.md
  - config/ac_store_schema.json
  - config/agent_registry.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  llm-expert: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
ac_traceability:
  l2:
    - BO-201
    - BO-202
  ac_path: docs/acceptance-criteria/build_pipeline/
---

# AC Fulfillment Gate — verify and auto-fix AC store fields before commit

## Actor / Goal

As a ticket-supervisor phase chain operator, I need an ac-fulfillment-gate agent
that runs at priority 11.7 — after ac-validator (11.5) and before commit (12) —
so that AC YAML store fields (`work_status`, `implemented_by`, `covered_by`) are
always accurate and up-to-date before any commit is made.

## Context

The AC traceability store (`docs/acceptance-criteria/**/*.yaml`) tracks acceptance
criteria with fields including `work_status`, `implemented_by`, and `covered_by`.
Currently no agent enforces that these fields are updated when implementation is
complete. This gap was observed during TICKET-20260605-ContractShrinkingSelfExclusion:
the ticket-supervisor completed all phase agents but left both AC files at
`work_status: todo` with empty `implemented_by` and `covered_by`.

The existing `ac-validator` (priority 11.5) checks AC coverage in the implementation
diff but does NOT verify the AC YAML store fields. This ticket introduces a
complementary gate that closes the gap.

The new agent follows the pattern established by `ac-validator.md`. It is registered
in `agent_registry.json` with `tier: phase`, `role: quality`, and `priority: 11.7`.
The `config/ac_store_schema.json` must be extended with v3 fields (`work_status`,
`level`, etc.) as a prerequisite.

Implements AC BO-201 and AC BO-202.

## AC References

- Implements AC BO-201 (ac-fulfillment-gate phase gate with ok/blocker verdict)
- Implements AC BO-202 (auto-fix when evidence exists in branch diff)

## Acceptance Criteria

- [ ] AC BO-201: `ac-fulfillment-gate` agent runs at priority 11.7 in the ticket-supervisor
  phase chain. Given a ticket with `ac_traceability` frontmatter referencing AC YAML files,
  when the agent runs after `ac-validator` and before `commit`, then it loads each referenced
  L2/L3 AC YAML file from the `ac_path`, verifies `work_status` equals `done`, verifies
  `implemented_by` contains at least one file path present in the branch diff (constrained to
  `files_touched` intersection), verifies `covered_by` contains at least one entry for L2 ACs
  (L3 ACs may have empty `covered_by`), and returns `status: blocker` with per-AC details if
  verification fails after auto-fix attempt, or `status: ok` if all pass. If `ac_traceability`
  is absent from ticket frontmatter, signs off as `ok` (no ACs to verify). L1/L0 ACs are
  skipped (composite — fulfillment derived from children).

- [ ] AC BO-202: When the `ac-fulfillment-gate` agent detects an AC YAML file with
  `work_status: todo` but matching evidence exists in the branch diff, it auto-fixes: sets
  `work_status` to `done`, populates `implemented_by` with file paths from the diff that
  intersect with the ticket's `files_touched`, populates `covered_by` with test file paths
  containing `# covers: <AC-ID>` tags. Auto-fix is append-only (never overwrites existing
  entries), idempotent, and produces valid YAML that passes `check_ac_schema.py`. Auto-fix
  actions are logged in the agent's sign-off comment for auditability.

## AC Traceability

| AC ID | Level | Title | Agent |
|-------|-------|-------|-------|
| BO-201 | L2 | ac-fulfillment-gate phase gate — ok/blocker verdict with per-AC details | llm-expert |
| BO-202 | L2 | Auto-fix work_status and implemented_by/covered_by when diff evidence exists | llm-expert |

AC files: `docs/acceptance-criteria/build_pipeline/BO-201.yaml`, `docs/acceptance-criteria/build_pipeline/BO-202.yaml`

## Test Requirements

- `test_ac_fulfillment_gate_template_frontmatter_valid`: Verify `templates/agents/ac-fulfillment-gate.md`
  has valid frontmatter (`name`, `model: sonnet`, `tools: Bash Read Edit`, `signoff: true`, `portable: true`).
- `test_building_epics_skill_includes_ac_fulfillment_gate_priority`: Verify
  `templates/skills/building-epics/SKILL.md` phase ordering includes `ac-fulfillment-gate` at
  priority 11.7 (after `ac-validator` at 11.5, before `commit` at 12).
- `test_ac_fulfillment_gate_agent_registry_entry`: Verify `config/agent_registry.json` contains
  an `ac-fulfillment-gate` entry with fields `tier: phase`, `role: quality`,
  `spawned_by: [ticket-supervisor]`, and `priority: 11.7`.

## Sign-offs

- [x] test-writer — 2026-06-05 09:15
- [x] llm-expert — 2026-06-05 10:30
- [x] test-runner — 2026-06-05 10:35
- [x] pr-reviewer — 2026-06-05 10:40
- [x] commit — 2026-06-05 10:45
- [ ] pull-request

## Comments

### 2026-06-05 09:15 — test-writer (status: ok)
feedback-id: fb_2026-06-05_6f5e6eed
completion_manifest:
  tests_written: true
  red_baseline_captured: true
  sign_off_complete: true
Wrote `tests/test_ac_fulfillment_gate.py` (18 tests across 3 test classes). 11 tests are
FAILED (correct red state — ac-fulfillment-gate template, registry entry, and SKILL.md
priority row do not yet exist); 7 frontmatter-detail tests are SKIPPED (skip-if-template-absent
guard fires — they will become active once llm-expert creates the template). Verification run
confirmed non-zero exit. Handing off to llm-expert to create the artifacts that will make
these tests green.

red_baseline:
  - test_name: test_template_file_exists
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: False is not true : Agent template not found: /home/henzeh/projects/leafcutter/worktrees/acfulfillmentgate/templates/agents/ac-fulfillment-gate.md\nExpected: llm-expert creates this file as part of TICKET-20260605-ACFulfillmentGate implementation."
  - test_name: test_ac_fulfillment_gate_mentioned
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: building-epics SKILL.md must reference 'ac-fulfillment-gate' in the phase ordering table or canonical phase ordering section."
  - test_name: test_ac_fulfillment_gate_priority_11_7
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: building-epics SKILL.md must associate 'ac-fulfillment-gate' with priority 11.7."
  - test_name: test_ac_fulfillment_gate_after_ac_validator
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: ac-fulfillment-gate must appear AFTER ac-validator (11.5) in the SKILL.md document to reflect correct phase ordering."
  - test_name: test_ac_fulfillment_gate_before_commit
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: ac-fulfillment-gate must appear before the commit priority-12 row in building-epics SKILL.md."
  - test_name: test_entry_exists
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: ac-fulfillment-gate not found in config/agent_registry.json agents list."
  - test_name: test_tier_is_phase
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: test setUp failed (entry is None)"
  - test_name: test_role_is_quality
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: test setUp failed (entry is None)"
  - test_name: test_spawned_by_includes_ticket_supervisor
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: test setUp failed (entry is None)"
  - test_name: test_priority_is_11_7
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: test setUp failed (entry is None)"
  - test_name: test_is_ticket_phase_true
    file: tests/test_ac_fulfillment_gate.py
    error: "AssertionError: test setUp failed (entry is None)"

### 2026-06-05 10:30 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Authored `templates/agents/ac-fulfillment-gate.md` (288 lines, portable: true, signoff: true, model: sonnet). Added `ac-fulfillment-gate` entry to `config/agent_registry.json` with tier: phase, role: quality, spawned_by: [ticket-supervisor], priority: 11.7, is_ticket_phase: true. Updated `templates/skills/building-epics/SKILL.md` pseudocode canonical ordering and added §2.1.1 Canonical Phase Ordering Table with `| 12 |` commit row. Extended `config/ac_store_schema.json` with v3 fields `work_status` and `level`. All 18 tests in `tests/test_ac_fulfillment_gate.py` pass (18 passed, 0 failed).

### 2026-06-05 10:35 — test-runner (status: ok)
feedback-id: fb_2026-06-05_7b8ef145
completion_manifest:
  tests_executed: true
  all_tests_pass: true
  no_regressions: true
Ran `tests/test_ac_fulfillment_gate.py`: 18 passed, 0 failed, 0 skipped. All three test classes (TestAcFulfillmentGateTemplateFrontmatter, TestAcFulfillmentGateTemplateExists, TestBuildingEpicsSkillIncludesAcFulfillmentGate, TestAcFulfillmentGateAgentRegistryEntry) green. Test baseline transitioned from 11 FAILED + 7 SKIPPED (pre-llm-expert) to 18 PASSED.

### 2026-06-05 10:40 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_1c0ef832
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  no_medium_findings: true
Reviewed staged diff (6 files, 815 insertions, 12 deletions). No high-confidence findings. No medium-confidence findings. Suppressed: 0 low-confidence nits. Registry entry mirrors ac-validator pattern correctly; schema extension is backward-compatible (additionalProperties: null union). SKILL.md §2.1.1 table and pseudocode ordering are consistent.

## Escalation

Branch: none
Reason: not escalated: medium count was 0 (threshold > 3)

### 2026-06-05 10:45 — commit (status: ok)
feedback-id: fb_2026-06-05_88c91568
completion_manifest:
  staged_files_verified: true
  commit_created: true
  no_scope_pollution: true
Staged 6 in-scope files: config/ac_store_schema.json, config/agent_registry.json, templates/agents/ac-fulfillment-gate.md, templates/skills/building-epics/SKILL.md, tests/test_ac_fulfillment_gate.py, tickets/00_inbox/TICKET-20260605-ACFulfillmentGate.md. Commit created on branch feature/acfulfillmentgate.

## Implementation Tasks

- [x] Extend `config/ac_store_schema.json` with v3 fields: `work_status`, `level`,
  `implemented_by`, `covered_by` (prerequisite for all other tasks)
- [x] Add `ac-fulfillment-gate` entry to `config/agent_registry.json` with
  `tier: phase`, `role: quality`, `spawned_by: [ticket-supervisor]`, `priority: 11.7`
- [x] Author `templates/agents/ac-fulfillment-gate.md` following the `ac-validator.md`
  pattern; implement:
  - Skip if `ac_traceability` absent from ticket frontmatter (sign off ok)
  - Skip L0/L1 ACs (composite — children determine fulfillment)
  - Load each referenced L2/L3 AC YAML from `ac_path`
  - Verify `work_status == done`
  - Verify `implemented_by` contains at least one path from `files_touched ∩ diff`
  - Verify `covered_by` non-empty for L2 ACs (L3 may be empty)
  - Auto-fix when diff evidence exists (append-only, idempotent, validate with `check_ac_schema.py`)
  - Log all auto-fix actions in sign-off comment
  - Return `status: blocker` with per-AC details on failure, `status: ok` on pass
- [x] Update `templates/skills/building-epics/SKILL.md` phase chain to insert
  `ac-fulfillment-gate` at priority 11.7
- [x] Write unit tests satisfying all three Test Requirements above
- [x] Run test suite; confirm all new tests pass

## Risk & Safety

- Touches money? No.
- Touches data? Modifies AC YAML files in `docs/acceptance-criteria/` via auto-fix;
  auto-fix is append-only and idempotent — no existing entries are overwritten.
  Schema validation (`check_ac_schema.py`) runs before any write.
- Reversibility? Auto-fix changes are committed with the ticket, visible in git diff.
  The blocker path writes nothing — it only reports and returns a non-zero verdict.
