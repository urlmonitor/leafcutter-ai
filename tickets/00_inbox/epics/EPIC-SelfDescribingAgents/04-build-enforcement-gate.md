---
title: "INF-600 Ticket 4: Add build validation gate rejecting agent templates missing required self-description fields"
status: done
components:
  - build_pipeline
created: 2026-06-05
depends_on:
  - TICKET-20260605-INF600-CardGenerator.md
  - TICKET-20260605-INF600-AgentCategories.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_phases.py
  - scripts/build.py
  - config/agent_registry.json
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
source_acs:
  - INF-600g
ac_path: docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/
ac_coverage: 0/1
---

# INF-600 Ticket 4: Add build validation gate rejecting agent templates missing required self-description fields

## Actor / Goal

In order to prevent agent cards from going stale, we need to add validation
to `build.py` that rejects agent templates missing required self-description
fields. The validation emits clear error messages naming the missing fields,
and has configurable severity (warning vs error) for the rollout period while
Ticket 5 populates all remaining agents.

## Context

This ticket implements INF-600g: "An agent that cannot describe itself does
not pass the build."

Without this gate, the Ticket 5 rollout can drift: contributors add agents
without filling in required fields, and the card generator silently produces
incomplete cards. The gate closes this drift path at build time.

The gate has two severity modes:
- `warning`: prints a message but does not fail the build. Used during the
  Ticket 5 rollout period when most agents still lack the new fields.
- `error`: fails the build with a non-zero exit. Used once Ticket 5 is
  complete and all agents carry the required fields.

The enforcement level is configurable via `config/agent_registry.json`
(a new `self_description_enforcement` key) or via a CLI flag to `build.py`.

Depends on Ticket 2 (card generator) and Ticket 3 (categories) because:
- Ticket 2 defines which fields the generator reads; those are the required fields.
- Ticket 3 adds `category` as a required registry field; this validator checks it.

All ACs are at:
`docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/INF-600g.yaml`

## Acceptance Criteria

```gherkin
# INF-600g: An agent that cannot describe itself does not pass the build
Given a build run that processes agent templates
When an agent template's frontmatter is missing one or more required
  self-description fields (any of: behavioral_patterns, pre_flight_reads,
  inputs, outputs, mutates)
And the build's self_description_enforcement is set to "error"
Then build.py exits with a non-zero exit code
And the error message names the agent template file
And the error message lists each missing field by name
And the error message suggests the field schema (structure expected)

Given a build run with self_description_enforcement: "warning"
When an agent template is missing required self-description fields
Then build.py exits 0 (build succeeds)
And a WARNING message is printed naming the agent and missing fields
And the card generator still produces a card for the agent (graceful degradation)

Given a registry entry is missing the "category" field
And self_description_enforcement is "error"
Then build.py exits non-zero
And the error message names the registry entry (agent ID) and the missing field

Given a registry entry's skills_invoked contains an unresolvable skill_id
And self_description_enforcement is "error"
Then build.py exits non-zero naming the agent and the unresolvable skill_id
And distinguishes "not in templates/skills/" from "not in .claude/skills/"

Given a registry entry's knowledge_channels contains channel: 12
And self_description_enforcement is "error"
Then build.py exits non-zero naming the agent and invalid channel
And the error cites the valid range (1-11)

Given all 40 agent templates carry all required self-description fields
And all registry entries carry category and valid skills_invoked
When the build runs with self_description_enforcement: "error"
Then build.py exits 0
And no warnings or errors are emitted for self-description validation

Given build.py --self-description-enforcement=warning
When an agent template is missing fields
Then this CLI flag overrides the config/agent_registry.json setting
```

## Sign-offs

- [x] architect-review — 2026-06-05 12:00
- [x] test-writer — 2026-06-05 12:15
- [x] python-coder — 2026-06-05 12:30
- [x] test-runner — 2026-06-05 12:45
- [x] pr-reviewer — 2026-06-05 13:00
- [x] commit — 2026-06-05 13:15
- [x] pull-request — 2026-06-05 13:20

## Comments

### 2026-06-05 13:20 — pull-request (status: ok)
feedback-id: fb_2026-06-05_8d17bc54
completion_manifest:
  branch_pushed: true
  pr_open: true

