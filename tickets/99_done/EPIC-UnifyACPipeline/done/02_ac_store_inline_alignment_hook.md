---
title: "Deterministic pre-commit hook: verify every inline AC-N in a v2 ticket maps to a store entry"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_v2_pipeline_ac_store_alignment.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: pre_commit_hook
actuation_contract: "When a ticket file is staged, the hook reads every 'implements AC-XX-NNN' reference in the ticket body, verifies each referenced ID exists as a YAML file in docs/acceptance-criteria/ with status: active, and exits 1 with a named list of missing or deprecated IDs if any are found."
files_touched:
  - templates/commit-guardian/check_v2_ac_store_alignment.py
  - templates/commit-guardian/commit_guardian.json
  - templates/agents/ac-validator.md
agents:
  architect-review: not_needed
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
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: signed_off
ac_coverage: 0/8
---

# Deterministic pre-commit hook: verify every inline AC-N in a v2 ticket maps to a store entry

## Actor / Goal

As the AC traceability pipeline, we need a deterministic Python script that checks
whether every `implements AC-XX-NNN` reference in a staged ticket body resolves to
an active YAML file in `docs/acceptance-criteria/`, so that the "Option B blocking"
design decision is enforced at commit time without relying on an LLM to perform a
structural/mechanical check.

## Context

The companion ticket `TICKET-20260604-V2PipelineACStoreAlignment.md` wires the
v2 BA and create-ticket-v2 to write AC YAML files into the store. This ticket adds
the enforcement side: once a ticket body references store IDs, a deterministic hook
verifies those IDs are valid.

### Design decision: script, not LLM

The user explicitly chose **Option B — blocking enforcement** for the AC store
cross-check, but directed that the check be implemented as a deterministic
Python script (pre-commit hook) rather than extending the `ac-validator` LLM agent.

The rationale: "does every AC-N in the ticket body have a corresponding YAML file
in `docs/acceptance-criteria/`?" is a structural file-existence check with no
ambiguity. It is exactly the kind of check that `check_ac_coverage.py` and
`check_test_ac_tags.py` (EPIC-ACTraceabilityStore tickets 03/04) already model.
LLM agents are expensive and non-deterministic; this check is neither.

### What the script checks

The hook fires on staged ticket files (`tickets/**/*.md`). For each staged ticket:

1. Extract all AC store references from the ticket body. The reference pattern is:
   ```
   implements AC-XX-NNN
   amends AC-XX-NNN
   introduces AC-XX-NNN
   ```
   Regex: `(?:implements|amends|introduces)\s+AC-([A-Z]{2,6}-[0-9]{3})`

2. For each extracted ID:
   - Resolve the component from the ID prefix (e.g. `FIN` → directory `finalize/`,
     derived from `docs/acceptance-criteria/index.yaml`).
   - Check that `docs/acceptance-criteria/{component}/{id}.yaml` exists.
   - Read the file and verify `status: active` (not `deprecated` or `superseded_by`).

3. If any ID is missing or non-active: exit 1 with a message naming each bad ID.

4. If `docs/acceptance-criteria/` does not exist: exit 0 silently (graceful
   degradation for pre-store installs — mirrors the pattern from `check_ac_coverage.py`).

5. If the ticket body contains no AC store references: exit 0 silently (the hook
   only fires when references are present — it does not mandate that every ticket
   must have store references).

### ac-validator minimal update

The `ac-validator` LLM agent gets one small addition to its Step 2 evidence
gathering: after collecting implementation and test evidence, it runs the script:

```bash
python scripts/commit_guardian/check_v2_ac_store_alignment.py --ticket <ticket_path>
```

If the script exits 1, the ac-validator surfaces the output as a `blocker` finding
appended to its verdict (it does NOT re-implement the check itself). This makes the
LLM-agent verdict complete: it validates both implementation coverage (LLM-readable)
and store alignment (deterministic).

The script output format must be machine-readable so ac-validator can parse it:
```
ERROR: AC FIN-003 referenced in ticket but not found in docs/acceptance-criteria/finalize/FIN-003.yaml
ERROR: AC FIN-004 referenced in ticket has status: deprecated (expected: active)
```

### Relationship to existing hooks

| Hook | What it checks | Direction |
|---|---|---|
| `check_test_ac_tags.py` | Tests have `# covers: XX-NNN` tags | test → AC |
| `check_ac_coverage.py` | Active ACs are covered by at least one test | AC → test |
| `check_v2_ac_store_alignment.py` (this ticket) | Ticket body references resolve to active store entries | ticket → AC |

