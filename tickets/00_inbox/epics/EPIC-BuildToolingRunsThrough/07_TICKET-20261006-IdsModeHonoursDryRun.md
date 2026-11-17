---
title: "goal_to_epic --ids honours --dry-run and writes nothing"
status: todo
components:
  - ac_driven_dev
created: 2026-10-06
depends_on: []
priority: medium
complexity: low
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: ACD-1200a-3-iii
ac_traceability:
  id: ACD-1200a-3-iii
  path: docs/acceptance-criteria/ac-driven-dev/ACD-1200-goal-to-epic/ACD-1200a-3-iii.yaml
requires_diagram: false
requires_adr: false
change_target:
  - code
risk_surface: internal
files_touched:
  - scripts/goal_to_epic.py
  - scripts/ac_store/epic_cli.py
  - scripts/ac_store/epic_pipeline.py
  - unit_tests/test_goal_to_epic.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  status-checker: not_needed
---

# 07: goal_to_epic --ids honours --dry-run and writes nothing

## Actor / Goal

As someone planning an epic from an explicit id list, I want
`goal_to_epic.py --ids <ids> --dry-run` to show the build order and the epic it
would create, without writing anything. Then I can check the order, the name and any
cycles before committing to the real run.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 6a). Keeps ACD-1200a-3-iii: the
dry-run and the real run report a byte-identical epic name. Also serves BO-2600a-5,
the `--ids` entrypoint.

**Root cause**
- `scripts/goal_to_epic.py:257-259` calls `_run_ids_mode(args.ids, ac_store_root, inbox_dir)` and drops `args.dry_run`.
- Neither `scripts/ac_store/epic_cli.py::_run_ids_mode` (136-167) nor `scripts/ac_store/epic_pipeline.py::build_epic_from_ids` (175-267) has a dry-run parameter.
- So a "dry run" with `--ids` writes:
  - the tickets, through the generator, which also writes `implemented_by` into the AC YAML (`epic_pipeline.py:229`);
  - the `implemented_by` repoint (232), the loose-copy removal (243), the folder (251) and the Master_Plan (260).
- The `--ac` mode's dry-run (`epic_pipeline.py:114-119`) already shows the expected shape.

**Fix**
- Thread a keyword-only `dry_run=False` through `_run_ids_mode` and `build_epic_from_ids`, so fast_lane's existing call is unchanged.
- In dry-run:
  - still build the dependency graph and sort it, so a cycle exits 1 before any write;
  - derive the epic name with the same call the real run uses (ACD-1200a-3-iii);
  - print the ids in build order, and finish with `Dry-run: would create <path>`;
  - write nothing.

**Relation to `tickets/00_inbox/TICKET-20261005-GoalToEpicKeepsOutOfEpicDependencies.md`.**
This ticket is a prerequisite for that ticket's "--dry-run shows order and cycles for
--ids" bullet, and already prints the `--ids` build order. That ticket keeps `--ac`
ordering and the out-of-epic reporting.

## Constraints

- **Test placement.** `unit_tests/build_orchestration/test_bo_2600a_5.py` measures 570 / 400, so the ratchet refuses growth. The tests go in `unit_tests/test_goal_to_epic.py` (138 / 400). They run `goal_to_epic.py` as a subprocess.
- `epic_pipeline.py` measures 168 / 400. Ticket 09 also touches it and runs after this ticket.

## Acceptance Criteria

- [ ] AC-1: `goal_to_epic.py --ids <ids> --dry-run` writes nothing. No file or folder appears under the tickets inbox, and every AC YAML (including `implemented_by`) is byte-identical before and after.
- [ ] AC-2: The dry-run builds the same dependency graph and topological order as the real run, prints the ids in build order, and finishes with `Dry-run: would create <path>`.
- [ ] AC-3: The epic folder name the dry-run prints is byte-identical to the name a real run with the same ids creates. Both use the same derivation call.
- [ ] AC-4: A dependency cycle among the ids exits 1 with an `ERROR:` line during the dry-run, before any write.
- [ ] AC-5: `dry_run` is keyword-only with default `False` on `_run_ids_mode` and `build_epic_from_ids`. A real `--ids` run, and fast_lane's call, behave exactly as today.

## Test Requirements

