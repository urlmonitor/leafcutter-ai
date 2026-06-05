---
title: "BO-400: Ticket Status as Single Source of Truth — eliminate done/ folder moves, use frontmatter status for all lifecycle decisions"
status: done
components:
  - infrastructure
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/set_ticket_status.py
  - .claude/skills/building-epics/SKILL.md
  - .claude/skills/finalize-feature-archive-check/SKILL.md
  - .claude/skills/ticket-prioritizer/SKILL.md
  - scripts/ticket_prioritizer.py
  - scripts/commit_guardian/check_ticket_signoff_parity.py
  - templates/agents/status-checker.md
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: standard
source_acs:
  - BO-400
  - BO-400a
  - BO-400a-1
  - BO-400a-1-i
  - BO-400a-2
  - BO-400a-2-i
  - BO-400a-3
  - BO-400a-4
  - BO-400a-5
  - BO-400b
  - BO-400b-1
  - BO-400b-1-i
  - BO-400b-2
  - BO-400b-2-i
  - BO-400b-3
  - BO-400c
  - BO-400c-1
  - BO-400c-1-i
  - BO-400c-2
  - BO-400c-2-i
  - BO-400c-3
  - BO-400c-4
ac_path: docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/
ac_coverage: 0/22
---

# BO-400: Ticket Status as Single Source of Truth

## Actor / Goal

As the build orchestration system, I need every lifecycle decision about a
ticket (is it ready to pick up? is it done? is it in progress?) to be
derivable from the ticket's own `status:` frontmatter field — so that
parallel worktree branches never conflict on folder structure and the system
remains auditable and testable independent of LLM behavior.

## Context

The current convention moves completed tickets into a `done/` subfolder
within their epic folder. This creates three independent problems:

1. **Parallel worktree conflicts.** When two branches are driving separate
   tickets in the same epic, both attempt `git mv` into `done/`. On merge,
   Git reports a rename conflict even though no file content has changed.

2. **Scattered state signals.** `ticket-prioritizer`, `finalize-feature-archive-check`,
   `check_ticket_signoff_parity.py`, and `building-epics` SKILL.md each use a
   different heuristic to determine whether a ticket is complete: some check
   the `done/` folder, some parse the sign-offs section, some inspect the agents
   map. There is no single authoritative field.

3. **Unmachineability.** File moves are orchestrated by the LLM generating
   `git mv` shell commands, which is fragile. A dedicated script that atomically
   updates a single frontmatter field is deterministic, testable, and auditable.

This ticket introduces `scripts/set_ticket_status.py` as the exclusive
mechanism for expressing ticket lifecycle transitions, and updates every
component that previously relied on the `done/` folder convention.

All ACs are pre-written at:
`docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/`

## Acceptance Criteria

The full Gherkin criteria are in the source AC YAML files listed in `source_acs`.
Key criteria per deliverable:

### Deliverable 1 — `scripts/set_ticket_status.py` (BO-400b)

```gherkin
# BO-400b-1: Core status update
Given a ticket at /path/to/epic/03_some_ticket.md with status: todo
When: python set_ticket_status.py --ticket /path/to/epic/03_some_ticket.md --status in_progress
Then the script locates `status:` in the YAML frontmatter block (between --- delimiters)
And replaces the value with `in_progress`
And writes the file back preserving all other frontmatter fields and all body content unchanged
And exits 0
And prints: "status: todo -> in_progress"

# BO-400b-2: Transition allow-list
Valid transitions (without --force):
  todo -> in_progress, in_progress -> done, in_progress -> todo
Same-status -> same-status (idempotent no-op, exits 0)
All other transitions require --force or exit 1 with:
  "Invalid transition: <old> -> <new> (use --force to override)"

# BO-400b-1-i: Parity guard on done transition
Given agents map contains `test-runner: needed` and `commit: needed`
When invoked with --status done (without --force)
Then exits 1 and prints:
  "Cannot set done - agents with status 'needed': test-runner, commit"
And the ticket file is NOT modified.
When invoked with --status done --force
Then prints: "status: in_progress -> done (forced, parity check skipped)"
And exits 0.

# BO-400b-2-i: Missing status field
Given ticket frontmatter has no `status:` field
When invoked with --status in_progress
Then treats absence as status: todo
And inserts `status: in_progress` into the frontmatter
And prints: "status: (absent, treated as todo) -> in_progress"

# BO-400b-3: Git staging
Given a successful status update (exit 0)
Then git add is run on the modified ticket file only
And git status --porcelain shows the file as staged-modified (M in index column)
And no staging is performed on rejected transitions or no-op same-status calls.
```