Existing epic PR #65 (`feat(EPIC-SelfDescribingAgents/01): add six self-description metadata fields to python-coder`) on `feature/EPIC-SelfDescribingAgents` is already open. Pushed commit 213d4a4 to the branch — the PR now includes the ticket 04 changes. URL: https://github.com/urlmonitor/leafcutter-ai/pull/65

### 2026-06-05 13:15 — commit (status: ok)
feedback-id: fb_2026-06-05_6ceeb6df
completion_manifest:
  files_staged_correctly: true
  commit_successful: true
  no_unintended_files: true

Committed 5 in-scope files on branch `feature/EPIC-SelfDescribingAgents` (SHA 213d4a4): `scripts/build_phases.py`, `scripts/build.py`, `config/agent_registry.json`, `tickets/00_inbox/epics/EPIC-SelfDescribingAgents/04-build-enforcement-gate.md`, `unit_tests/test_agent_self_description_validation.py` (new). No unintended files staged. No pre-commit config present in worktree; `PRE_COMMIT_ALLOW_NO_CONFIG=1` used to bypass the pre-commit framework guard.

### 2026-06-05 13:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_bf0a88d8
completion_manifest:
  acs_satisfied: true
  error_handling_policy_followed: true
  code_quality_acceptable: true
  no_regressions: true

Reviewed implementation against all 7 AC scenarios in INF-600g. All scenarios satisfied: (1) error mode → non-zero exit with named agent and fields, (2) warning mode → zero exit with WARNING messages, (3) missing registry category caught, (4) unresolvable skills_invoked with package/project-local distinction, (5) out-of-range knowledge_channels citing 1-11, (6) fully-populated → clean exit, (7) CLI flag overrides config. Error-handling policy followed (all I/O in try/except OSError). Aggregated output confirmed by test. 11/11 tests green. No blockers.

### 2026-06-05 12:45 — test-runner (status: ok)
feedback-id: fb_2026-06-05_b47ae37c
completion_manifest:
  all_tests_green: true
  no_regressions: true
  test_coverage_complete: true

Ran `unit_tests/test_agent_self_description_validation.py` — 11/11 tests passed. All test cases exercised: fully-populated pass, each missing frontmatter field (behavioral_patterns, pre_flight_reads, inputs, outputs, mutates), missing registry category, unresolvable skills_invoked, out-of-range knowledge_channels (12), warning mode (returns (0,N)), error mode aggregation (all errors collected), CLI flag override, and integration return-type check. No regressions in `test_generate_agent_cards.py`, `test_build_hooks.py`, `test_build_workflows.py`, `test_build_workflow_phase.py`, `test_build_epic_workflow.py`, `test_build_ac_store_scaffold.py`.

### 2026-06-05 12:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_72387b13
completion_manifest:
  validate_agent_self_description_implemented: true
  self_description_enforcement_key_added: true
  build_py_wired: true
  tests_green: true
  error_handling_policy_followed: true

Implemented `validate_agent_self_description()` in `scripts/build_phases.py` per the approved schema: validates 5 frontmatter fields (`behavioral_patterns`, `pre_flight_reads`, `inputs`, `outputs`, `mutates`), 3 registry fields (`category`, `skills_invoked`, `knowledge_channels`), skill_id resolvability against package and project-local paths, and channel range 1-11. Aggregated output — never halts on first error. Added `self_description_enforcement: "warning"` to `config/agent_registry.json`. Wired `--self-description-enforcement` CLI flag into `build.py` with registry-config → CLI-flag precedence; validation runs before `_run_phases()` so errors surface before card generation. All 11 new tests green; 0 regressions in existing suite. All file I/O in `try/except OSError` per error-handling policy.

### 2026-06-05 12:15 — test-writer (status: ok)
feedback-id: fb_2026-06-05_7860ecb0
completion_manifest:
  tests_written: true
  red_baseline_confirmed: true
  covers_all_acs: true

Created `unit_tests/test_agent_self_description_validation.py` with 11 failing tests (red baseline). All tests fail with ImportError confirming `validate_agent_self_description` does not yet exist. Test coverage includes: fully-populated pass, each missing frontmatter field, missing registry category, unresolvable skills_invoked, out-of-range knowledge_channels, warning mode, error aggregation, CLI flag override, and integration return-type check.

### 2026-06-05 12:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_95f8f96b
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

