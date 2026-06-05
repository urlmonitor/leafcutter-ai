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
  architect-review: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  llm-expert: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] llm-expert
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read `templates/workflows/create-ticket.md` and one other workflow file
  to confirm the workflow frontmatter schema (slash command registration format).
- [ ] Read `templates/agents/build-feature.md` (or equivalent) to understand
  how `/build-feature` is invoked in single-ticket mode vs epic mode.
- [ ] Confirm the `work_status: deferred` enum value exists in the AC schema
  (read 5 ACs — if `deferred` is not in use, approve `work_status: skipped`
  as an alternative or recommend adding `deferred` to the schema).
- [ ] Approve the agent sequencing design: confirm that calling `/build-feature`
  from inside `build-ac.md` at depth 1 does not violate the depth-cap rule
  (agent nesting limit in user memory).

### test-writer

- [ ] Write `tests/test_build_ac_workflow.py`:
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

- [ ] Author `templates/agents/build-ac.md`:
  - Frontmatter: `name: build-ac`, `description`, `allowed-tools: Bash, Read`.
  - Body: encode the 5-step sequence from the Context section.
  - Include explicit error recovery: if `generate_ticket_from_ac.py` fails
    (AC already has a ticket), surface the existing ticket path and offer
    "build the existing ticket instead? (yes / no)".
  - Include the `--ac` flag handling: bypass ranking, propose the named AC.
  - Include depth-cap note from architect-review decision.
- [ ] Author `templates/workflows/build-ac.md`:
  - Register `/build-ac` as the user-facing slash command.
  - Map flags: `--ac <id>` (optional), `--dry-run` (print proposal, don't
    confirm or build).
  - Description: "Find and build the next most important AC in the store."
- [ ] Register `build-ac` in `config/agent_registry.json` with:
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
