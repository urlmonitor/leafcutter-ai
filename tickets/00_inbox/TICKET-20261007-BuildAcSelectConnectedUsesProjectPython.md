---
title: "build-ac: run select_connected under the project's python, not python3"
status: todo
components:
  - ac_driven_dev
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: prompt
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build-ac
  - interpreter
  - windows
  - portability
last_updated: 2026-10-07
files_touched:
  - templates/agents/build-ac.md
  - unit_tests/agents/test_build_ac_select_connected_interpreter.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  llm-expert: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# build-ac: run select_connected under the project's python, not python3

## Actor / Goal
In order that `/build-ac` can resolve an AC's connected build set on a standard Windows venv, we
need its `select_connected` call to use the project's interpreter (`python`), as the three lane
drivers do since EPIC-BuildToolingRunsThrough ticket 01. Then the step runs with the project's
packages instead of failing on import.

## Context
- **The call.** Step 2b.1 of `templates/agents/build-ac.md:333` runs
  `python3 {{config.output_root}}/scripts/build_orchestration/fast_lane.py select_connected --exclude-structural-parent --ac <TOP_AC.id> --ac-root docs/acceptance-criteria`.
  The deployed copy `.claude/agents/build-ac.md:279` has the same line. It is gitignored build output
  that `scripts/build.py` regenerates.
- **The trap.** Ticket 01 (`tickets/00_inbox/epics/EPIC-BuildToolingRunsThrough/01_TICKET-20261006-GateUsesProjectInterpreter.md`,
  Context) fixed it in the lane drivers. A standard Windows venv has `python.exe` but no `python3.exe`,
  so `python3` resolves to a system interpreter (the Windows Store 3.11 in the DK-400 build) without
  the project's packages. Ticket 01 also records that `python` is already the project's interpreter
  convention.
- **Why this call fails.** `fast_lane.py` imports `_fl_lifecycle` at module load (:123), and
  `_fl_lifecycle` imports `yaml` (`scripts/build_orchestration/_fl_lifecycle.py:29`). On an
  interpreter without PyYAML, `select_connected` fails before it runs. The template then stops:
  "If `select_connected` exits non-zero: surface the error verbatim and stop" (`build-ac.md:349`).
- **Out of ticket 01's scope.** Ticket 01's AC-6 left every other `python3` use unchanged.
- This workspace's venv happens to ship a `python3.exe`
  (`C:\Users\Hendrik\Code\leafcutter\.venv\Scripts\python3.exe`), so the trap does not fire here.
- **Analogous lines, listed so the duplication is visible.** The same template runs `python3` at
  :114, :151, :157, :257, :263, :372, :422, :499, :546, :557 and :600. They are exposed wherever the
  script they call needs a package the system interpreter lacks; `generate_ticket_from_ac.py` and
  `mark_ac_done.py` import `yaml` directly. They are out of scope here. A project-wide interpreter
  key is the `{{config.python_command}}` ticket the epic left out of scope.

## Acceptance Criteria
- [ ] AC-1: The `select_connected` command in `templates/agents/build-ac.md` starts with the interpreter token `python`, not `python3`. After `python scripts/build.py`, the deployed `.claude/agents/build-ac.md` has the same command.
- [ ] AC-2: The rest of that line (script path, subcommand, flags and stderr redirect) is unchanged, and no other line of the template changes.
- [ ] AC-3: The command as written, with `{{config.output_root}}` resolved to the deployed `.leafcutter` and run under the project's interpreter, exits 0 for a real AC id in the store and prints the connected-set JSON. This is the reachability check.

## Test Requirements

```yaml
tests:
  - name: test_select_connected_command_uses_project_python
    location: unit_tests/agents/test_build_ac_select_connected_interpreter.py
    type: unit
    covers: [AC-1, AC-2]
    description: |
      Read the template and the deployed agent file and find the select_connected command line.
      Its first token is "python"; the remainder equals today's line after "python3 ". Red today.
  - name: test_select_connected_command_runs_as_written
    location: unit_tests/agents/test_build_ac_select_connected_interpreter.py
    type: integration
    covers: [AC-3]
    description: |
      Take the command from the deployed agent file, resolve the output root, replace the leading
      "python" with sys.executable, and run it as a subprocess against the real store for a real
      AC id. Exit 0, and stdout parses as the select_connected JSON.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_select_connected_command_uses_project_python | | |
| AC-2 | test_select_connected_command_uses_project_python | | |
| AC-3 | test_select_connected_command_runs_as_written | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write `unit_tests/agents/test_build_ac_select_connected_interpreter.py`. Existing tests that read
  this step (`unit_tests/agents/test_bo_2600a_4.py`, `unit_tests/build_orchestration/test_bo_2600a_2.py`,
  `unit_tests/build_orchestration/test_bo2600b1_seam_build_ac_unaffected.py`) pin no `python3`.

### llm-expert
- [ ] `templates/agents/build-ac.md:333`: `python3` → `python`. Add a DECISION HISTORY line.
- [ ] Run `python scripts/build.py` and stage every tracked output it changes (for example the
  generated agent card).

### test-runner / pr-reviewer / commit
- [ ] Run the new file and the three existing files above.

## Risk & Safety
- Touches money? No.
- Touches data? No; an agent template.
- Reversibility: revert the commit.

## Out of Scope
- The other `python3` lines in `build-ac.md` (see Context).
- A configurable interpreter key (`{{config.python_command}}`).
