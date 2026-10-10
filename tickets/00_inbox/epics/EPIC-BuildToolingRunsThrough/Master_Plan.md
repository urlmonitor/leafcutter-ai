---
title: "EPIC: Build tooling runs through — one run builds a ticket"
type: epic
status: in_progress
components:
  - build_orchestration
  - testing_quality
  - supervisor_system
  - ac_store
  - commit_guardian
  - ac_driven_dev
  - ticket_creation_pipeline
created: 2026-10-06
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
change_target:
  - pipeline
  - code
  - config
  - prompt
  - docs
risk_surface: contract_boundary
---

# EPIC: Build tooling runs through — one run builds a ticket

## Goal

The DK-400 E1 build (EPIC-ABundledRequestThatRoutingTurnsAwayIs) needed about 10
`/build-feature` runs to finish **one** ticket (01, DK-400a-1). Each run stopped on a
tooling defect, not on the ticket's own work. Every defect below was verified in the
code. This epic fixes them so that one run carries a ticket, and an epic, as far as
the work allows.

| Defect | What happened in the DK-400 E1 build | Ticket |
|---|---|---|
| The gate hard-codes `python3` | In a Windows venv `python3` is the Store 3.11 interpreter. Every new test ERRORed, and the verdict said `no_red_outcome_among_new_tests`, hiding the cause. | 01 |
| The driver halts after every handoff | A valid handoff re-dispatched the target inline, then always returned `blocked / cross_agent` ("re-run /build-feature"). The inline dispatch also skipped the test guard, the red-baseline gate and the record check. | 02 |
| Red-baseline gate deadlock on re-run | The gate's pass lived only in memory. After any halt, a re-run found the coder's uncommitted code made the tests green, so the gate halted the ticket as `all_new_tests_green_at_baseline`, and it could not move. | 03 |
| A halted ticket stops independent work | One halt ended every later batch and look. Almost every DK ticket shares a file, so each sat in its own batch and one halt stopped everything. | 04 |
| Generated tickets get `status-checker: needed` | The guardrail matrix listed status-checker for `config` / `model` with `contract_boundary` / `cost`. The driver sorts it to priority 1, where it handed off and looped. | 05 |
| AC gates mark a composite AC done | The fulfillment gate set DK-400a-1 to `done` on diff evidence alone, while its `covered_by` held only child AC ids. | 06 |
| `goal_to_epic --ids` ignores `--dry-run` | A "dry run" wrote the epic and the AC `implemented_by` back-references. | 07 |
| `expects_from` edges lose the epic prefix | DK-400a-3 and DK-400a-4 got the loose inbox name in `depends_on`. The build driver could not resolve it, so the tickets were withheld. They were fixed by hand in scaffold commit 7d593952e. | 08 |
| Master_Plan fails both frontmatter gates | The generated Master_Plan lacked `title`, `depends_on`, `requires_*`, `change_target` and `risk_surface`, so it had to be hand-edited before it could be committed. | 09 |

Source of truth for scope, files and tests: the build-tooling fix design
(sections 1a-6c and the ticket split in section 7), with the user's decisions
F1-F6 of 2026-10-06.

## AC amendments (user decisions 2026-10-06)

The business-analyst applied these on this branch, staged with this epic. They are
the AC text the tickets implement:

- **F1, BO-3000a**: a handoff re-dispatches its target, then the ticket continues. It halts only on a repeated pair, the per-ticket cap (3), or a target the record cannot confirm. Ticket 02.
- **F2, TQ-500f-3-ii**: the reader records its own pass in the ticket, and a resume reuses it under strict conditions. The test-writer's claim never substitutes. Ticket 03.
- **F3, TQ-500f-3-ii**: "no production change" tickets halt with reason `green_at_baseline`, list the green tests, and suggest setting the coder `not_needed` with a comment naming the implementing commit. There is no automatic pass. Ticket 03.
- **F4**: a halted ticket that left **staged** changes stops the run and names the paths. Ticket 04.
- **F5**: replace status-checker with architect-review in the guardrail cells that listed it. Ticket 05.
- **F6, BO-202**: an AC with child ACs goes to `in_progress` until every child is done and proven. Ticket 06.
- **ACD-1200a-8-i** moved from draft to approved, so ticket 09 may be built.

## Tickets