### Deliverable 2 — `building-epics` SKILL.md (BO-400a-1, BO-400a-2, BO-400c-1)

```gherkin
# BO-400a-1: Drive start
Given a ticket with status: todo and at least one agent: needed
When ticket-supervisor begins driving this ticket (before spawning the first phase agent)
Then it invokes set_ticket_status.py --ticket <path> --status in_progress
And the script updates frontmatter to status: in_progress and stages the file.

# BO-400a-1-i: Idempotent re-drive
Given a ticket already with status: in_progress (prior run incomplete)
When ticket-supervisor begins driving and calls set_ticket_status.py --status in_progress
Then the script exits 0 and prints "status: in_progress -> in_progress (no change)"
And ticket-supervisor proceeds without error.

# BO-400a-2: Drive completion
Given all agents: map entries are in {signed_off, not_needed}
When ticket-supervisor determines the ticket is done-eligible
Then it invokes set_ticket_status.py --ticket <path> --status done
And the ticket file is NOT moved (no git mv, no done/ subfolder created).

# BO-400c-1: No git mv
Then ticket-supervisor does NOT invoke git mv to move the file to done/
And the ticket file remains at its original path after completion.
```

### Deliverable 3 — `finalize-feature-archive-check` SKILL.md (BO-400a-3, BO-400c-2, BO-400c-2-i)

```gherkin
# BO-400a-3 / BO-400c-2: Frontmatter-based archive check
Given all sub-tickets have status: done in frontmatter but none have been moved to done/
When finalize-feature-archive-check runs its pre-archive validation
Then it scans ALL .md files recursively (excluding Master_Plan.md)
And reads the `status:` frontmatter field from each ticket
And reports all_clear: true
And does NOT require the existence of a done/ subfolder.

# BO-400c-2-i: Mixed-state epic (transitional)
Given done/01_ticket.md (status: done, legacy), 02_ticket.md (status: done, new),
  03_ticket.md (status: in_progress, active)
Then reports ok_count: 2, missing_count: 1,
  missing_tickets: [{path: "03_ticket.md", current_status: "in_progress"}]
  all_clear: false
And blocks the archive operation.
```

### Deliverable 4 — `ticket-prioritizer` script + SKILL.md (BO-400a-4, BO-400a-5, BO-400c-1-i)

```gherkin
# BO-400a-5: Ready set excludes in_progress
Given ticket-A (status: todo, unblocked), ticket-B (status: in_progress),
  ticket-C (status: done), ticket-D (status: todo, depends_on: [ticket-C])
When ticket-prioritizer scans the folder
Then ticket-A and ticket-D appear in the ready list
And ticket-B and ticket-C do NOT appear in the ready list.

# BO-400c-1-i: Backward compatibility with done/ subfolder
Given legacy epic with done/01_first.md, done/02_second.md (status: done)
  and 04_incomplete.md (status: todo) at epic root
When /build-feature computes the dependency graph
Then it scans both epic root AND done/ subfolder recursively
And correctly identifies the three done tickets and one remaining ticket
And emits no error or warning about the done/ subfolder existing.
```

### Deliverable 5 — `check_ticket_signoff_parity.py` (BO-400c-3)

```gherkin
# BO-400c-3: Prohibit done-folder moves via pre-commit hook
Given a staged commit that moves a ticket from EPIC-Foo/03_ticket.md
  to EPIC-Foo/done/03_ticket.md
When check_ticket_signoff_parity.py runs as a pre-commit hook
Then it exits 1 and prints:
  "Prohibited: ticket file moved into done/ subfolder.
   Use set_ticket_status.py --status done instead.
   File: EPIC-Foo/done/03_ticket.md"
And the commit is blocked.

Given a staged commit that modifies frontmatter to set status: done (no file move)
When the hook runs
Then the done-folder-move check passes
And the existing parity rule is evaluated:
  tickets with status: done must not have `needed` or `failed` in agents map.
```

### Deliverable 6 — `templates/agents/status-checker.md` (BO-400c-4)

