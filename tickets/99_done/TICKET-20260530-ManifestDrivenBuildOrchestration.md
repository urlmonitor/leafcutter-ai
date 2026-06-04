---
title: "Refactor /build-feature orchestration into a script-driven manifest system"
status: done
components:
  - build_pipeline
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - templates/scripts/setup_ticket_worktree.py
  - templates/workflows/build-feature.md
  - .gitignore
  - unit_tests/test_build_workflows.py
agents:
  architect-review: needed
  adr-author: needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Refactor /build-feature orchestration into a script-driven manifest system

## Actor / Goal

In order to make `/build-feature` orchestration reliable, testable, and
resumable, we need to move all orchestration logic out of the ~420-line prose
skill file and into `setup_ticket_worktree.py` (or a companion script) so that
the agent follows a machine-generated manifest instead of interpreting prose at
runtime.

## Context

`templates/workflows/build-feature.md` is currently ~420 lines of procedural
prose that the agent must interpret at runtime to decide: Is this an epic or a
single ticket? Which tickets are ready? What step comes next? This approach has
three compounding problems:

1. **Non-determinism** — two agent sessions reading the same prose can make
   different routing decisions (e.g. what counts as a "ready" ticket when a
   dependency is `in_progress` vs `done`).
2. **Non-testability** — the dependency-resolution and step-ordering logic lives
   inside a natural-language document; there is no unit-test harness that can
   exercise it.
3. **Fragile resume** — when context is compressed mid-run, the agent must
   re-interpret the full prose from scratch. A manifest file on disk can be read
   in one line.

`setup_ticket_worktree.py` already exists and handles worktree creation and
ticket promotion (`setup-ticket` and `create-only` subcommands). This ticket
extends it with a `plan` subcommand that emits a `.build-progress.json` manifest
to the worktree root. The skill prose shrinks to ~20 lines: "run the script,
read the manifest, execute each pending step, update status after each."

The existing lock file protocol (`.build-feature.lock`, `.epic-commit-lock`)
is **unchanged** — the manifest complements it and does not replace it.

Related: the branching policy in `setup_ticket_worktree.py` (branch from local
`main`, not `origin/main`) already encodes the correct behaviour for stale
worktrees described in `build-feature-ops-notes/SKILL.md` KI-1. The manifest
generator must respect this same policy when computing the ticket list.

## Architecture Plan

### ADRs

- ADR-007: Manifest-driven orchestration for /build-feature — captures the
  decision to replace prose-interpreted skill with a script-generated step plan,
  the manifest schema, the resumability contract, and the trade-offs vs.
  alternatives (e.g. keeping all logic in prose, using a database).
  Target path: `docs/architecture/adrs/ADR-007-manifest-driven-build-orchestration.md`

## Acceptance Criteria

```gherkin
Given a repo with an epic folder at tickets/00_inbox/epics/EPIC-Foo/
When setup_ticket_worktree.py plan --target EPIC-Foo is run
Then a .build-progress.json file is written to the worktree root
  AND it contains an ordered steps array with status "pending" for each ready ticket
  AND each step includes: agent_dispatch_target, ticket_path, description, depends_on
  AND tickets whose depends_on references an incomplete ticket are excluded from the first batch

Given a repo with a single standalone ticket at tickets/00_inbox/TICKET-XYZ.md
When setup_ticket_worktree.py plan --target tickets/00_inbox/TICKET-XYZ.md is run
Then a .build-progress.json manifest is written with a single-step plan
  AND the step's agent_dispatch_target is "ticket-supervisor"

Given .build-progress.json exists with step 2 status "done" and step 3 status "pending"
When the agent reads the manifest at resume time
Then it skips step 2 and begins executing step 3 without re-running any prior step

Given templates/workflows/build-feature.md is refactored to the manifest-reader form
When /build-feature is invoked via Claude Code
Then the skill runs the plan subcommand, reads the manifest, and executes pending steps
  AND no orchestration decision is made by reading prose — all routing comes from the manifest

Given .build-progress.json is written to the worktree root
When git status is run in the worktree
Then .build-progress.json does not appear in tracked files (it is gitignored)
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Add a `plan` subcommand to `setup_ticket_worktree.py` that:
  - Accepts `--target <epic-name-or-ticket-path>` and `--worktree-root <path>`
  - Detects epic vs single-ticket by checking for a `Master_Plan.md` in the target
  - For epics: reads all sub-ticket frontmatter, resolves `depends_on` chains,
    computes the initial "ready batch" (tickets with no unmet dependencies), and
    emits ordered steps
  - For single tickets: emits a single-step manifest with `agent_dispatch_target: ticket-supervisor`
  - Writes `.build-progress.json` to `--worktree-root` (default: current working directory)
  - Outputs a one-line JSON summary to stdout (consistent with existing subcommand convention)
  - Is idempotent: if `.build-progress.json` already exists and has `status: done` steps,
    preserve them and only re-plan pending steps
- [ ] Define the `.build-progress.json` schema as a Python `TypedDict` or dataclass at
  the top of the script (serves as the authoritative schema reference for the ADR)
- [ ] Add a `step-done <step_index>` subcommand that updates a step's status to `done`
  in the manifest (called by the skill after each agent dispatch completes)
- [ ] Update `templates/workflows/build-feature.md` to ~20 lines:
  - Step A: write lock file (unchanged)
  - Step B: run `setup_ticket_worktree.py plan --target $ARGUMENTS`
  - Step C: loop — read manifest, find first pending step, dispatch agent, call `step-done`
  - Step D: delete lock file on exit (unchanged)

### test-writer

- [ ] `test_plan_epic_detects_ready_batch` — given a mocked epic folder with three
  sub-tickets where ticket 2 depends on ticket 1, verify that only ticket 1 appears
  in the initial ready batch (ticket 2 is excluded until ticket 1 is `done`)
- [ ] `test_plan_single_ticket_produces_one_step` — given a single ticket path, verify
  the manifest contains exactly one step with `agent_dispatch_target: ticket-supervisor`
- [ ] `test_plan_is_idempotent` — run `plan` twice on the same target; verify the
  second run does not overwrite `done` steps from the first run
- [ ] `test_step_done_updates_status` — call `step-done 0` and verify step 0 transitions
  from `pending` to `done` in the written manifest
- [ ] `test_plan_excludes_blocked_tickets` — a ticket whose `depends_on` references a
  ticket that is `status: todo` (not `done`) must not appear in the initial batch
- [ ] Target directory: `unit_tests/` (new file: `test_setup_ticket_worktree_plan.py`)

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The manifest file is ephemeral and gitignored — if the format is
  wrong, delete it and re-run `plan`. The skill rewrite is the only irreversible
  change; the old prose must be archived in a comment block or git history before
  deletion so it can be recovered if the manifest approach is rolled back.
- Shared contract risk: `setup_ticket_worktree.py` is called by multiple skill files
  (build-single-ticket, worktree-agent). The new `plan` subcommand is additive; it
  does not modify existing subcommand behaviour. Low risk.
- `.gitignore` update: adding `.build-progress.json` to the root `.gitignore` is safe
  and consistent with the existing `.build-feature.lock` and `.epic-commit-lock`
  ephemeral-file pattern.
