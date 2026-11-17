---
title: "The red-baseline gate records its own pass on the ticket and a resumed run reuses it"
status: todo
components:
  - build_orchestration
  - testing_quality
created: 2026-10-06
depends_on:
  - 01_TICKET-20261006-GateUsesProjectInterpreter.md
  - 02_TICKET-20261006-HandoffContinuesTheTicket.md
priority: high
complexity: high
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: TQ-500f-3-ii
ac_traceability:
  id: TQ-500f-3-ii
  path: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - code
risk_surface: contract_boundary
files_touched:
  - scripts/build_orchestration/_fl_heavy_lane_gate.py
  - scripts/build_orchestration/_fl_cli.py
  - scripts/build_orchestration/fast_lane.py
  - scripts/build_orchestration/_fl_red_baseline_support.py
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
  - unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py
  - unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py  # new in 01
  - unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py  # new in 03 (test-writer)
  - unit_tests/workflows/test_tq500f3ii_gate_record_driver.py  # new in 03 (test-writer)
  - unit_tests/workflows/test_tq500f3ii_h3_resume_gate.py  # docstring note only
  - templates/skills/ticket-authoring/SKILL.md
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: not_needed
  test-runner: signed_off
  documentation-expert: needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  status-checker: not_needed
---

# 03: The red-baseline gate records its own pass on the ticket and a resumed run reuses it

## Actor / Goal

As the build driver, I want the red-baseline reader to record its own pass in the
ticket, and a resumed run to reuse that record under strict conditions. Then a ticket
that halted after its coder started can be resumed. Today the coder's uncommitted
code turns the new tests green, and the gate wrongly halts the ticket as
"green at baseline". A ticket whose tests really are green before any coding still
halts, with a clear `green_at_baseline` message that says what to do.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 2). Implements TQ-500f-3-ii as
amended on this branch: F2 (record and reuse) and F3 Option A (the
`green_at_baseline` halt). Both are user decisions of 2026-10-06.

**Root cause**
- `redBaselineGateChecked` exists only in memory for one drive:
  - `templates/workflows-js/build-feature.js:1914`, set at 2107-2108;
  - `templates/workflows-js/build-ticket.js:1547`, set at 1743-1744.

  Every re-run with a coder still `needed` runs the reader again.
- `verify_red_baseline` (`scripts/build_orchestration/fast_lane.py:263-421`) runs the new tests against the current working tree. Once the coder's uncommitted code is there they pass, so it returns `all_new_tests_green_at_baseline` (403-410), and the JS halts (2135-2141 / 1771-1777).
- Any halt after the coder ran triggers this: today's handoff halt, a blocker, a retry cap, a crash.

**Why not "red at the test-writer's commit"**
- No per-phase commit exists. Tests and code stay uncommitted until the commit phase (priority 12).
- Running against merge-base or HEAD in a temporary checkout has three problems:
  - in an epic, merge-base predates earlier tickets, so the tests go red by import error, which TQ-500f-3-i refuses as absence-only red;
  - it costs a full checkout per gate run;
  - it changes the reader's inputs, which breaks TQ-500f-3-ii's rule that both lanes give an identical verdict.

**Rule: a durable record written by the reader alone**
- `heavy_lane_gate` takes `--ticket <path>`.
- On `gate_passed`, it alone (never the test-writer) writes one frontmatter line with an anchored atomic write. Use the `scripts/ac_store/mark_ac_done.py::_atomic_write` pattern (200-260):

  ```
  red_baseline_gate: {"passed": true, "recorded_at": "<iso>", "head": "<sha>", "source_ac": [...], "red": [{"file": "...", "function": "..."}]}
  ```

  `ticket_frontmatter_guard` ignores unknown keys.
- A later run reuses the record, without running pytest, only when all of these hold:
  - the record exists;
  - its `source_ac` equals the ticket's current ids;
  - every recorded red `(file, function)` is still among the newly-added covers-tagged tests. This is a subset check, because a later test-writer handoff may add tests.

  It then returns `gate_passed: true, reused: true` and an outcome naming `recorded_at` and `head`. The newly-added partition is computed without running pytest (`scripts/ac_store/done_proof.py::_scan_test_root_for_covers_tags` plus `scripts/build_orchestration/_fl_red_baseline_support.py::_partition_newly_added`).
- In every other case the reader runs as today and fails closed.
- If the record cannot be written, the gate still passes, and reports `recorded: false` and `record_error`.

**`green_at_baseline` (F3 Option A, no automatic pass)**
- Keep the halt for `all_new_tests_green_at_baseline`, but classify it `green_at_baseline`.
- List the green tests and suggest: set the coder phase `not_needed` with a comment naming the ticket or commit that delivered the behaviour.
- The driver never flips the phase itself (TKT-600b-4).
- The gate runs only before a coder dispatch. test-runner, pr-reviewer and ac-fulfillment still verify the tests.

## Constraints

- **Twins.** The gate command and halt message change in both `build-feature.js` and `build-ticket.js`, in the same commit.
- **File-size ratchet (GE-127b-1, GE-127f-2).** `build-feature.js` measures 2964 / 1000 and `build-ticket.js` 1647 / 1000. Each staged file may measure at most `previous − gross measured lines added`, and a changed line counts as added.
  - Appending `--ticket ${worktreeTicketPath}` (build-ticket.js: `${ticketPath}`) to the existing gate line changes 1 line in each twin.
  - Changing the halt message changes more.
  - Pay each of these back by removing at least as many further measured lines in the same file.
  - Compute the `green_at_baseline` classification, the green-test list and the remedy text in Python (`heavy_lane_gate` verdict fields), and have the JS echo them inside its existing halt return.