```gherkin
# BO-400c-4: status-checker close-out
Given a ticket driven to completion (all agents in {signed_off, not_needed})
When status-checker performs the two-pass close-out
Then it invokes set_ticket_status.py --ticket <path> --status done
And it does NOT invoke git mv
And it flips pull-request: needed -> signed_off in the agents map
And the ticket file remains at its original path.
```

## AC Coverage

| AC ID | Level | Title | Agent |
|-------|-------|-------|-------|
| BO-400 | L0 | Know exactly which tickets are in progress, done, or waiting — without moving files | — |
| BO-400a | L1 | Ticket frontmatter status drives all lifecycle decisions | — |
| BO-400a-1 | L2 | ticket-supervisor sets status to in_progress at drive start | llm-expert |
| BO-400a-1-i | L3 | Ticket already in_progress from a previous failed run | llm-expert |
| BO-400a-2 | L2 | ticket-supervisor sets status to done when all agents complete | llm-expert |
| BO-400a-2-i | L3 | Parity violation: status done but agents map has needed entries | llm-expert |
| BO-400a-3 | L2 | finalize-feature reads status from frontmatter, not folder position | llm-expert |
| BO-400a-4 | L2 | Dependency graph uses frontmatter status to determine completed tickets | python-coder |
| BO-400a-5 | L2 | ticket-prioritizer excludes in_progress tickets from the ready set | python-coder |
| BO-400b | L1 | A dedicated script manages all ticket status transitions | — |
| BO-400b-1 | L2 | set_ticket_status.py accepts a ticket path and target status | python-coder |
| BO-400b-1-i | L3 | Script refuses done when agents map has needed entries | python-coder |
| BO-400b-2 | L2 | Script validates status transitions against an allow-list | python-coder |
| BO-400b-2-i | L3 | Script handles missing status field gracefully | python-coder |
| BO-400b-3 | L2 | Script stages the modified ticket file after a successful update | python-coder |
| BO-400c | L1 | The done/ subfolder convention is deprecated | — |
| BO-400c-1 | L2 | ticket-supervisor does not move files to done/ | llm-expert |
| BO-400c-1-i | L3 | Backward compatibility: old epics with done/ subfolder still work | python-coder |
| BO-400c-2 | L2 | finalize-feature-archive-check scans by frontmatter, not folder position | llm-expert |
| BO-400c-2-i | L3 | Mixed state: some tickets in done/ folder, some with status: done at root | llm-expert |
| BO-400c-3 | L2 | Parity guard rejects commits that move ticket files into epic subfolders | python-coder |
| BO-400c-4 | L2 | status-checker close-out calls set_ticket_status.py instead of git mv | llm-expert |

## Sign-offs

- [x] architect-review — 2026-06-05 12:00
- [x] test-writer — 2026-06-05 12:15
- [x] python-coder — 2026-06-05 12:45
- [x] llm-expert — 2026-06-05 13:00
- [x] test-runner — 2026-06-05 13:15
- [x] pr-reviewer — 2026-06-05 13:30
- [x] commit — 2026-06-05 13:45
- [x] pull-request — 2026-06-05 13:50

## Comments

### 2026-06-05 13:50 — pull-request (status: ok)
feedback-id: fb_2026-06-05_a7b246fd
completion_manifest:
  branch_pushed: true
  pr_opened: true
  pr_url_recorded: true
Branch feature/bo400-ticketstatussourceoftruth pushed to origin. PR #66 opened at https://github.com/urlmonitor/leafcutter-ai/pull/66. No conflicts detected on push.

### 2026-06-05 13:45 — commit (status: ok)
feedback-id: fb_2026-06-05_2fa05b4e
completion_manifest:
  files_staged_by_explicit_path: true
  commit_created: true
  no_cross_worktree_pollution: true
Committing 12 in-scope files staged by explicit path: scripts/set_ticket_status.py (new), scripts/ticket_prioritizer.py (new), scripts/commit_guardian/_signoff_parity_checks.py (modified), scripts/commit_guardian/check_ticket_signoff_parity.py (modified), templates/agents/status-checker.md (modified), templates/skills/building-epics/SKILL.md (modified), templates/skills/finalize-feature-archive-check/SKILL.md (modified), templates/skills/ticket-prioritizer/SKILL.md (modified), unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py (new), unit_tests/commit_guardian/test_set_ticket_status.py (new), unit_tests/test_ticket_prioritizer_status_filter.py (new), tickets/00_inbox/TICKET-20260605-BO400-TicketStatusSourceOfTruth.md (modified). No unrelated files staged.