| # | File | Description | Source AC | Depends On | Status |
|---|------|-------------|-----------|------------|--------|
| 01 | [01_TICKET-20261006-GateUsesProjectInterpreter.md](./01_TICKET-20261006-GateUsesProjectInterpreter.md) | The red-baseline gate runs under `python` in both lanes and names an unusable interpreter | TQ-500f-3-ii | — | `[ ]` |
| 02 | [02_TICKET-20261006-HandoffContinuesTheTicket.md](./02_TICKET-20261006-HandoffContinuesTheTicket.md) | A handoff runs its target through the normal loop and the ticket continues | BO-3000a | 01 | `[ ]` |
| 03 | [03_TICKET-20261006-RedBaselineVerdictRecordedAndReused.md](./03_TICKET-20261006-RedBaselineVerdictRecordedAndReused.md) | The gate records its own pass and a resume reuses it; `green_at_baseline` halt message | TQ-500f-3-ii | 01, 02 | `[ ]` |
| 04 | [04_TICKET-20261006-EpicContinuesPastHaltedTicket.md](./04_TICKET-20261006-EpicContinuesPastHaltedTicket.md) | An epic run continues past a halted ticket; staged leftovers stop it | BO-100e-4 | 02, 03 | `[ ]` |
| 05 | [05_TICKET-20261006-NoStatusCheckerOnGeneratedTickets.md](./05_TICKET-20261006-NoStatusCheckerOnGeneratedTickets.md) | Guardrail matrix: status-checker replaced by architect-review | — | — | `[ ]` |
| 06 | [06_TICKET-20261006-CompositeAcGoesInProgress.md](./06_TICKET-20261006-CompositeAcGoesInProgress.md) | A composite AC goes to `in_progress` until its children are done and proven | BO-202 | — | `[ ]` |
| 07 | [07_TICKET-20261006-IdsModeHonoursDryRun.md](./07_TICKET-20261006-IdsModeHonoursDryRun.md) | `goal_to_epic --ids --dry-run` writes nothing | ACD-1200a-3-iii | — | `[ ]` |
| 08 | [08_TICKET-20261006-ExpectsFromEdgesGetEpicPrefixes.md](./08_TICKET-20261006-ExpectsFromEdgesGetEpicPrefixes.md) | `expects_from` edges are wired with epic-prefixed ticket names | BO-2600a-5 | — | `[ ]` |
| 09 | [09_TICKET-20261006-MasterPlanPassesFrontmatterGates.md](./09_TICKET-20261006-MasterPlanPassesFrontmatterGates.md) | The generated Master_Plan passes both frontmatter gates | ACD-1200a-8-i | 07 | `[ ]` |

## Dependencies and order

```
01 (no dependencies)
02 -> 01
03 -> 01, 02
04 -> 02, 03
05 (no dependencies)
06 (no dependencies)
07 (no dependencies)
08 (no dependencies)
09 -> 07
```

- **JS lane, strictly in series: 01 → 02 → 03 → 04.** These tickets share `build-feature.js` and `build-ticket.js`, and the size ratchet is judged on every commit.
- 05 and 06 can run in parallel with everything.
- 07 and 08 can run in parallel. Ticket 08 writes its tests to a new file so the two tickets share no file. Then 09, which shares `epic_pipeline.py` with 07.
- After this epic: `tickets/00_inbox/TICKET-20261005-GoalToEpicKeepsOutOfEpicDependencies.md`. It extends the code that 07 and 08 change, and its out-of-epic report must include `expects_from`-only edges.

## Constraints that apply to several tickets

- **Twin drivers.** `templates/workflows-js/build-feature.js` and `templates/workflows-js/build-ticket.js` must stay in sync. Any change to shared logic lands in both, in the same commit.
- **File-size ratchet (GE-127b-1, GE-127f-2).** Measured lengths at bc8e6c62 against the limits:
  - `build-feature.js`: 2964 / 1000;
  - `build-ticket.js`: 1647 / 1000;
  - `fast-lane-ship.js`: 1673 / 1000;
  - several Python files over 400 are named in each ticket.

  For a file already over its limit, check-file-size accepts the staged file only if its measured length is at most `max(limit, previous − gross measured lines added)`. A changed line counts as an added line. So "net-zero" is not enough: the file must get shorter by at least the number of lines added or changed. `//` and `#` comment lines are measured; `/* */` and triple-quoted content are not. Put decision logic in Python where possible, as `heavy_lane_gate` does.
- **Build mirrors.** After any `templates/` edit, run `python scripts/build.py` and stage every tracked output it changes, or check-build-drift fails.
- **Lane parity (TQ-500f-3-ii).** The heavy lane (both twins) and the fast lane (`fast-lane-ship.js`) run the same red-baseline reader with the same command form, and give the same verdict whenever the reader runs.

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architect-review | 02, 03, 04 |
| test-writer | 01-09 |
| python-coder | 01-09 |
| llm-expert | 02, 04, 06 |
| test-runner | 01-09 |
| documentation-expert | 03, 04 |
| pr-reviewer | 01-09 |
| commit | 01-09 |
| pull-request | none (the epic opens one PR) |
| status-checker | none |

## Out of Scope

- A configurable `{{config.python_command}}` key. It would have to cover the hooks in `templates/settings.json` too, so it needs its own ticket.
- Migrating tickets that were already generated with `status-checker: needed`. The DK tickets were fixed by hand.
- Out-of-epic dependency reporting: `TICKET-20261005-GoalToEpicKeepsOutOfEpicDependencies`.
- The `permits_shell: false` mismatch for the gate's status-checker executor (KI-BO-20260927).

## Comments

_(Append-only log — leave blank when authoring.)_