```yaml
tests:
  - name: test_ids_dry_run_writes_nothing_under_inbox
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      Running goal_to_epic.py --ids A,B --dry-run as a subprocess against a
      temporary AC store and inbox exits 0, and the set of files under the
      inbox is identical before and after.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_ids_dry_run_leaves_ac_yamls_byte_identical
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      After the same dry-run subprocess, every AC YAML in the temporary store
      has the same bytes as before, including implemented_by.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_ids_dry_run_name_equals_real_run_name
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
    asserts: >-
      The EPIC-<name> path printed in the dry-run's "Dry-run: would create
      <path>" line is byte-identical to the folder a following real --ids run
      with the same ids creates.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_ids_dry_run_prints_ids_in_build_order
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      With ids given in the order B,A, where B depends on A, the dry-run's
      stdout lists A before B, and its last line starts with
      "Dry-run: would create".
    framework: pytest
    type: integration
    angle: boundary
  - name: test_ids_dry_run_cycle_exits_1_without_writes
    file: unit_tests/test_goal_to_epic.py
    covers:
      - ACD-1200a-3-iii
      - BO-2600a-5
    asserts: >-
      With A depending on B and B depending on A, the dry-run exits 1 with an
      "ERROR:" line on stderr, and the inbox and the AC YAMLs are unchanged.
    framework: pytest
    type: integration
    angle: failure
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_ids_dry_run_writes_nothing_under_inbox, test_ids_dry_run_leaves_ac_yamls_byte_identical | | |
| AC-2 | test_ids_dry_run_prints_ids_in_build_order | | |
| AC-3 | test_ids_dry_run_name_equals_real_run_name | | |
| AC-4 | test_ids_dry_run_cycle_exits_1_without_writes | | |
| AC-5 | existing test_bo_2600a_5.py and the fast_lane tests stay green | | |

## Implementation Tasks

### test-writer
- [x] Add the five subprocess tests to `unit_tests/test_goal_to_epic.py`, using a temporary AC store and inbox.

### python-coder
- [x] `goal_to_epic.py:257-259`: pass `dry_run=args.dry_run`.
- [x] `epic_cli._run_ids_mode` and `epic_pipeline.build_epic_from_ids`: add keyword-only `dry_run=False`. In dry-run, stop after the sort and the name derivation, print the order and the would-create line, and return.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/test_goal_to_epic.py`, `unit_tests/build_orchestration/test_bo_2600a_5.py` and the fast_lane `--ids` tests.

## Risk & Safety

- Touches money? No.
- Touches data? No. This removes unwanted writes.
- Reversibility: revert the commit.

## Out of Scope

- `--ac` mode ordering and out-of-epic reporting (TICKET-20261005).
- `expects_from` edges (ticket 08) and Master_Plan frontmatter (ticket 09).

## Comments

### 2026-10-06 16:02 — test-writer (status: ok)
feedback-id: (submit-failed)
Added class TestIdsModeHonoursDryRun (5 subprocess tests, real temp AC store via yaml.safe_dump, real generator) to unit_tests/test_goal_to_epic.py (255 lines, ratchet OK). Strict run: 4 failed, 5 passed (the 4 pre-existing tests pass).
red_baseline:
  - file: unit_tests/test_goal_to_epic.py
    function: test_ids_dry_run_writes_nothing_under_inbox
    red_reason: "AssertionError: inbox gained epics/EPIC-TestAcDryA/... (dry-run wrote tickets, Master_Plan)"
  - file: unit_tests/test_goal_to_epic.py
    function: test_ids_dry_run_leaves_ac_yamls_byte_identical
    red_reason: "AssertionError: AC YAML now has implemented_by entries (bytes changed)"
  - file: unit_tests/test_goal_to_epic.py
    function: test_ids_dry_run_name_equals_real_run_name
    red_reason: "AssertionError: last stdout line lacks 'Dry-run: would create' prefix"
  - file: unit_tests/test_goal_to_epic.py
    function: test_ids_dry_run_prints_ids_in_build_order
    red_reason: "AssertionError: last stdout line lacks 'Dry-run: would create' prefix"
  - file: unit_tests/test_goal_to_epic.py
    function: test_ids_dry_run_cycle_exits_1_without_writes
    red_reason: green_at_baseline (guard) - cycle already exits 1 before any write; must stay green