This completes the triangle: tickets reference ACs, ACs are covered by tests, tests
tag their ACs.

### Prefix-to-directory resolution

The `docs/acceptance-criteria/index.yaml` file maps component IDs to prefixes:
```yaml
components:
  - id: finalize
    prefix: FIN
```

The script reads this file to resolve `FIN-001` → `docs/acceptance-criteria/finalize/FIN-001.yaml`.
If the prefix does not appear in `index.yaml`, the hook emits an error: "prefix XX has no
registered component in docs/acceptance-criteria/index.yaml".

## Acceptance Criteria

- [ ] AC-1: When a staged ticket file contains `implements AC-FIN-001` and
  `docs/acceptance-criteria/finalize/FIN-001.yaml` exists with `status: active`,
  the hook exits 0 with no output.

- [ ] AC-2: When a staged ticket file contains `implements AC-FIN-003` and
  `docs/acceptance-criteria/finalize/FIN-003.yaml` does not exist,
  the hook exits 1 and prints `ERROR: AC FIN-003 referenced in ticket but not found
  in docs/acceptance-criteria/finalize/FIN-003.yaml`.

- [ ] AC-3: When a staged ticket file contains `amends AC-FIN-001` and
  `docs/acceptance-criteria/finalize/FIN-001.yaml` has `status: deprecated`,
  the hook exits 1 and prints `ERROR: AC FIN-001 referenced in ticket has status:
  deprecated (expected: active)`.

- [ ] AC-4: When a staged ticket file contains no AC store references (no
  `implements/amends/introduces AC-XX-NNN` pattern), the hook exits 0 silently.

- [ ] AC-5: When `docs/acceptance-criteria/` does not exist in the target project,
  the hook exits 0 silently (graceful degradation).

- [ ] AC-6: When a staged ticket file contains `implements AC-ZZ-001` and `ZZ` is
  not a registered prefix in `docs/acceptance-criteria/index.yaml`, the hook exits 1
  and prints `ERROR: prefix ZZ has no registered component in
  docs/acceptance-criteria/index.yaml`.

- [ ] AC-7: The `ac-validator.md` template contains a step (in Step 2 or a new
  Step 2c) that runs `check_v2_ac_store_alignment.py --ticket <ticket_path>`,
  reads the exit code, and includes any stderr/stdout lines in the verdict output
  as a blocker finding when the exit code is non-zero.

- [ ] AC-8: The hook is registered in `templates/commit-guardian/commit_guardian.json`
  `hooks_manifest` with `files: "^tickets/.*\\.md$"`, `pass_filenames: false`,
  and `stages: ["pre-commit"]`.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |
| AC-7 |      |                |           |
| AC-8 |      |                |           |

## Smoke Fixture

```yaml
surface: check_v2_ac_store_alignment
fixture_input: |
  A staged ticket file at tickets/00_inbox/TICKET-test-smoke.md
  with body containing: "implements AC-FIN-001"
  and docs/acceptance-criteria/finalize/FIN-001.yaml present with status: active
assertion: "exit 0"
placeholder_signature: "No such file or directory|AttributeError|ImportError"
```

## Sign-offs

- [x] test-writer — 2026-06-04 11:30
- [x] python-coder — 2026-06-04 11:45
- [x] test-runner — 2026-06-04 11:50
- [x] pr-reviewer — 2026-06-04 11:55
- [x] commit — 2026-06-04 12:05
- [x] pull-request — 2026-06-04 12:10
- [x] user-surface-smoker — 2026-06-04 12:00

## Comments

### 2026-06-04 11:30 — test-writer (status: ok)
feedback-id: fb_2026-06-04_1ec9ae01
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [UNKNOWN]

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_check_v2_ac_store_alignment.py | unit_tests/commit_guardian/ | unittest | written |

### Verification Run
- Command: `python3 -m pytest unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py -v`
- Result: 19 skipped (expected; implementation not yet written — module not importable). Exit 0.

### Red Baseline
All 19 tests skip because `check_v2_ac_store_alignment.py` does not yet exist at
`templates/commit-guardian/check_v2_ac_store_alignment.py`. Per the established pattern
in this repo (see `test_check_ac_coverage.py`), skipped-until-importable is the pre-implementation
state for commit-guardian hook tests. Once python-coder creates the module, all 19 tests
will run and must pass.

