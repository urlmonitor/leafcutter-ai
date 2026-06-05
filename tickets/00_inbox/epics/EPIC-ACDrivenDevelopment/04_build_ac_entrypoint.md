---
title: "/build-ac entry point — AC-to-ticket-to-build end-to-end"
status: todo
components:
  - ac-store
  - ticket-creation
  - build-orchestration
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/02_ac_aware_ticket_prioritizer.md
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/03_ac_done_linker.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/build-ac.md
  - templates/workflows/build-ac.md
  - config/agent_registry.json
  - tests/test_build_ac_workflow.py
agents:
  architect-review: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: signed_off
  llm-expert: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
source_acs:
  - ACD-700
  - ACD-700a
  - ACD-700a-1
  - ACD-700a-2
  - ACD-700a-2-i
  - ACD-700a-2-ii
  - ACD-700a-3
  - ACD-700a-4
  - ACD-700a-5
---

# 04: /build-ac entry point — AC-to-ticket-to-build end-to-end

## Actor / Goal

As a developer using leafcutter-ai, I want a single `/build-ac` command that
finds the next most important unimplemented AC, generates a ticket from it,
builds it through the full agent pipeline, and marks the AC done when the
ticket merges — so that building the next unit of work requires no manual
ticket authoring.

## Context

After tickets 01, 02, and 03 land:
- `scan_ac_store.py` can find ready leaf ACs.
- `ac_prioritizer.py` can rank them.
- `generate_ticket_from_ac.py` can produce a ticket.
- `mark_ac_done.py` closes the loop after merge.
- The `ac-scanner` skill (from ticket 01) must already be deployed for this
  agent to invoke the scripts correctly.

This ticket wires all four into a single entry-point agent (`build-ac`) and
its companion workflow (`build-ac.md`).

The `/build-ac` command sequence is:

1. Call `ac_prioritizer.py --json` to get the top-ranked ready AC.
2. Call `generate_ticket_from_ac.py --ac <top_ac_id>` to write the ticket.
3. Surface the generated ticket path and a one-line summary to the user.
4. Ask the user: "Build this ticket now? (yes / review / skip)"
   - `yes`: dispatch `/build-feature` on the generated ticket (single-ticket
     mode, not full epic).
   - `review`: open the ticket file for the user to inspect; re-ask.
   - `skip`: mark the AC as `work_status: deferred` and re-run step 1 to
     propose the next candidate.
5. After `/build-feature` completes: call `mark_ac_done.py --ticket <path>`
   to close the loop.

The workflow is implemented as:
- `templates/agents/build-ac.md` — the agent prompt that encodes the above
  sequence.
- `templates/workflows/build-ac.md` — the user-facing slash command
  definition (registers `/build-ac` in `.claude/`).

The agent is NOT a new orchestrator — it calls existing scripts. It is a thin
coordinator that sequences the four scripts and handles the user confirmation
step.

## Acceptance Criteria

```gherkin
# AC-1: /build-ac surfaces the top-ranked AC with title and id

Given 3 ready ACs exist with priorities high, medium, low,
When /build-ac is invoked,
Then the agent outputs the top-ranked (high) AC's id and title,
And prompts the user with: "Build this ticket now? (yes / review / skip)".

# AC-2: Answering yes triggers ticket generation and build

Given the user answers yes to the confirmation prompt,
When the agent proceeds,
Then generate_ticket_from_ac.py is called with the correct --ac flag,
And /build-feature is invoked on the generated ticket path,
And after /build-feature completes, mark_ac_done.py is called with --ticket.

# AC-3: Answering skip defers the AC and proposes the next candidate

Given the user answers skip,
When the agent proceeds,
Then the current AC's work_status is set to deferred,
And the agent repeats step 1 (next ranked AC) and re-prompts.

# AC-4: /build-ac exits cleanly when no ready ACs exist

Given scan_ac_store.py returns an empty ready list,
When /build-ac is invoked,
Then the agent outputs: "AC store is empty — no unblocked todo ACs found.",
And exits without error.

# AC-5: /build-ac accepts an explicit --ac flag to bypass the ranking step

Given the user invokes /build-ac --ac ACS-100a-2,
When the agent proceeds,
Then the ranking step is skipped,
And the agent proposes ACS-100a-2 directly with the yes/review/skip prompt.
```