- **Python size.** Measured / limit at bc8e6c62:
  - `fast_lane.py` 387 / 400: only a pass-through of `--ticket`; crossing 400 is refused;
  - `_fl_heavy_lane_gate.py` 36 / 400: the record and reuse logic goes here, or in a new `_fl_*` module registered for deployment;
  - `_fl_cli.py` 262 / 400;
  - `_fl_red_baseline_support.py` 305 / 400.
- **Test-file size.** `test_tq500f3ii_heavy_lane_red_baseline_gate.py` measures 346 / 400; only change its `wrapper_only_keys` there. New driver-side tests go in `test_tq500f3ii_gate_driver_contract.py`, which ticket 01 creates.
- **Build mirrors.** After the template edits, run `python scripts/build.py` and stage every tracked output it changes.
- **Lane parity (TQ-500f-3-ii).** Whenever the reader runs, its verdict is identical in both lanes. The fast lane's `verify_red_baseline` invocation does not change. The heavy lane's extra keys (`reused`, `recorded`, `record_error`, the halt classification) are wrapper keys only.

## Acceptance Criteria

- [ ] AC-1: When `heavy_lane_gate --ticket <path>` passes, it writes exactly one `red_baseline_gate:` frontmatter line (passed, recorded_at, head, source_ac, red) with an anchored atomic write. The real `ticket_frontmatter_guard.validate` and `check_doc_frontmatter` accept the ticket afterwards. The test-writer never writes this line.
- [ ] AC-2: A later gate run on the same ticket reuses the record without running pytest only when the record exists, its `source_ac` equals the current ids, and every recorded red `(file, function)` is among the newly-added covers-tagged tests (subset). It then returns `gate_passed: true`, `reused: true`, and an outcome naming `recorded_at` and `head`.
- [ ] AC-3: In every other case the reader runs as today and its verdict decides: no record, a different `source_ac`, a recorded red test renamed or removed, or only a test-writer `red_baseline_verified` claim.
- [ ] AC-4: If the record cannot be written (missing or unwritable ticket), the gate still passes and reports `recorded: false` with `record_error`.
- [ ] AC-5: Both twins pass `--ticket <ticket path>` on the gate command. The fast lane's `verify_red_baseline` command is unchanged, and whenever the reader runs, its verdict keys are identical across lanes apart from the wrapper keys.
- [ ] AC-6: An `all_new_tests_green_at_baseline` verdict halts the ticket before the coder with classification `green_at_baseline`. The halt lists every green newly-added covering test and suggests setting the coder phase `not_needed` with a comment naming the implementing commit. The driver never changes the phase itself.
- [ ] AC-7: `templates/skills/ticket-authoring/SKILL.md` documents `red_baseline_gate` as a field written only by the gate, which authors and agents must not write or edit.

## Test Requirements