### 2026-10-06 17:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Threaded keyword-only `dry_run=False` through `_run_ids_mode` and `build_epic_from_ids`; goal_to_epic passes `dry_run=args.dry_run`. In dry-run the pipeline stops after graph, sort and name derivation, prints the build order then `Dry-run: would create <resolved EPIC path>`, writes nothing; the CLI skips its trailing path print. Cycle still raises before any write.
red_baseline_results: all 4 red tests green; cycle guard, test_dry_run_matches_real_run and slug tests green.
Strict (AC_ENFORCE_STRICT=1): test_goal_to_epic.py 9 passed. All 29 test files referencing goal_to_epic/epic_cli/epic_pipeline: 266 passed, 5 failed, all 5 fail identically on base worktree build-tooling-done-proof (pre-existing: test_no_tty_no_flag_fails_clearly, three test_ac1_performance_* timing tests, test_implemented_by_written_repo_relative backslash path on Windows).
Ratchet: epic_cli.py 195 -> 201 (limit 400), epic_pipeline.py 316 -> 327, goal_to_epic.py 492 -> 492 (no change); check_file_size passed. No tracked deployed mirrors, so no build.py run.

### 2026-10-06 17:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Verdict: ok, no high findings. dry_run returns before every write point in build_epic_from_ids (ticket generation, assemble, depends_on wiring, implemented_by back-refs, loose-ticket removal, Master_Plan); only reads/prints precede it. Real --ids run unchanged; dry_run defaults False and the only callers (epic_cli._run_ids_mode, goal_to_epic.main) are the ones changed. Tests run the real CLI against a temp store and assert on the filesystem.
Medium:
- M-1 scripts/ac_store/epic_pipeline.py:236 - ids dry-run line is `Dry-run: would create <path>`, while the --ac form (epic_pipeline.py:115) is `Dry-run: would create EPIC-<name> with N ticket(s):`. Same prefix, different shape; the test pins the path form. Acceptable if the design intends it, otherwise align.
- M-2 scripts/ac_store/epic_pipeline.py:283, epic_cli.py:178, goal_to_epic.py:280 - all three carry a DECISION HISTORY footer; none got an entry for this change.
- M-3 templates/agents/build-ac.md:79, :461, :651 - still say "--ids mode does not implement dry-run" and skip the --ids call (line 506 already says to pass --dry-run, so the file contradicts itself). Stale now; needs a follow-up ticket (documentation-expert not_needed here). docs/how-to/goal-to-epic.md and templates/skills/build-feature-ops-notes/SKILL.md do not mention it.
Suppressed: 0 low.

### 2026-10-06 17:45 — test-runner (status: ok)
feedback-id: (submit-failed)
Ran with AC_ENFORCE_STRICT=1. All failures are pre-existing and identical at base; nothing broken by this ticket.
- unit_tests/test_goal_to_epic.py: 9 passed, 0 failed.
- All 29 test files in unit_tests/ and tests/ referencing goal_to_epic/epic_cli/epic_pipeline/build_epic_from_ids (-n auto): 266 passed, 5 failed, 1 skipped. Failures (pre-existing): test_acd_1200b_4::test_no_tty_no_flag_fails_clearly; test_bo_2600a_5::test_implemented_by_written_repo_relative (Windows backslash); perf-timing tests test_readiness_gate::test_ac1_performance_under_100_leaves, test_dependency_wiring::test_ac1_performance_100_leaves_500_edges, test_tree_traversal::test_ac1_performance_200_nodes.
- Reachability via real temp store (BO-3900, BO-3900a, BO-3900b copied): `goal_to_epic.py --ids BO-3900a,BO-3900b --dry-run --store-root <tmp> --inbox-dir <tmp>` exit 0, last line `Dry-run: would create <tmp inbox>\epics\EPIC-...`, 0 files in tmp inbox, 3 YAMLs sha256-identical.

completion_manifest:
  test_suite_executed: true
  all_tests_passing: true   # only pre-existing base failures remain
  failure_report_structured: true

### 2026-10-06 18:00 — llm-expert (status: ok)
feedback-id: (submit-failed)
M-3 follow-up: templates/agents/build-ac.md (frontmatter behavior line, Step 2b.3 dry-run paragraph, new DECISION HISTORY entry) now says --ids honours --dry-run and the dry-run path passes --dry-run; build-ac.card.md regenerated and staged; 24 template tests green before and after.
M-2 follow-up: NOT applied by llm-expert - the three DECISION HISTORY footers are in .py files, outside this agent scope; left for python-coder or the caller.

### 2026-10-06 16:22 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(ac-driven-dev): make goal_to_epic --ids honour --dry-run".

completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