**Architectural Review — Small Case**

Blast-radius: 3 files touched (`scripts/build_phases.py`, `scripts/build.py`, `config/agent_registry.json`), all within the `build_pipeline` component. No Alembic migrations, no hypertable changes, no public API changes, no ADR contract changes.

**Impact classification: SMALL.** Threshold rules: 3 files ≤ 5, 1 component, no cross-module boundary. No always-large trigger fired.

**Design confirmations:**
1. Required frontmatter fields: `behavioral_patterns`, `pre_flight_reads`, `inputs`, `outputs`, `mutates`. Required registry fields: `category`, `skills_invoked`, `knowledge_channels`. Schema approved.
2. Enforcement config: both mechanisms approved — `self_description_enforcement` key in `config/agent_registry.json` (default `"warning"`) + `--self-description-enforcement` CLI override.
3. Validation phase ordering: `validate_agent_self_description()` runs BEFORE `build_agent_cards()`. Aggregated output (all problems in one pass) confirmed.
4. Error message format: confirmed as proposed. Messages must name agent, field, location (frontmatter vs registry), and fix hint.

**Design concerns:** The `skills_invoked` validation path must check both `templates/skills/` and `.claude/skills/` directories and clearly distinguish "not in package" from "not in project-local". This distinction is already called out in the ACs. No ADR required (`requires_adr: false`). No diagrams needed (pure refactor within one component).

## Escalation

Branch: none
Reason: 3 files in one component (build_pipeline); no always-large trigger fired.

## Implementation Tasks

### architect-review

- [x] Confirm which fields are "required" for self-description validation.
  Proposed required-in-frontmatter: `behavioral_patterns`, `pre_flight_reads`,
  `inputs`, `outputs`, `mutates`. Proposed required-in-registry: `category`,
  `skills_invoked`, `knowledge_channels`. Confirm this list is correct and
  complete, or adjust. The validation gate must check exactly these fields.

- [x] Confirm the enforcement level configuration mechanism. Two options:
  (a) A top-level `self_description_enforcement: "warning"|"error"` key in
  `config/agent_registry.json` (config-file driven, version-controlled).
  (b) A `--self-description-enforcement` CLI flag on `build.py` (runtime
  override). Recommend using both: config sets the default, CLI can override.
  Confirm this is acceptable.

- [x] Confirm the validation should run as a separate build phase
  (`validate_agent_self_description()`) that runs BEFORE `build_agent_cards()`
  (Ticket 2), so validation errors are surfaced before the generator runs.
  The error/warning output should be aggregated: list all problems across all
  agents in one pass, not halt on the first agent.

- [x] Confirm error message format. Proposed:
  ```
  ERROR: Agent 'sql-coder' template missing required self-description fields:
    - behavioral_patterns (frontmatter): Add a behavioral_patterns array listing
      conditional behaviors, gates, delegation rules. Example:
        behavioral_patterns:
          - name: "Stop-and-Ask"
            trigger: "..."
            behavior: "..."
            related_agent: null
    - pre_flight_reads (frontmatter): Add a pre_flight_reads array listing
      documents the agent reads before starting work.
  Fix these fields and re-run the build.
  ```
  Confirm this format or propose an alternative. The message must be actionable.

**Delivers to python-coder:** Approved validation schema, enforcement config
mechanism, and error message format.

### test-writer

Create `unit_tests/test_agent_self_description_validation.py`:

- [x] `test_validation_passes_for_fully_populated_agent`:
  Given a fixture with all required fields present, assert the validator
  returns no errors.

- [x] `test_validation_fails_for_missing_behavioral_patterns`:
  Given frontmatter with `behavioral_patterns` absent, assert the validator
  returns an error entry naming the field.

- [x] `test_validation_fails_for_missing_pre_flight_reads`:
  Similar test for `pre_flight_reads` absent.

- [x] `test_validation_fails_for_missing_inputs_outputs_mutates`:
  Given frontmatter missing all three I/O fields, assert three error entries.

- [x] `test_validation_fails_for_missing_registry_category`:
  Given a registry entry with no `category` field, assert error naming the agent.

- [x] `test_validation_fails_for_invalid_skills_invoked_skill_id`:
  Given `skills_invoked: [{skill_id: "ghost-skill", mode: "always"}]`,
  assert error naming the unresolvable skill_id and distinguishing the two
  not-found cases (package vs. project-local).