### 2026-06-05 13:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_aa3a89f8
completion_manifest:
  code_quality_verified: true
  docstrings_present: true
  error_handling_policy_followed: true
  file_size_limits_respected: true
  tests_green: true
Approved. All 12 changed files reviewed. set_ticket_status.py (271 effective lines) and ticket_prioritizer.py (297 effective lines) both within the 400-line budget after docstring stripping. Module docstrings with MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE present on both new scripts. Error handling policy followed — all I/O wrapped in try/except OSError, no bare excepts, no silent swallows. All 15 BO-400 tests pass (1 skipped for git context). Skill and template updates are accurate, internally consistent, and reference BO-400 AC IDs correctly.

### 2026-06-05 13:15 — test-runner (status: ok)
feedback-id: fb_2026-06-05_4583f655
completion_manifest:
  tests_executed: true
  results_verified: true
  regressions_checked: true
15 passed, 1 skipped across 3 BO-400 test files. The skipped test (test_git_staging_on_success) requires a tracked git file context and is expected to skip in the test environment. 9 pre-existing failures in test_check_ac_limits.py and test_build_precommit.py confirmed unrelated to BO-400 changes (those scripts do not exist in this worktree and the failures predate this branch). No regressions introduced.

### 2026-06-05 13:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  building_epics_skill_updated: true
  finalize_feature_archive_check_updated: true
  ticket_prioritizer_skill_updated: true
  status_checker_template_updated: true
Updated all four deliverables. building-epics SKILL.md: added §2.0.5 drive-start set_ticket_status.py call (BO-400a-1/a-1-i), updated done-marking recipe and §1.5 close-out to avoid git mv (BO-400a-2/c-1), updated §7.2 archival gate to scan by frontmatter status (BO-400a-3). finalize-feature-archive-check SKILL.md: replaced done/-subfolder-only scan with recursive all-.md scan and set_ticket_status.py auto-fix (BO-400a-3/c-2/c-2-i). ticket-prioritizer SKILL.md: full rewrite documenting status-field lifecycle, in_progress exclusion, and legacy done/ backward compat (BO-400a-4/a-5/c-1-i). status-checker.md: replaced git mv with set_ticket_status.py in both closing protocol and auto-close trigger (BO-400c-4). Note: llm-expert is not in feedback_categories.yaml allowed_writers list — feedback submission failed, using (submit-failed).

### 2026-06-05 12:45 — python-coder (status: ok)
feedback-id: fb_2026-06-05_0c262c1d
completion_manifest:
  set_ticket_status_implemented: true
  ticket_prioritizer_implemented: true
  done_folder_move_prohibition_added: true
  all_red_baseline_tests_green: true
  error_handling_policy_followed: true
Implemented all three deliverables. set_ticket_status.py: targeted YAML line-replacement (no yaml.dump round-trip), ALLOWED_TRANSITIONS frozenset, parity check on done transitions, graceful git-not-available handling. ticket_prioritizer.py: get_ready_tickets() with status-field filter (excludes in_progress/done/blocked/deferred), dependency resolution via frontmatter status:, backward-compat for legacy done/ subfolders. _check_done_folder_move(): added to _signoff_parity_checks.py and wired into _validate_ticket_content() as first check. All 13 red-baseline tests now green (8 set_ticket_status, 1 parity_done_folder, 4 prioritizer).