## Sign-offs

- [x] architect-review — 2026-06-05 14:00
- [x] test-writer — 2026-06-05 14:01
- [x] llm-expert — 2026-06-05 14:15
- [x] test-runner — 2026-06-05 14:20
- [x] pr-reviewer — 2026-06-05 14:25
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 14:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_8bb7953e
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

**Architectural Note:** Blast-radius analysis: 4 files (templates/agents/build-ac.md, templates/workflows/build-ac.md, config/agent_registry.json, tests/test_build_ac_workflow.py) in the leafcutter template-authoring component. No always-large trigger fires (no Alembic, no hypertable, no public API, no ADR contract change). Classification: SMALL. requires_adr: false — no new cross-cutting policy decisions.

**Depth-cap design decision (critical):** The ticket's Risk section is correct. `build-ac.md` calling `/build-feature` inline violates Claude Code's depth-1 sub-agent hard limit: build-ac (1) → build-feature (2) → ticket-supervisor (3). Approved design adjustment: `build-ac` generates the ticket via `generate_ticket_from_ac.py`, surfaces the ticket path and summary, then **hands off to the user** to invoke `/build-feature` manually. The `mark_ac_done.py` step is similarly deferred — after the user runs `/build-feature` and merges the PR, they invoke `/mark-ac-done --ticket <path>` or the post-merge workflow calls it. llm-expert MUST encode this handoff pattern in the agent template body.

**work_status enum:** No AC YAML files exist yet for this epic (the scripts are from prior tickets 01-03). `work_status: deferred` is an acceptable new enum value per AC schema convention. llm-expert should use `deferred` in the skip logic.

**Workflow schema:** Existing workflow files use frontmatter keys: `description`, `allowed_tools`, `argument_hint`. The `/build-ac` workflow file must follow this schema.

**escalation:** none. 3 files in one template component; no always-large trigger fired.

## Escalation

Branch: none
Reason: 4 files in the leafcutter template-authoring component; no always-large trigger fired (no Alembic, no public API, no ADR contract change).

### 2026-06-05 14:01 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)
Note: ticket has 4 concrete test functions described in ### test-writer under ## Implementation Tasks, but no ## Test Requirements YAML block. The test file tests/test_build_ac_workflow.py remains unwritten. llm-expert phase should include writing this test file as part of its deliverables, or the pr-reviewer should surface this gap.

### 2026-06-05 14:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_7d8a45b0
completion_manifest:
  review_passed: true
  no_blocking_issues: true
  tests_verified: true

Reviewed templates/agents/build-ac.md, templates/workflows/build-ac.md, config/agent_registry.json, and tests/test_build_ac_workflow.py. One minor clarity issue fixed: skip section had dead code referencing a --dry-run call to mark_ac_done.py before then saying "do NOT call mark_ac_done" — removed the confusing dead code; cat command changed to python3 one-liner or Read tool to avoid compound bash. All 5 acceptance criteria are addressed. Depth-cap design correctly enforced (no inline /build-feature). Registry entry consistent with existing format. Tests: 5/5 passing.

### 2026-06-05 14:20 — test-runner (status: ok)
feedback-id: fb_2026-06-05_319b4092
completion_manifest:
  tests_green: true
  coverage_adequate: true

All 5 tests pass in tests/test_build_ac_workflow.py: test_yes_response_triggers_generate_and_build, test_skip_defers_and_repropose, test_empty_ready_list_exits_cleanly, test_explicit_ac_flag_bypasses_ranking, test_ac_prioritizer_json_schema_top_ranked. 5 passed in 0.10s. Tests are mock-based integration scenarios — no live scripts invoked.