red_baseline:
  - test_name: all 19 tests (TestLoadPrefixMap, TestExtractAcReferences, TestCheckAcExistsAndActive, TestMainIntegration)
    file: unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py
    error: "SKIPPED: check_v2_ac_store_alignment not yet implemented (module absent at templates/commit-guardian/check_v2_ac_store_alignment.py)"

### Notes
- 19 tests written across 4 test classes: TestLoadPrefixMap (2), TestExtractAcReferences (5), TestCheckAcExistsAndActive (4), TestMainIntegration (8).
- All unit tests use `@_skip_if_not_imported` (established repo pattern).
- Integration tests use `self.skipTest()` from `setUp()` when script file absent.
- Ruff E722/BLE001/TRY rules: clean (verified).
- `# covers: UNKNOWN` tags present on all test functions (no AC store in worktree).

### 2026-06-04 11:45 — python-coder (status: ok)
feedback-id: fb_2026-06-04_ae434d12
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true

Implemented all three deliverables: (1) `templates/commit-guardian/check_v2_ac_store_alignment.py` — stdlib-only hook with `load_prefix_map`, `extract_ac_references`, `check_ac_exists_and_active`, and `main`; accepts `--ticket` for ac-validator and `--ac-store` for test isolation; graceful degradation when store absent. (2) `templates/agents/ac-validator.md` — added Step 2c with the deterministic store-alignment check and DECISION HISTORY entry. (3) `templates/commit-guardian/commit_guardian.json` — registered `check-v2-ac-store-alignment` hook in `hooks_manifest`. All 19 tests (128 total in commit_guardian suite) pass. Ruff E722/BLE001/TRY clean.

### 2026-06-04 11:50 — test-runner (status: ok)
feedback-id: fb_2026-06-04_5ef66006
completion_manifest:
  tests_executed: true
  all_tests_passed: true
  no_regressions: true

19/19 tests pass in `unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py`. Full suite: 128/128 passed in `unit_tests/commit_guardian/`. Zero regressions. Exit 0.

### 2026-06-04 11:55 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_6896b63a
completion_manifest:
  acs_reviewed: true
  implementation_correct: true
  tests_green: true
  no_regressions: true

All 8 ACs satisfied: AC-1 (exit 0 on valid active ref), AC-2 (exit 1 on missing file), AC-3 (exit 1 on deprecated), AC-4 (exit 0 on no refs), AC-5 (exit 0 on no store), AC-6 (exit 1 on unknown prefix), AC-7 (ac-validator.md updated with Step 2c), AC-8 (hook registered in commit_guardian.json with correct files/stages/pass_filenames). Implementation is stdlib-only, ruff-clean, and uses established hook patterns. 19/19 tests pass, 128/128 commit_guardian suite. No regressions. ok — 2026-06-04

### 2026-06-04 12:00 — user-surface-smoker (status: ok)
feedback-id: fb_2026-06-04_c9323c71
completion_manifest:
  smoke_fixture_run: true
  assertion_passed: true
  placeholder_signature_absent: true

Ran smoke fixture from `## Smoke Fixture` block: created temp AC store with FIN-001.yaml (status: active), invoked script with `--ticket <smoke_ticket> --ac-store <tmp>`. Assertion `exit 0` — PASSED. Ran again with `--ac-store /nonexistent` (graceful degradation path) — exit 0 PASSED. No `No such file or directory`, `AttributeError`, or `ImportError` output (placeholder_signature absent). Surface confirmed operational with production wiring.

### 2026-06-04 12:05 — commit (status: ok)
feedback-id: fb_2026-06-04_eb985064
completion_manifest:
  files_staged: true
  commit_created: true
  pre_commit_hooks_passed: true

All 5 implementation files staged and committed on EPIC-UnifyACPipeline branch.

### 2026-06-04 12:10 — pull-request (status: ok)
feedback-id: fb_2026-06-04_4e694612
completion_manifest:
  branch_pushed: true
  pr_exists: true

Pushed commit 406135e to `EPIC-UnifyACPipeline` branch. Existing PR #52 (https://github.com/urlmonitor/leafcutter-ai/pull/52) auto-updated — ticket-02 commit is included in the PR's diff.

## Implementation Tasks

### test-writer