### 2026-06-05 12:15 — test-writer (status: ok)
feedback-id: fb_2026-06-05_49cb0e97
completion_manifest:
  tests_written: true
  tests_confirmed_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: test_todo_to_in_progress_updates_frontmatter
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 0 — script not found (set_ticket_status.py does not exist yet)"
  - test_name: test_same_status_is_noop
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 0 — script not found"
  - test_name: test_done_transition_blocked_by_needed_agents
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 1 — script not found"
  - test_name: test_done_transition_forced_bypasses_parity
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 0 — script not found"
  - test_name: test_invalid_transition_rejected_without_force
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 1 — script not found"
  - test_name: test_missing_status_field_treated_as_todo
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 0 — script not found"
  - test_name: test_no_staging_on_noop
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 0 — script not found"
  - test_name: test_no_staging_on_rejection
    file: unit_tests/commit_guardian/test_set_ticket_status.py
    error: "AssertionError: 2 != 1 — script not found"
  - test_name: test_done_folder_move_blocked
    file: unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
    error: "AssertionError: False is not true — Prohibited check not yet in _validate_ticket_content"
  - test_name: test_in_progress_excluded_from_ready
    file: unit_tests/test_ticket_prioritizer_status_filter.py
    error: "FileNotFoundError: scripts/ticket_prioritizer.py does not exist yet"
  - test_name: test_done_excluded_from_ready
    file: unit_tests/test_ticket_prioritizer_status_filter.py
    error: "FileNotFoundError: scripts/ticket_prioritizer.py does not exist yet"
  - test_name: test_done_satisfies_depends_on
    file: unit_tests/test_ticket_prioritizer_status_filter.py
    error: "FileNotFoundError: scripts/ticket_prioritizer.py does not exist yet"
  - test_name: test_legacy_done_subfolder_scanned
    file: unit_tests/test_ticket_prioritizer_status_filter.py
    error: "FileNotFoundError: scripts/ticket_prioritizer.py does not exist yet"
13 failing tests across 3 test files. 1 test skipped (test_git_staging_on_success requires git context). 2 tests pass immediately (guard-rail tests for existing parity behavior). All expected red-baseline entries represent unimplemented production code. Python-coder must implement set_ticket_status.py, ticket_prioritizer.py, and the done-folder-move prohibition in _signoff_parity_checks.py to turn these green.

### 2026-06-05 12:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_64abc1e6
completion_manifest:
  cli_interface_confirmed: true
  parity_check_design_confirmed: true
  backward_compat_strategy_confirmed: true
Impact classification: LARGE (7 files, multiple cross-module boundaries: scripts/, templates/agents/, .claude/skills/). No always-large trigger fired (no Alembic migration, no hypertable change, no public API change, no ADR contract change). requires_adr: false — the policy change is fully documented in the SKILL.md updates and ticket body; no separate ADR needed at this time. All three interface contracts confirmed: CLI `--ticket <path> --status <status> [--force]` is consistent across all callers; frontmatter YAML is the correct parity-check source (not Sign-offs body); backward-compat strategy (recursive scan, absent status treated as done in legacy done/ folders) is sound. Approved for python-coder and llm-expert to proceed.

## Implementation Tasks

### architect-review

Review the interface contract for `set_ticket_status.py` before any coding begins:

- [x] Confirm the CLI interface: `--ticket <absolute-path> --status <todo|in_progress|done> [--force]`
  is consistent with how `building-epics` SKILL.md will invoke it and how
  `status-checker.md` will call it.
- [x] Confirm the agents-map parity check design: the script reads `agents:` from
  frontmatter YAML, not from the `## Sign-offs` body section. This is intentional —
  the frontmatter is the machine-readable source; the body section is human-readable.
  Verify this does not conflict with existing parity tooling.
- [x] Confirm backward-compatibility strategy for epics that already have tickets
  in a `done/` subfolder: the scanner should scan recursively and treat their
  frontmatter `status:` as authoritative. If a legacy ticket in `done/` lacks a
  `status:` field, treat it as `status: done` (the only reason it would be in that
  folder under the old convention).

**Delivers to python-coder:** Approved interface contract for `set_ticket_status.py`.
**Delivers to llm-expert:** Approved invocation contract for SKILL.md updates.

### test-writer

Write tests before `python-coder` begins implementation.

- [x] `unit_tests/commit_guardian/test_set_ticket_status.py`:
  - `test_todo_to_in_progress_updates_frontmatter`: write temp ticket with `status: todo`,
    invoke script, assert frontmatter reads `status: in_progress`, body unchanged.
  - `test_same_status_is_noop`: invoke with current status == target, assert file unchanged,
    exit 0, stdout contains "(no change)".
  - `test_done_transition_blocked_by_needed_agents`: ticket with `test-runner: needed`,
    invoke with `--status done`, assert exit 1, file unchanged.
  - `test_done_transition_forced_bypasses_parity`: same ticket, invoke with `--force`,
    assert exit 0, status updated.
  - `test_invalid_transition_rejected_without_force`: `done -> in_progress`, assert exit 1.
  - `test_missing_status_field_treated_as_todo`: ticket with no `status:` field,
    invoke with `--status in_progress`, assert `status: in_progress` inserted.
  - `test_git_staging_on_success`: successful update, assert `git status --porcelain`
    shows staged-modified.
  - `test_no_staging_on_noop`: no-op call, assert file not staged.
  - `test_no_staging_on_rejection`: rejected transition, assert file not staged.