- [x] `test_validation_fails_for_out_of_range_knowledge_channel`:
  Given `knowledge_channels: [{channel: 12, ...}]`, assert error citing range 1-11.

- [x] `test_warning_mode_does_not_raise`:
  Given enforcement_level="warning" and missing fields, assert the function
  returns without raising and returns a list of warning strings (not raises).

- [x] `test_error_mode_aggregates_all_problems`:
  Given two agents with missing fields, assert all errors are returned in one
  list (not halted at first error).

- [x] `test_cli_flag_overrides_config`:
  Given registry config says "warning" and CLI flag says "error", assert
  validation uses "error" mode.

- [x] `test_build_phases_integration`:
  Call `validate_agent_self_description(target_root=<tmp>, config={...},
  dry_run=False)` and assert it returns (error_count, warning_count) integers.

**Depends on architect-review:** Approved validation schema and enforcement config.

### python-coder

**Important:** Do not begin until architect-review and test-writer have signed off.

**Deliverable 1 — `validate_agent_self_description()` in `scripts/build_phases.py`**

Add a new validation function following the `build_vision()` pattern:

```python
def validate_agent_self_description(
    target_root: Path,
    config: dict,
    dry_run: bool,
    enforcement_level: str = "warning"  # "warning" | "error"
) -> tuple[int, int]:
    """Validate all agent templates have required self-description fields.
    Returns (error_count, warning_count).
    """
```

Implementation requirements:

1. **Read all agent templates** from `target_root / "templates" / "agents"`.
   Skip `_*.md` helper files.

2. **Read the registry** from `target_root / "config" / "agent_registry.json"`.
   Build a dict keyed by agent ID for fast lookup.

3. **Validate each agent**:
   - Frontmatter fields: check for `behavioral_patterns`, `pre_flight_reads`,
     `inputs`, `outputs`, `mutates`. Each missing field adds one entry to
     the problem list for this agent.
   - Registry fields: check for `category`, `skills_invoked`, `knowledge_channels`.
   - `skills_invoked` validation: for each entry, resolve `skill_id` against
     `target_root / "templates" / "skills"` (packaged) and
     `.claude/skills/` (project-local). If not found in either, add problem.
   - `knowledge_channels` validation: for each entry, check `channel` is 1-11.

4. **Enforce per problem level**: collect all problems, then:
   - `warning`: print warnings and return `(0, warning_count)`.
   - `error`: print errors and return `(error_count, 0)`.

5. **Error message format**: use the format approved by architect-review.
   Every problem entry must name the agent, the field, the location
   (frontmatter vs registry), and provide a brief fix hint.

6. **Aggregated output**: always emit all problems before returning.
   Never halt on the first error.

7. **Follow error handling policy**: all file I/O in `try/except OSError`.

**Deliverable 2 — `config/agent_registry.json`: `self_description_enforcement` key**

Add a top-level `self_description_enforcement` key to the registry JSON:

```json
"self_description_enforcement": "warning"
```

Initial value is `"warning"` for the rollout period. Ticket 5 will flip it
to `"error"` once all agents are populated.

**Deliverable 3 — Wire into `scripts/build.py`**

- Read `self_description_enforcement` from the registry config (or use "warning"
  as default when absent).
- Add `--self-description-enforcement` CLI flag to `build.py`'s argument parser.
  When specified, it overrides the registry config value.
- Call `validate_agent_self_description(...)` as the first phase in the build
  pipeline, before template compilation and card generation.
- When `enforcement_level == "error"` and `error_count > 0`: exit with
  `sys.exit(1)` after printing all errors.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only validation. Writes nothing.
- Reversibility? The enforcement level defaults to "warning" so the gate cannot
  break builds during rollout. Switching to "error" is a one-line config change.
- Risk of regressions: low. The validator is a new code path that runs before
  existing phases. The existing template compilation and card generation are
  unaffected by validation results (the generator still runs; it handles absent
  fields gracefully per Ticket 2).
- Risk if enforcement prematurely set to "error": would block all builds for all
  teams using the package until their agents are populated. The "warning" default
  for the rollout period mitigates this. The registry `self_description_enforcement`
  key makes the upgrade path explicit and version-controlled.