```yaml
tests:
  - name: test_gate_pass_writes_record_accepted_by_real_guards
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      On the _tq500f3i_fixtures real git fixture with red new tests,
      heavy_lane_gate --ticket <tmp ticket> passes and the ticket gains exactly
      one red_baseline_gate line holding passed true, recorded_at, head equal to
      the fixture HEAD sha, the source_ac list and the red (file, function)
      pairs. The real ticket_frontmatter_guard.validate returns no errors and
      check_doc_frontmatter accepts the file.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_rerun_after_coding_reuses_record_without_pytest
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      After a recorded pass, the fixture's production code is changed so the
      new tests pass ("coding"), and heavy_lane_gate is run again. It returns
      gate_passed true and reused true, with an outcome naming recorded_at and
      head, and the pytest runner is never invoked.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_renamed_recorded_red_test_runs_reader_and_fails
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      After a recorded pass and coding, one recorded red test function is
      renamed. The next run does not reuse the record, the reader runs, and it
      returns gate_passed false with reason all_new_tests_green_at_baseline.
    framework: pytest
    type: integration
    angle: failure
  - name: test_different_source_ac_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      With a record made for source_ac [A], a run with --source-ac A,B does not
      reuse it (reused absent or false), and the reader's verdict is returned.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_test_writer_claim_without_record_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      A ticket whose test-writer sign-off claims red_baseline_verified but which
      has no red_baseline_gate line gets a run in which the reader runs, and its
      verdict decides (the K1 guarantee is preserved).
    framework: pytest
    type: integration
    angle: failure
  - name: test_missing_ticket_passes_with_recorded_false
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      heavy_lane_gate --ticket <nonexistent path> with red new tests returns
      gate_passed true, recorded false and a non-empty record_error, and writes
      no file.
    framework: pytest
    type: integration
    angle: failure
  - name: test_both_twins_gate_command_carries_ticket_flag
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      For build-feature.js and build-ticket.js, the captured red-baseline-gate
      command contains "--ticket <the worktree ticket path>", and the fast-lane
      verify_red_baseline command is unchanged.
    framework: pytest
    type: integration
    angle: seam
  - name: test_green_at_baseline_halt_lists_tests_and_suggests_not_needed
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      Both twins, with a stubbed gate verdict of gate_passed false and reason
      all_new_tests_green_at_baseline listing two green tests: the ticket halts
      before python-coder with classification green_at_baseline, the halt
      message names both tests and tells the user to set the coder phase
      not_needed with a comment naming the implementing commit, and the
      ticket's agents map still reads python-coder needed.
    framework: pytest
    type: integration
    angle: criterion
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_tq500f3ii_gate_record_reuse.py:test_gate_pass_writes_record_accepted_by_real_guards | | |
| AC-2 | test_tq500f3ii_gate_record_reuse.py:test_rerun_after_coding_reuses_record_without_pytest, test_tq500f3ii_gate_record_reuse.py:test_tests_added_after_record_do_not_block_reuse, test_tq500f3ii_gate_record_driver.py:test_reused_pass_dispatches_coder_and_reports_reuse | | |
| AC-3 | test_tq500f3ii_gate_record_reuse.py:test_renamed_recorded_red_test_runs_reader_and_fails, test_tq500f3ii_gate_record_reuse.py:test_different_source_ac_runs_reader, test_tq500f3ii_gate_record_reuse.py:test_test_writer_claim_without_record_runs_reader | | |
| AC-4 | test_tq500f3ii_gate_record_reuse.py:test_missing_ticket_passes_with_recorded_false, test_tq500f3ii_gate_record_reuse.py:test_relative_ticket_resolves_against_test_root | | |
| AC-5 | test_tq500f3ii_gate_record_driver.py:test_both_twins_gate_command_carries_ticket_flag, seam tests in test_tq500f3ii_heavy_lane_red_baseline_gate.py and test_tq500f3ii_heavy_lane_gate_subcommand.py (coder updates wrapper_only_keys) | | |
| AC-6 | test_tq500f3ii_gate_record_driver.py:test_green_at_baseline_halt_lists_tests_and_suggests_not_needed, test_tq500f3ii_gate_record_reuse.py:test_green_at_baseline_verdict_carries_classification_and_remedy | | |
| AC-7 | pr-reviewer reads the skill diff | | |

## Implementation Tasks

### architect-review
- [x] Review the durable `red_baseline_gate` frontmatter field: its trust level matches sign-offs, and `head` and `recorded_at` support audit. Decide whether it needs an ADR. If yes, flip `requires_adr` to true and dispatch adr-author.

### test-writer
- [x] Extend `test_tq500f3ii_heavy_lane_gate_subcommand.py` with the six reader tests, on the real git fixture `unit_tests/build_orchestration/_tq500f3i_fixtures.py`. (Done in the new sibling `unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py`: ten tests; the existing file would overflow 400 lines.)
- [x] Add the two driver tests to `unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py`. (Done in the new `unit_tests/workflows/test_tq500f3ii_gate_record_driver.py`: four tests, each over both twins.)
- [x] In `test_tq500f3ii_heavy_lane_red_baseline_gate.py`, add the new keys (`reused`, `recorded`, `record_error`, and any halt-classification key) to the seam test's `wrapper_only_keys` (line 309). (Handed to python-coder: the keys become one exported `HEAVY_WRAPPER_KEYS` constant that does not exist yet; see the sign-off comment.)
- [x] FIX the fixture ticket in `test_tq500f3ii_gate_record_reuse.py::_write_ticket`: its frontmatter lacks `requires_diagram`, `requires_adr`, `change_target`, `risk_surface`, so `test_gate_pass_writes_record_accepted_by_real_guards` fails on the real `ticket_frontmatter_guard.validate` for reasons unrelated to the record (python-coder probe: with those four keys added the test passes, the record is accepted by both real guards and the control still fails). Do not weaken the guard assertion.

### python-coder
- [x] `_fl_heavy_lane_gate.py` (38-77): add record write, reuse check, `recorded`/`record_error`, and the `green_at_baseline` classification with the green-test list and the remedy text.
- [x] `_fl_cli.py` (128-130): add `--ticket`. `fast_lane.py` (485-493): pass it through.
- [x] Add a helper that computes the newly-added covers-tagged partition without running pytest (`_scan_test_root_for_covers_tags` + `_partition_newly_added`).
- [x] Both twins:
  - append `--ticket` to the gate line (build-feature.js:2114-2116 `${worktreeTicketPath}`; build-ticket.js:1750-1752 `${ticketPath}`);
  - make the halt return echo the verdict's classification and remedy (2135-2141 / 1771-1777);
  - pay back every changed line.
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### documentation-expert
- [ ] `templates/skills/ticket-authoring/SKILL.md`: add `red_baseline_gate` to the frontmatter field table. It is written only by the gate; authors and agents must not write or edit it; describe what it holds and when it is reused.

### test-runner / pr-reviewer / commit
- [ ] Run all `test_tq500f3ii_*` and `test_tq500f3i*` suites and the fast-lane workflow tests. pr-reviewer checks twin parity, lane parity and check-file-size.

## Risk & Safety

- Touches money? No.
- Touches data? Writes one frontmatter line into the ticket being built, with an anchored atomic write.
- A hand-edited record could forge a pass. That is the same trust level as sign-offs; `head` and `recorded_at` support audit.
- The gate's executor is status-checker, which has `permits_shell: false` (known issue KI-BO-20260927). This ticket does not change that.
- Sequenced after ticket 01, which changes the same command line and module.
- Reversibility: revert the commit. Tickets that already carry a record keep a harmless unknown key.

## Out of Scope

- Option C (the reader checks red at the implementing commit's parent).
- Any automatic pass for green-at-baseline tests.
- Changing the gate's executor agent (KI-BO-20260927).

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-10-06 15:40 — architect-review (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  blast_radius_read_at_head: true
  guards_probed_with_real_record_line: true
  gate_executor_confirmed_with_file_line: true
  adr_decision_made: true
  size_ratchet_measured: true

**Classification: large.** No always-large trigger fired (no migration, hypertable, FastAPI or ADR-contract change). Thresholds crossed: 10 files in `files_touched` (more than 5), and the change spans `scripts/` and `templates/` (workflow JS, skill, Python) plus two ticket components (`build_orchestration`, `testing_quality`). The deep Opus pass was not spawned: `architect-review-deep` is not in this agent's spawn allowlist, so the review was done inline against HEAD 119fca8e2 by reading the code (no research-agent fan-out; every symbol was named in the ticket). `escalation: opus`, `escalation_reason: more than 5 affected files and cross-package change`. Nothing below needs a second opinion.

**ADR decision: no ADR. `requires_adr` stays `false`.** The rubric's two-component clause would say `true`, but it is a judgment call and the components are nominal: every changed behaviour is `build_orchestration`, and `testing_quality` is only the AC's home. The field has one writer and one reader (the heavy-lane gate wrapper), no other component reads it, and its trust level equals sign-offs. Other durable ticket keys (`ac_coverage`, `test_constraints`, `handoff_target`) are documented only in `templates/skills/ticket-authoring/SKILL.md` (field table, lines 139-161) with no ADR; ADR-026 governs only the required keys. The decision itself (F2/F3) is already recorded in the amended AC TQ-500f-3-ii (`it_requirements` and the 2026-10-06 amendment reason) and the design. SKILL.md (AC-7) plus a changelog entry suffice. Revisit only if a second consumer (another agent or hook) starts reading `red_baseline_gate`. `suggested_adr: null`, `suggested_diagrams: []`.

**Findings (file:line at HEAD)**

1. Gate executor (confirmed; do not change it here). Both twins dispatch the gate with `agentType: "status-checker"`: `templates/workflows-js/build-feature.js:2120` (label `red-baseline-gate`, schema `REPO_FACTS_ENVELOPE_SCHEMA`) and `templates/workflows-js/build-ticket.js:1756` (`RED_BASELINE_GATE_ENVELOPE_SCHEMA`). The registry says `permits_shell: false` (`config/agent_registry.json:1296-1300`), while the agent template carries `tools: Bash, Read, Edit, Write, Agent` (`templates/agents/status-checker.md:22`), so it runs today; the mismatch is the known KI-BO-20260927-status-checker-runs-workflow-shell-commands. fast-lane-ship.js already moved its claim runner to `command-step-runner` (`fast-lane-ship.js:1071`). This ticket must NOT change the executor (Out of Scope). The record is written by the Python process, never by the LLM executor, which only relays stdout; a forged relay is an existing risk, not a new one.
2. Where the logic goes. `scripts/build_orchestration/_fl_heavy_lane_gate.py` is the wrapper (36 / 400 measured, room for record, reuse and remedy logic). `fast_lane.py:485-493` dispatches it; `_fl_cli.py:128-130` declares its args. The reader (`verify_red_baseline`, `fast_lane.py:263-421`) stays untouched: no record or reuse code there (lane parity).
3. Reuse without pytest is possible with existing parts: `_scan_test_root_for_covers_tags`, `_resolve_git_baseline_context` and `_partition_newly_added` (`_fl_red_baseline_support.py:136, 221`) are a file scan plus read-only `git show`. Use the same local (function-body) import pattern the wrapper already uses; a top-level `from fast_lane import ...` is an import cycle (module docstring). Catch `_RedBaselineGitError` and any partition failure and treat it as "no reuse, run the reader" (fail closed). The base ref is the merge-base with origin/main, so a recorded test stays "newly added" across a resume while nothing has committed it. The record's `head` is audit only: do NOT require it to equal the current HEAD (an epic resume legitimately has a newer HEAD).
4. Frontmatter acceptance (probed, not assumed). I put a single-line `red_baseline_gate: {"passed": true, "recorded_at": "...", "head": "119fca8e2", "source_ac": [...], "red": [{"file": ..., "function": ...}]}` into a scratch copy of this ticket: `yaml.safe_load` returns a dict and `ticket_frontmatter_guard.validate` (`templates/hooks/ticket_frontmatter_guard.py:570`) returns `[]`. The guard checks only its fixed key set (`REQUIRED_FIELDS` line 24, enums 25-50); unknown keys are ignored. check-doc-frontmatter validates required fields and enums per glob (`templates/scripts/commit_guardian/frontmatter_validators.py`, `check_doc_frontmatter.py`) and ignores unknown keys; it treats a file as a ticket only when the repo-relative path starts with `tickets/` (`check_doc_frontmatter.py:238-248`), and my direct `--file` run on a path outside the repo printed nothing, so the new test must put the temp ticket under a `tickets/...` relative path inside its temp repo and run the checker from that root. Do not weaken either gate.
5. Record writer design. Reuse the `mark_ac_done._atomic_write` pattern (`scripts/ac_store/mark_ac_done.py:200-230`: same-dir `mkstemp`, `newline=""`, `os.replace`, temp cleanup on failure) and the column-0 anchoring of `_set_work_status_done` (233+). Rules: read with `newline=""` and keep each line's own ending (CRLF is real on this host); find the frontmatter block by the first two column-0 `---` lines; replace the single column-0 `red_baseline_gate:` line, or insert it just before the closing `---`; if more than one such line exists, or there is no closing `---`, raise and report `recorded: false` with `record_error` (never guess); re-parse after the write and verify the key reads back. Serialise with `json.dumps(record)` on one line (a valid YAML flow mapping). Touch no other byte, including the `agents:` map. `scripts/ac_store/epic_tickets.py:291` safe_dumps frontmatter, but only at epic scaffold time, before any gate runs.
6. Relative ticket path. build-ticket.js passes `ticketPath` exactly as the user gave it (`build-ticket.js:1385`), which may be relative while the gate runs in the status-checker's cwd; build-feature.js passes `worktreeTicketPath` (absolute, `build-feature.js:1849`). Python should resolve a relative `--ticket` against `--test-root` when it does not exist as given; if still missing, `recorded: false` with `record_error` (pass stands, AC-4). An unrecorded pass means the next resume re-runs the reader and can hit the deadlock again, so `record_error` must show in the drive outcome (see 7).
7. `green_at_baseline` naming trap. The reader's verdict already has a LIST key named `green_at_baseline` (`_fl_red_baseline_support.py:367-421`). Do not reuse that name for the halt classification. Add wrapper keys `halt_classification: "green_at_baseline"` and `remedy: "<text>"`, set only when `reason == "all_new_tests_green_at_baseline"`. `remedy` lists every green nodeid and says to set the coder phase `not_needed` with a comment naming the implementing ticket or commit; when a record existed but reuse was skipped (recorded test renamed or removed, different source_ac) it adds one sentence saying so, because a resumed ticket that lost a recorded test name would otherwise be told wrongly to skip the coder. The JS only echoes: `classification: gateVerdict.halt_classification || "halt"` and `${gateVerdict.remedy || ""}` appended to the existing halt message (`build-feature.js:2138-2139`; build-ticket.js has the same two lines near 1774-1775). Reused-pass and unrecorded-pass reporting needs NO JS change: put it in the wrapper's `outcome` string, which the JS already copies into `redBaselineGateOutcome` (`build-feature.js:2134`).
8. Lane parity seam. The seam test is `unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py:309-310` (`wrapper_only_keys = {"applicable", "verified", "outcome"}`; the heavy verdict minus those keys is compared to the fast-lane verdict). There is a second copy of the same set at `unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py:225-226` (`test_heavy_lane_gate_verdict_equals_verify_red_baseline_no_second_reader`) that the ticket does not list; it fails too once `recorded` / `record_error` are emitted unless updated. Recommended: export one `HEAVY_WRAPPER_KEYS` frozenset from `_fl_heavy_lane_gate.py` (exactly the keys the wrapper can add: `applicable, verified, outcome, reused, recorded, record_error, halt_classification, remedy`, plus the reuse provenance keys the coder chooses, for example `recorded_at`, `head`) and import it at both sites so they cannot drift. The seam's captured command now carries `--ticket <fixture ticket path>`; the test rewrites `fx.WORKTREE_ABS_PATH` to the temp dir, so the ticket does not exist there and the wrapper returns `recorded: false` plus `record_error`, both stripped. `_GATE_INVOCATION_RE` (`unit_tests/workflows/_tq500f3ii_fixtures.py:74`, `[^\n\"]*`) already captures the extra flag. The fast-lane `verify_red_baseline` command and verdict do not change.
9. `unit_tests/workflows/test_tq500f3ii_h3_resume_gate.py` does NOT pin the old rule at the Python level, so no assertion changes. It drives the real JS under the harness with the gate reply stubbed (`fx.red_baseline_gate_response`) and asserts only that the gate is dispatched before the coder on a resumed ticket and that `gate_passed=False` blocks the coder. Reuse is decided inside the Python wrapper and the JS still dispatches the gate on every resume, so both assertions stay true and the tests must stay green unchanged. Only the docstring (lines 1-30, "re-runs the reader before the coder rather than trusting the earlier sign-off") is now stale: the coder adds a short note that a valid record makes the wrapper return a reused pass while the driver still always dispatches the gate (file is 115 / 400). The Python-level resume behaviour is pinned by the new subcommand tests (`test_rerun_after_coding_reuses_record_without_pytest`, `test_test_writer_claim_without_record_runs_reader`).
10. File-size ratchet (measured with `check_file_size.measure_current_length` at HEAD). OVER the limit: `templates/workflows-js/build-feature.js` 2964 / 1000 and `templates/workflows-js/build-ticket.js` 1647 / 1000 only (a changed line counts as added; `//` lines count, `/* */` blocks and triple-quoted content do not). Under: `fast_lane.py` 387 / 400 (only the `--ticket` pass-through at 485-493, budget 13 lines), `_fl_heavy_lane_gate.py` 36 / 400, `_fl_cli.py` 262 / 400, `_fl_red_baseline_support.py` 305 / 400 (not needed), `test_tq500f3ii_heavy_lane_red_baseline_gate.py` 346 / 400, `test_tq500f3ii_heavy_lane_gate_subcommand.py` 227 / 400 (it already holds ticket 01's staged additions; six new cases need roughly 150 lines, so put them in a sibling `unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py` if the file would pass 400, and add that path to `files_touched`), `h3` test 115 / 400. SKILL.md is `.md` and is not measured. Per JS twin the change adds 3 lines: the `--test-root ... --ac-root ...` command line gains `--ticket` (`build-feature.js:2115-2116`, `build-ticket.js:1751-1752`), the failure return line gains the classification, and the halt message gains the remedy. Pay them back in the same file inside the same gate block: for example condense the `//` comment block above the gate (`build-feature.js:2100-2106`, 7 lines; `build-ticket.js:1740-1743`, 4 lines) by at least 3 lines each. Recount with `check_file_size.py` before commit.
11. What 01 and 02 change. 01 turns `python3` into `python` in the gate command (same lines as this ticket's `--ticket` edit, so re-read line numbers), adds `interpreter` and the `test_interpreter_unusable` reason to the verdict from the shared reader, and creates `test_tq500f3ii_gate_driver_contract.py` (already present and staged in this worktree). `interpreter` and `test_interpreter_unusable` come from the reader, so they are NOT wrapper keys and must stay in the seam comparison. The ratchet baseline for this ticket is the HEAD that includes 01 and 02 (02 rewrites the handoff branch near 2353-2388 / 1979-2014), so re-measure. 02 sends a handoff target through the normal loop, so a handoff to python-coder now reaches this gate and its reuse path. `redBaselineGateChecked` stays as the in-memory once-per-drive flag.
12. Concurrency. The wrapper's read-modify-write of the ticket is safe only because the driver runs the gate sequentially before the coder dispatch. Write only after a `gate_passed: true` reader verdict (never for a failed or not-applicable verdict), and make it the last action before returning.
13. Accepted risks, no action: (a) a recorded red test whose name survives but whose body is rewritten still reuses the record (the AC accepts name-level identity); (b) a hand-edited record forges a pass at sign-off trust level; (c) `--ticket`, like `--test-root`, is not shell-quoted, so a path with spaces already breaks the command.

**Implementation guidance (in order)**
- python-coder: (1) `_fl_heavy_lane_gate.py`: add `ticket: Path | None = None` to `heavy_lane_gate`, then the reuse check, the reader call, the record write, the wrapper keys, the `outcome` text for reused / unrecorded passes, and `halt_classification` / `remedy`. Stay under 400; split the writer into a new `_fl_*` module only if it would pass about 250 lines, and then register it wherever the other `_fl_*` modules are deployed (check `.build_manifest.json` and `scripts/build.py` first). (2) `_fl_cli.py:128-130`: `--ticket`; `fast_lane.py:485-493`: pass it through and nothing else. (3) Both twins in the same commit, with the payback. (4) `python scripts/build.py`, then stage every tracked mirror it changes.
- test-writer: the six subcommand tests; both `wrapper_only_keys` sites (or the shared constant); the two driver tests in the file ticket 01 created; the check-doc-frontmatter assertion on a temp ticket under a `tickets/` relative path.
- documentation-expert: one `red_baseline_gate` row in the SKILL.md field table (after `risk_surface`, line 159): written only by the gate; authors and agents must not write, copy or edit it; holds `passed, recorded_at, head, source_ac, red`; reused only when `source_ac` matches and every recorded red test is still among the newly added covers-tagged tests. Add a changelog entry.

**Acceptance adjustments**
- AC-5: both tests that compare verdicts strip the same shared wrapper-key set; name the second site (`test_tq500f3ii_heavy_lane_gate_subcommand.py:225`).
- AC-2 / AC-4: a relative `--ticket` is resolved against `--test-root`; a git or partition failure while checking reuse means "run the reader", not an error.
- AC-6: the wrapper keys are `halt_classification` and `remedy` (`green_at_baseline` is already a verdict list key).
- `files_touched`: add `unit_tests/workflows/test_tq500f3ii_h3_resume_gate.py` (docstring note only) and, if needed, the sibling record/reuse test file.

**Must-decide questions:** none. Nothing in the code makes F2 or F3 option A impossible.

### 2026-10-06 17:21 — test-writer (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  tests_written_and_staged: true
  tests_red_by_assertion_in_strict_mode: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "scripts/build_orchestration/_fl_heavy_lane_gate.py heavy_lane_gate, run as the real fast_lane.py CLI subprocess against the real git fixture (writes the red_baseline_gate line and the verdict keys); build-feature.js and build-ticket.js drivers (scripted gate reply)"
    consuming_side: "the real ticket_frontmatter_guard.validate and check_doc_frontmatter.py over the written ticket; the same gate's next run (reuse decision); the real JS twins' halt return and outcome under the E2 harness"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python scripts/build_orchestration/fast_lane.py heavy_lane_gate --source-ac <ids> --test-root <dir> --ac-root <dir> --ticket <path> (CLI via subprocess); build-feature.js and build-ticket.js driven under run_workflow_under_e2"

Wrote 14 tests in two new files (the existing subcommand test is at 227/400 lines, so the reader cases go in a sibling). Classification: no existing test was repaired; no production code was touched.

**Files**
- `unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py` (338 measured lines): 10 tests on the real `heavy_lane_gate` CLI, real git fixture, ticket written with `yaml.safe_dump`. The covered tests append their name to a log outside the repo when they run, so "reuse without pytest" is proved by the log's absence, not by a mock.
- `unit_tests/workflows/test_tq500f3ii_gate_record_driver.py` (133 lines): 4 driver tests parametrised over TWIN_DRIVERS (8 cases), real twins under the E2 harness with the gate reply scripted.

**Strict run** (`AC_ENFORCE_STRICT=1 python -m pytest <both files> -q -p no:cacheprovider`): 14 failed, 4 passed. All 14 failures are assertions (today `--ticket` is an unrecognised argument, so the CLI exits 2 with no JSON; the driver cases see no `--ticket` and `classification: "halt"`). No ERRORs. Re-run once after a nested-pytest flake in my own probe.

red_baseline:
  - test_name: test_gate_pass_writes_record_accepted_by_real_guards
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 stdout='' ... fast_lane.py: error: unrecognized arguments: --ticket"
  - test_name: test_rerun_after_coding_reuses_record_without_pytest
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_renamed_recorded_red_test_runs_reader_and_fails
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_different_source_ac_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_tests_added_after_record_do_not_block_reuse
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_test_writer_claim_without_record_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
    note: "red only because --ticket is unknown today; once the flag exists it guards K1 (a trusted claim would pass the gate)"
  - test_name: test_missing_ticket_passes_with_recorded_false
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_relative_ticket_resolves_against_test_root
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_later_pass_replaces_the_record_not_duplicates_it
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_green_at_baseline_verdict_carries_classification_and_remedy
    file: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
    error: "AssertionError: heavy_lane_gate --ticket must print one JSON object on stdout; exit=2 (unrecognized arguments: --ticket)"
  - test_name: test_both_twins_gate_command_carries_ticket_flag[build-feature.js] and [build-ticket.js]
    file: unit_tests/workflows/test_tq500f3ii_gate_record_driver.py
    error: "AssertionError: build-feature.js: the gate command must carry the ticket path; command='python .../fast_lane.py heavy_lane_gate --source-ac ... --test-root ...'"
  - test_name: test_green_at_baseline_halt_lists_tests_and_suggests_not_needed[build-feature.js] and [build-ticket.js]
    file: unit_tests/workflows/test_tq500f3ii_gate_record_driver.py
    error: "AssertionError: payload=... assert 'halt' == 'green_at_baseline'"

**Passing today (guards, `green_at_baseline (guard)`)** — not in `red_baseline`:
- `test_reused_pass_dispatches_coder_and_reports_reuse[both twins]`: the JS already copies the verdict's `outcome` into `red_baseline_gate`. It pins that the coder-side reporting of reused and unrecorded passes needs NO JS change (architect finding 7).
- `test_halt_without_wrapper_keys_stays_a_generic_halt[both twins]`: discrimination guard against a coder that hard-codes `green_at_baseline` for every refusal; it must stay green.

**Notes for python-coder**
1. Seam tests: update BOTH `wrapper_only_keys` sites, `unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py:309-310` and `unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py:225-226`. Export one `HEAVY_WRAPPER_KEYS` frozenset from `_fl_heavy_lane_gate.py` (`applicable, verified, outcome, reused, recorded, record_error, halt_classification, remedy`, plus any reuse provenance keys you add, e.g. `recorded_at`, `head`) and import it at both. I did not edit either (the constant does not exist yet). `interpreter` stays in the comparison. The seam command now carries `--ticket`; the seam test rewrites the worktree path so the ticket does not exist there, so the wrapper returns `recorded: false` plus `record_error`, both stripped.
2. `h3_resume_gate.py`: docstring note only, no assertion change (file 115/400).
3. Success verdict contract pinned by my tests: `recorded: true` on a written record; `halt_classification` and `remedy` absent on a pass; on reuse `reused: true` and `outcome` containing the record's `recorded_at` and `head` strings, ticket bytes unchanged (no rewrite on reuse or on any failed run).
4. Record contents: `red[].file` must be the repo-relative POSIX path from the covers tag (`tests/test_rec_tests.py`), NOT the pytest nodeid: the reader's nodeids are relative to the process cwd (`..\..\AppData\...\work\tests\...` in my fixture), and `head` equals `git rev-parse HEAD` of the test root. Only the one column-0 line may change (compare with the line removed: bytes identical).
5. `remedy` must name every green test by function name, contain `not_needed` and the word `commit`, and, when a `red_baseline_gate` record existed but reuse was skipped, contain the word `record`.
6. `--ticket` relative: resolve against `--test-root`, even when the gate's cwd is elsewhere.
7. Run `test_tq500f3ii_gate_record_reuse.py` with a re-run on a `no_red_outcome_among_new_tests` surprise: the first gate run in a fresh temp repo hit the known nested-pytest flake once during my probing (log file absent, tests ERROR).
8. JS ratchet: both twins are over 1000 lines; pay back every added measured line (design/ticket constraint). The driver tests only need `--ticket ${worktreeTicketPath}` / `${ticketPath}` on the gate line and `classification: gateVerdict.halt_classification || "halt"` plus `${gateVerdict.remedy || ""}` in the existing halt message.

### 2026-10-06 18:30 — python-coder (status: handoff)

feedback-id: (submit-failed)
handoff_target: "test-writer"

Implemented record, reuse and green_at_baseline in `_fl_heavy_lane_gate.py` (HEAVY_WRAPPER_KEYS exported and used at both seam sites), `--ticket` in `_fl_cli.py` and `fast_lane.py` (one pass-through line), both JS twins (gate command, `classification: gateVerdict.halt_classification || "halt"`, `${gateVerdict.remedy || ""}` in the halt message), one SKILL.md row, one changelog entry, h3 docstring note.

Strict results (AC_ENFORCE_STRICT=1; nested pytest needs a quiet temp dir here, see notes): 34 passed, 1 failed across `unit_tests/build_orchestration/test_tq500f3ii_*.py` and `unit_tests/workflows/test_tq500f3ii_*.py`. The one failure is `test_gate_pass_writes_record_accepted_by_real_guards`: the test's own fixture ticket lacks four required frontmatter keys (requires_diagram, requires_adr, change_target, risk_surface), so the real `ticket_frontmatter_guard.validate` rejects it independent of the record. Probe with those keys added: the test passes. Handed to test-writer; no test was edited, skipped or weakened.

red_baseline_results:
  - the 9 other test_tq500f3ii_gate_record_reuse.py tests: green
  - test_both_twins_gate_command_carries_ticket_flag[both twins]: green
  - test_green_at_baseline_halt_lists_tests_and_suggests_not_needed[both twins]: green
  - test_gate_pass_writes_record_accepted_by_real_guards: red (fixture defect, handed off)

Ratchet (check_file_size.py): build-feature.js 2958 -> 2948 (10 lines added, 20 removed); build-ticket.js 1642 -> 1631 (11 added, 22 removed); fast_lane.py 392/400; _fl_cli.py 268/400; _fl_heavy_lane_gate.py 277/400. Paid from the BO-2000e-2 precondition comment block above each driver loop; the handoff block and in-loop history comments are untouched.

Not done: `python scripts/build.py` (outputs are gitignored, no tracked mirror exists for the changed files).

## Escalation

Branch: opus (rubric trigger: more than 5 affected files and a cross-package change; no always-large trigger). `architect-review-deep` is outside this agent's spawn allowlist, so the deep review was done inline with the code read at HEAD.


### 2026-10-07 06:56 — test-writer (status: ok)

feedback-id: (submit-failed)

Fixed `_write_ticket` in `test_tq500f3ii_gate_record_reuse.py`: the fixture now carries requires_diagram: false, requires_adr: false, change_target: [code], risk_surface: [internal], so the real guard sees a valid ticket. The guard assertion and the status-less negative control are unchanged.
Strict run (private TEMP): 35 passed. Discrimination: in a temp copy with the gate's record line replaced by invalid YAML, the test goes red (recorded: false at the first assertion).

### 2026-10-07 12:00 — pr-reviewer (status: ok)

feedback-id: (submit-failed)

No high-confidence findings. Medium findings (not blocking):
- M-1 _fl_heavy_lane_gate.py _record_reusable: the subset check only requires every RECORDED red test to still be newly added. A test added after the record (resumed test-writer) is never verified red, and a recorded test edited to pass trivially still reuses. K1 holds for the recorded set only.
- M-2 A hand-written red_baseline_gate line (passed true, matching source_ac, red naming any existing newly-added covers test) bypasses the gate. Accepted risk at the documented trust level (equals sign-offs); SKILL.md row forbids agent writes. Empty red, passed != true, source_ac superset/subset/reordered-equal, renamed/deleted test, git or partition failure, duplicate line all fall through to the reader (checked).
- M-3 MERGE CONFLICT with ticket 02 (worktree build-tooling-runs-through, staged): it rewrites the same BO-2000e-2 comment block as a /* */ block in build-feature.js (about 1883-1900) and build-ticket.js (about 1513-1533), where this ticket's ratchet payment shortens it. Resolve by taking one comment form (keep BO-2000e-2 id and the three routes), then re-check check-file-size after merge. Gate-line hunks (2110/2132, 1747/1769) do not overlap 02's hunks.
Verified: writer anchoring, duplicate/missing-fence refusal, atomic replace, line endings kept, re-parse, no file created for a missing ticket, relative --ticket against --test-root; HEAVY_WRAPPER_KEYS complete and excludes interpreter; halt_classification/remedy only on all-green refusal; remedy names green tests, not_needed, the commit, and the record; non-reraising excepts all log or surface record_error; BO-2000e-2 id retained; SKILL.md row and changelog accurate.

### 2026-10-07 14:30 — test-runner (status: ok)

feedback-id: (submit-failed)

No test attributable to this ticket fails. Env: private TEMP/TMP, AC_ENFORCE_STRICT=1, PYTEST_ADDOPTS=--rootdir=<private dir> (rootdir override kept for all runs, discovery fine), `-p lfopen` (local plugin, scratchpad on PYTHONPATH).

```yaml
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "step-2 run has 69 failed + 1 error, all but two also fail at base 119fca8e2 (pre-existing); the two extra pass serially in both trees (flake under -n auto)"
    remediation: "none for this ticket; pre-existing failures belong to other tickets"
  failure_report_structured: true
  counts:
    step1_tq500f3ii_files: "35 passed"
    step2_new_tree: "69 failed, 1311 passed, 4 xfailed, 1 error, 298 subtests passed (283s)"
    step2_base_tree: "67 failed, 1290 passed, 4 xfailed, 1 error, 298 subtests passed (262s)"
  split:
    attributable: 0
    pre_existing: "failing in both trees: acd_2100a/b/c, bo2400*, bo_100e, bo_2600a_5, bo_3000a_3700, bo_400e_4, bundle_blank_lines, epic_removed_work_verdict, epic_ticket_set_recheck, inf_700a_5*, phase_dispatch_ticket_path_pointer, unbuilt_work_count, durable_write (error)"
    flake: "test_tq500f3i_h1_kind_pairing_bug::test_h1a_declared_absence_plus_declared_bare_assert_in_one_batch and test_tq500f3ii_heavy_lane_gate_subcommand::test_heavy_lane_gate_verdict_equals_verify_red_baseline_no_second_reader fail only under -n auto (nested pytest ERROR); serial re-run passes in both trees (11 passed new, 9 passed base)"
    base_lacks_ticket_01: "none distinguishable"
  real_world_check:
    command: "fast_lane.py heavy_lane_gate on a COPY of this ticket"
    first_run: "gate_passed false, reason all_new_tests_green_at_baseline, halt_classification green_at_baseline, remedy present (names tests, not_needed)"
    second_run_same_copy: "gate_passed true, recorded true, record_error null; red_baseline_gate line written (passed true, head d7d1255da, source_ac [TQ-500f-3-ii], red list)"
    fresh_copies_x3: "pass, recorded true; rerun on the same copy returned a reused verdict (no red/green keys)"
    caveat: "the red set differs on every run (0..5 tests): the gate's own pytest runs this ticket's nested-pytest tests, which are env-flaky here (CRLF trap, no lfopen), so red/green at baseline is nondeterministic on this host"
```

### 2026-10-07 07:37 — commit (status: ok)
feedback-id: (submit-failed)
Subject: "fix(build-orchestration): record the red-baseline gate's pass and reuse it on resume"

```yaml
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
```