- [x] `unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py`:
  - `test_done_folder_move_blocked`: stage a rename from `EPIC-Foo/03.md` to
    `EPIC-Foo/done/03.md`, assert hook exits 1 with the expected error message.
  - `test_frontmatter_done_without_move_passes`: stage a modification setting
    `status: done` in frontmatter (all agents signed_off), assert hook exits 0.
  - `test_non_done_subfolder_move_not_blocked`: rename to a subfolder NOT named
    `done/`, assert hook does not block on this new rule.

- [x] `unit_tests/test_ticket_prioritizer_status_filter.py`:
  - `test_in_progress_excluded_from_ready`: assert ticket with `status: in_progress`
    is not in ready set even when unblocked.
  - `test_done_excluded_from_ready`: assert ticket with `status: done` not in ready.
  - `test_done_satisfies_depends_on`: ticket D depends on C; C has `status: done`;
    assert D is in ready set.
  - `test_legacy_done_subfolder_scanned`: fixture with `done/old.md` (status: done);
    assert it is included in the completed set and excluded from ready.

**Depends on architect-review:** Approved interface contracts.

### python-coder

**Deliverable 1 — `scripts/set_ticket_status.py`**

CLI: `python scripts/set_ticket_status.py --ticket <path> --status <todo|in_progress|done> [--force]`

Implementation requirements (derived from BO-400b-1, BO-400b-1-i, BO-400b-2, BO-400b-2-i, BO-400b-3):

1. Read the ticket file. Parse the YAML frontmatter block (text between the first
   and second `---` lines). Do NOT use `yaml.dump` for round-trip — use targeted
   line replacement to preserve field order and formatting.

2. Locate the `status:` field. If absent, treat as `todo` and note "(absent, treated
   as todo)" in the stdout message.

3. Validate the transition using the allow-list (as data, not scattered conditionals):
   ```python
   ALLOWED_TRANSITIONS = {
       ("todo",        "in_progress"),
       ("in_progress", "done"),
       ("in_progress", "todo"),
   }
   FORCE_ALLOWED_TRANSITIONS = {
       ("todo",  "done"),
       ("done",  "todo"),
       ("done",  "in_progress"),
   }
   ```
   Same-status pairs are always allowed (idempotent no-op). Reject all others without
   `--force` with: `"Invalid transition: <old> -> <new> (use --force to override)"`.

4. For `done` transitions without `--force`: parse the `agents:` map from frontmatter.
   Find all entries with value `needed`. If any found, exit 1 with:
   `"Cannot set done - agents with status 'needed': <comma-separated list>"`.

5. Write the updated file only if the transition is not a no-op. Preserve all other
   frontmatter fields and all body content below the closing `---` delimiter.

6. After a successful write, run `subprocess.run(["git", "add", str(ticket_path)], ...)`.
   Handle the case where the file is not tracked by git gracefully (warning, not error).

7. Print to stdout: `"status: <old> -> <new>"` (or the appropriate variant for no-op
   and forced transitions).

8. Follow the project error handling policy: all file I/O wrapped in `try/except OSError`.
   No bare excepts. No silent swallows.

9. Follow the pattern established by `scripts/commit_guardian/` scripts for structure,
   docstrings, and `DECISION HISTORY` entry.

- [x] Implemented `scripts/set_ticket_status.py` with all requirements above.

**Deliverable 2 — `scripts/ticket_prioritizer.py`** (BO-400a-4, BO-400a-5)

Modify the prioritizer to:

1. Filter by `status:` frontmatter field, not folder position. The ready set
   must exclude any ticket with `status: in_progress` (already being driven)
   or `status: done` (completed). Tickets with a missing `status:` field are
   treated as `status: todo`.

2. Dependency resolution: a ticket's `depends_on` is satisfied when all
   referenced tickets have `status: done` in their frontmatter. The current
   folder-based check must be replaced.