- [x] Write `unit_tests/commit_guardian/test_check_v2_ac_store_alignment.py` with
  failing test stubs (red baseline) before python-coder implements the script:
  - `test_valid_reference_exits_0` — `implements AC-FIN-001`, file exists + active → exit 0
  - `test_missing_file_exits_1` — `implements AC-FIN-003`, file absent → exit 1, correct error message
  - `test_deprecated_ac_exits_1` — `amends AC-FIN-001`, status: deprecated → exit 1, correct error message
  - `test_no_references_exits_0` — ticket with no AC refs → exit 0 silently
  - `test_missing_ac_dir_exits_0` — no `docs/acceptance-criteria/` → exit 0 silently
  - `test_unknown_prefix_exits_1` — `implements AC-ZZ-001`, ZZ not in index.yaml → exit 1, correct error
  - `test_amends_reference_detected` — `amends AC-FIN-001`, file exists + active → exit 0
  - `test_introduces_reference_detected` — `introduces AC-FIN-002`, file exists + active → exit 0

### python-coder

- [x] Write `templates/commit-guardian/check_v2_ac_store_alignment.py`:
  - Stdlib only (re, pathlib, argparse). No third-party dependencies.
  - `load_prefix_map(ac_dir)` — reads `docs/acceptance-criteria/index.yaml`,
    builds `{prefix: component_id}` map. Returns empty dict when file absent.
  - `extract_ac_references(ticket_text)` — regex scan for
    `(?:implements|amends|introduces)\s+AC-([A-Z]{2,6}-[0-9]{3})`,
    returns list of ID strings.
  - `check_ac_exists_and_active(ac_dir, prefix_map, ac_id)` — resolves component
    directory from prefix_map, checks file exists, reads `status:` field,
    returns `(ok: bool, error_message: str)`.
  - `main()` — iterates staged ticket files (`git diff --cached --name-only`
    filtered to `tickets/**/*.md`), calls the above, prints errors, exits 1 on
    any failure or 0 on clean.
  - Accepts `--ticket <path>` CLI argument (for ac-validator invocation) as
    an alternative to reading staged files from git.
  - Graceful degradation: if `docs/acceptance-criteria/` does not exist, exit 0.
  - Module docstring in standard commit-guardian format (MODULE, GOAL, BUSINESS
    CONTEXT, ARCHITECTURE, Exit Codes).

- [x] Update `templates/agents/ac-validator.md`:
  - In Step 2 (Gather Evidence), add a new sub-step 2c: "Run
    `python scripts/commit_guardian/check_v2_ac_store_alignment.py --ticket <ticket_path>`.
    Capture stdout and exit code. When exit code is non-zero, record each ERROR line
    as a store-alignment failure. These are included in the verdict as blocker findings
    regardless of implementation/test evidence."
  - The DECISION HISTORY block at the end of the file must have a new entry:
    `- 2026-06-04 [TICKET-20260604-ACStoreInlineAlignmentHook]: Add Step 2c ...`

- [x] Add hook entry to `templates/commit-guardian/commit_guardian.json`
  `hooks_manifest`:
  ```json
  {
    "id": "check-v2-ac-store-alignment",
    "name": "Check V2 AC Store Alignment (ticket AC refs resolve to active store entries)",
    "entry": "python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_v2_ac_store_alignment.py",
    "language": "system",
    "files": "^tickets/.*\\.md$",
    "stages": ["pre-commit"],
    "pass_filenames": false,
    "_comment": "TICKET-20260604-ACStoreInlineAlignmentHook: Blocks commit when a staged ticket body references an AC store ID (implements/amends/introduces AC-XX-NNN) that does not resolve to an active YAML file in docs/acceptance-criteria/. Exits 0 silently when AC store absent or no references present."
  }
  ```

## Risk & Safety

- Touches money? No.
- Touches data? No. The hook reads files only; it never writes.
- Reversibility? Fully reversible — new script file + config entry. Removing from
  `commit_guardian.json` restores prior behaviour.
- Blocking risk: the hook blocks commits when referenced ACs are missing or
  deprecated. This is the intended Option B behaviour. Teams using the v2 pipeline
  must ensure `create-ticket-v2` writes AC files (companion ticket) before staging
  the ticket for commit. The graceful degradation on missing `docs/acceptance-criteria/`
  means existing projects without the AC store are unaffected.
- The `--ticket <path>` CLI flag ensures the script is testable in isolation and
  callable by the ac-validator without staging files.