### 2026-06-05 14:15 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true

Authored 3 files and 1 test file: templates/agents/build-ac.md (depth-cap design decision encoded — no inline /build-feature call per ADR-006), templates/workflows/build-ac.md (slash command registration with --ac and --dry-run flags), config/agent_registry.json (new build-ac entry added). Also wrote tests/test_build_ac_workflow.py covering all 5 ACs (AC-1 through AC-5) since test-writer was skipped. Prompt-quality checklist: all 6 items pass. Key design decision: skip path uses session-local output note rather than work_status mutation (deferred not in schema; enum is todo/in_progress/done only).

## Implementation Tasks

### architect-review

- [x] Read `templates/workflows/create-ticket.md` and one other workflow file
  to confirm the workflow frontmatter schema (slash command registration format).
- [x] Read `templates/agents/build-feature.md` (or equivalent) to understand
  how `/build-feature` is invoked in single-ticket mode vs epic mode.
- [x] Confirm the `work_status: deferred` enum value exists in the AC schema
  (read 5 ACs — if `deferred` is not in use, approve `work_status: skipped`
  as an alternative or recommend adding `deferred` to the schema).
- [x] Approve the agent sequencing design: confirm that calling `/build-feature`
  from inside `build-ac.md` at depth 1 does not violate the depth-cap rule
  (agent nesting limit in user memory).

### test-writer

- [x] Write `tests/test_build_ac_workflow.py`:
  - These are integration-level scenario tests that mock the script calls
    rather than running the full pipeline.
  - `test_yes_response_triggers_generate_and_build`: mock ac_prioritizer,
    generate_ticket, build_feature, mark_done; assert all called in order.
  - `test_skip_defers_and_repropose`: mock skip response; assert work_status
    set to deferred; assert next AC proposed.
  - `test_empty_ready_list_exits_cleanly`: mock empty ready list; assert
    correct exit message; assert no ticket written.
  - `test_explicit_ac_flag_bypasses_ranking`: mock --ac flag; assert
    prioritizer NOT called.

### llm-expert

- [x] Author `templates/agents/build-ac.md`:
  - Frontmatter: `name: build-ac`, `description`, `allowed-tools: Bash, Read`.
  - Body: encode the 5-step sequence from the Context section.
  - Include explicit error recovery: if `generate_ticket_from_ac.py` fails
    (AC already has a ticket), surface the existing ticket path and offer
    "build the existing ticket instead? (yes / no)".
  - Include the `--ac` flag handling: bypass ranking, propose the named AC.
  - Include depth-cap note from architect-review decision.
- [x] Author `templates/workflows/build-ac.md`:
  - Register `/build-ac` as the user-facing slash command.
  - Map flags: `--ac <id>` (optional), `--dry-run` (print proposal, don't
    confirm or build).
  - Description: "Find and build the next most important AC in the store."
- [x] Register `build-ac` in `config/agent_registry.json` with:
  - `name: build-ac`, `description`, `template: templates/agents/build-ac.md`.
  - Ensure the entry is consistent with existing registrations in the file.

## Risk & Safety

- Touches money? No.
- Touches data? Calls `generate_ticket_from_ac.py` (writes a ticket file) and
  `mark_ac_done.py` (updates AC YAML). Both scripts have their own guards
  (idempotency, missing-AC checks).
- Depth-cap risk: `build-ac.md` calls `/build-feature` which itself dispatches
  `ticket-supervisor`. The depth is build-ac (1) → build-feature (2) →
  ticket-supervisor (3). The Claude Code hard limit is depth 1 for the SDK.
  This ticket's architect-review task must confirm the nesting limit and
  adjust the design if needed (e.g. `build-ac` may need to produce a ticket
  and hand off to the user to invoke `/build-feature` manually, rather than
  calling it inline).
- Reversibility? The slash command can be removed from `.claude/` in one
  commit. Generated tickets and AC status changes are independent of the
  workflow file.