3. Backward compatibility: scan recursively. Tickets found in a `done/`
   subfolder without a `status:` field are treated as `status: done`
   (the only reason they would be there under the old convention).

4. Performance: complete dependency graph computation in <500ms for epics
   with up to 50 tickets (BO-400a-4 IT requirement).

- [x] Implemented `scripts/ticket_prioritizer.py` with `get_ready_tickets()` function.

**Deliverable 3 — `scripts/commit_guardian/check_ticket_signoff_parity.py`** (BO-400c-3)

Add two new checks to the existing pre-commit hook:

1. **Done-folder move detection**: inspect staged files via `git diff --cached
   --name-status`. For each rename (R) or add (A) + delete (D) pair where the
   destination path matches the pattern `*/done/*.md` inside an epic folder,
   emit:
   ```
   Prohibited: ticket file moved into done/ subfolder.
   Use set_ticket_status.py --status done instead.
   File: <destination_path>
   ```
   and exit 1. Do not block moves that are NOT into a `done/` subfolder.

2. **Frontmatter status parity rule**: for any staged ticket file modification
   where the resulting frontmatter has `status: done`, verify that no agent
   in the `agents:` map has value `needed` or `failed`. If any are found,
   emit a parity violation and exit 1.

Both checks must complete within the existing hook time budget (<5 seconds).
Must run as additions to the existing hook, not as a separate hook file.

- [x] Added `_check_done_folder_move()` to `_signoff_parity_checks.py` and wired into `_validate_ticket_content()`.

**Depends on test-writer:** Tests must exist before implementation begins.
**Depends on architect-review:** Approved interface contracts.

### llm-expert

Update four skill/template files to replace the `done/` folder convention with
`set_ticket_status.py` invocations.

- [x] **Deliverable 1 — `templates/skills/building-epics/SKILL.md`** (BO-400a-1, BO-400a-2, BO-400c-1): Added §2.0.5 drive-start status transition; updated §1.5 close-out to use set_ticket_status.py; updated §7.2 archival gate to scan by frontmatter status; replaced git mv guidance with BO-400c-1 note.

- [x] **Deliverable 2 — `templates/skills/finalize-feature-archive-check/SKILL.md`** (BO-400a-3, BO-400c-2, BO-400c-2-i): Replaced done/-subfolder-only scan with recursive all-.md scan; updated auto-fix to use set_ticket_status.py; added backward-compat rule for legacy done/ tickets without status field; updated edge-case table.

- [x] **Deliverable 3 — `templates/skills/ticket-prioritizer/SKILL.md`** (BO-400a-4, BO-400a-5): Rewrote skill to document status-field-based lifecycle table; in_progress exclusion; done detection; backward-compat section for legacy done/ subfolders.

- [x] **Deliverable 4 — `templates/agents/status-checker.md`** (BO-400c-4): Replaced git mv in closing protocol and auto-close trigger with set_ticket_status.py invocations; added non-zero exit as blocker note.

**Depends on python-coder:** The script CLI interface must be finalised before
SKILL.md and template updates can document it accurately.

## Risk & Safety

- Touches money? No.
- Touches data? The script modifies ticket `.md` files in-place. It uses targeted
  line replacement (not YAML round-trip) to preserve field order. The `--force`
  flag bypasses parity checks but always requires explicit invocation.
- Reversibility? The frontmatter `status:` field is a one-line change. Reverting
  to `done/` folder convention requires re-adding `git mv` instructions to SKILL.md
  and removing the done-folder block from the parity guard.
- Backward compatibility? Epics that already have tickets in `done/` subfolders
  continue to work: the scanner reads recursively and treats frontmatter `status:`
  as authoritative (BO-400c-1-i). Tickets in `done/` without a `status:` field
  are treated as `done` for backward compatibility.
- Risk of regressions: medium. `ticket_prioritizer.py` and `building-epics` SKILL.md
  are on the hot path of every `/build-feature` run. Test suite must cover both the
  new status-field path and the legacy done-subfolder backward-compat path before
  any SKILL.md changes land.
- The parity guard addition to `check_ticket_signoff_parity.py` must not increase
  hook runtime above the 5-second budget. Use `git diff --cached --name-status`
  (not `git diff --cached --diff-filter=R`) to stay within that budget.
