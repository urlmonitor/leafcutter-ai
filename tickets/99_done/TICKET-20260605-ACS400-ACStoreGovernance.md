---
title: "ACS-400: AC Store Governance — write-lock criteria fields, audit trail, build deployment"
status: done
components:
  - ac_store
  - infrastructure
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/24
source_acs:
  - ACS-400
  - ACS-400a
  - ACS-400a-1
  - ACS-400a-2
  - ACS-400a-3
  - ACS-400a-3-i
  - ACS-400b
  - ACS-400b-1
  - ACS-400b-2
  - ACS-400b-3
  - ACS-400b-3-i
  - ACS-400c
  - ACS-400c-1
  - ACS-400c-2
  - ACS-400c-2-i
  - ACS-400d
  - ACS-400d-1
  - ACS-400d-2
  - ACS-400d-2-i
  - ACS-400e
  - ACS-400e-1
  - ACS-400e-1-i
  - ACS-400e-2
  - ACS-400e-3
ac_path: docs/acceptance-criteria/ac-store/ACS-400-ac-governance/
files_touched:
  - scripts/commit_guardian/check_ac_governance.py
  - scripts/commit_guardian/commit_guardian.json
  - templates/commit-guardian/check_ac_governance.py
  - templates/commit-guardian/commit_guardian.json
  - templates/CLAUDE.md.template
  - unit_tests/commit_guardian/test_check_ac_governance.py
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
complexity: standard
---

# ACS-400: AC Store Governance — write-lock criteria fields, audit trail, build deployment

## Actor / Goal

As the product team, we need the AC store's requirement-defining fields
(`criteria`, `title`, `req_status`, `depends_on`) to be mechanically
write-locked to authorized agents only (product-owner-v3, business-analyst-v3,
it-po-v3, and the human user), so that implementation agents can never silently
rewrite what they are being measured against.

## Context

The AC store is the authoritative definition of "done" for every piece of work
in the system. If an implementation agent can rewrite `criteria` without
detection, the team loses the trustworthy source of truth that makes
ticket-driven development tractable.

Three enforcement surfaces are needed:

1. **Pre-commit hook** (`check_ac_governance.py`): catches unauthorized field
   changes at commit time before they reach the repository.
2. **Build deployment**: the hook and governance rules are automatically
   installed into every consumer project via `build.py` / the templates
   mechanism — no manual opt-in required.
3. **Agent instruction injection**: the `CLAUDE.md.template` carries the
   governance rules so every agent in every consumer project inherits them
   at invocation time.

All ACs are pre-written at:
`docs/acceptance-criteria/ac-store/ACS-400-ac-governance/`

## Agent Contracts

### test-writer

Write the full test suite **before** `python-coder` begins implementation.
All tests must pass on the final implementation.

- [x] AC-1: `unit_tests/commit_guardian/test_check_ac_governance.py` exists and
  covers the authorized-agent allow path (ACS-400a-1): given a staged AC YAML
  with a new `criteria` field and `origin_agent: business-analyst-v3`, the
  hook exits 0 and produces no blocking output. <!-- signed: test-writer -->
- [x] AC-2: Test covers the modification allow path (ACS-400a-2): given a staged
  diff where `criteria` changed and the committer is `it-po-v3`, the hook exits
  0. <!-- signed: test-writer -->
- [x] AC-3: Test covers the unauthorized agent block path (ACS-400a-3): given
  `criteria` changed by `python-coder`, the hook exits 1 and stdout contains the
  agent name, the file path, and the phrase "criteria field may only be written
  by requirement authors". <!-- signed: test-writer -->
- [x] AC-4: Test covers the human-user allow path (ACS-400a-3-i): given
  `origin_agent: BrainCandy` (not in `config/agent_registry.json`), the hook
  exits 0 — unknown identities are treated as human users. <!-- signed: test-writer -->
- [x] AC-5: Test covers the implementation-agent progress fields allow path
  (ACS-400b-1, ACS-400b-2): `python-coder` changing only `work_status`,
  `implemented_by`, or `covered_by` — hook exits 0. <!-- signed: test-writer -->
- [x] AC-6: Test covers the protected field rejection path (ACS-400b-3): an
  implementation agent changes `title` or `req_status` or `depends_on` —
  hook exits 1 and the error lists each modified protected field. <!-- signed: test-writer -->
- [x] AC-7: Test covers the mixed-commit rejection path (ACS-400b-3-i): same
  commit has `work_status` changed (allowed) AND `criteria` changed (blocked) —
  hook exits 1 for the criteria violation, and the error message acknowledges
  both changed fields. <!-- signed: test-writer -->
- [x] AC-8: Test covers the `origin_agent` audit check (ACS-400c-1): a new AC
  YAML file staged without an `origin_agent` field — hook exits 1 with "new AC
  file requires origin_agent to identify the criteria author". <!-- signed: test-writer -->
- [x] AC-9: Test covers the `amended_by` audit check (ACS-400c-2): an existing
  AC has `criteria` changed in the staged diff but `amended_by` list is
  identical to HEAD — hook exits 1 with "criteria was modified but amended_by
  was not updated". <!-- signed: test-writer -->
- [x] AC-10: Test covers the stale `amended_by` check (ACS-400c-2-i): the
  `amended_by` list exists but has no new entries compared to HEAD — hook exits
  1 and the error distinguishes "no new entry" from "list is empty". <!-- signed: test-writer -->
- [x] AC-11: Test covers the fail-open path (ACS-400e-1-i): the hook encounters
  a YAML parse exception — exits 0, no stdout, diagnostic message on stderr. <!-- signed: test-writer -->
- [x] AC-12: Test covers the no-AC-store early-exit path (ACS-400d-2-i): no
  `docs/acceptance-criteria/` directory exists — hook exits 0 in under 100 ms
  without creating any directories. <!-- signed: test-writer -->
- [x] AC-13: Test covers the staged-files-only scope (ACS-400e-2): 100 AC YAML
  files on disk but only 2 staged — hook parses only 2 files (assert via a
  counter or mock). <!-- signed: test-writer -->
- [x] AC-14: Test covers the non-AC-file neutrality (ACS-400e-3): commit
  includes `scripts/build.py` (valid change) plus an AC YAML with unauthorized
  `criteria` change — hook exit 1 message references only the AC file, not
  `build.py`. <!-- signed: test-writer -->

**Delivers to python-coder:** Verified test suite that `check_ac_governance.py`
must satisfy before `test-runner` can sign off.

### python-coder

Implement three deliverables. Tests written by `test-writer` must pass.

- [x] AC-15: `scripts/commit_guardian/check_ac_governance.py` exists, follows
  the same module-docstring + DECISION HISTORY + Google-style docstring
  conventions as `check_ac_limits.py`, and passes all 14 test-writer ACs
  (AC-1 through AC-14). <!-- signed: python-coder -->
- [x] AC-16: The hook reads the agent identity from `config/agent_registry.json`
  (not hard-coded): any string not in the registry is treated as a human user
  (ACS-400a-3-i). The registry is loaded once per hook invocation (not on every
  file iteration). <!-- signed: python-coder -->
- [x] AC-17: Protected fields (`criteria`, `title`, `req_status`, `depends_on`)
  and open fields (`work_status`, `implemented_by`, `covered_by`) are declared
  as named constants at module level (not inline strings), so future additions
  require a one-line change (ACS-400b-3 IT requirement). <!-- signed: python-coder -->
- [x] AC-18: Field comparison uses YAML-level comparison (load both staged and
  HEAD versions with PyYAML `safe_load`), not raw text diff, to avoid false
  positives from whitespace or formatting changes (ACS-400c-2 IT requirement). <!-- signed: python-coder -->
- [x] AC-19: Blocked commit output: stdout receives a JSON block decision
  `{"decision": "block", "reason": "..."}` matching the PreToolUse hook
  contract; stderr receives diagnostic detail. The `reason` string contains
  agent identity, file path, violated rule, and authorized agents list
  (ACS-400e-1 IT requirements). <!-- signed: python-coder -->
- [x] AC-20: The entire `main()` body is wrapped in `try/except Exception` that
  exits 0 on any unexpected error (fail-open per ACS-400e-1-i). The exception
  type and message are printed to stderr with a `[check-ac-governance]` prefix. <!-- signed: python-coder -->
- [x] AC-21: `scripts/commit_guardian/commit_guardian.json` gains a new entry in
  `hooks_manifest.hooks` for `check-ac-governance` following the same pattern as
  the existing `check-ac-tree-limits` and `check-ac-schema` entries:
  - `files` pattern: `^docs/acceptance-criteria/.*\\.yaml$`
  - `stages`: `["pre-commit"]`
  - `pass_filenames: false`
  - `_comment` referencing the ACS-400 family <!-- signed: python-coder -->

**Delivers to test-runner:** Implemented `check_ac_governance.py` satisfying
the test suite.

**Delivers to pr-reviewer:** Updated `commit_guardian.json` with the hook
registered in `hooks_manifest.hooks`.

**Depends on test-writer:** Tests (AC-1 through AC-14) must exist before
implementation begins.

### python-coder (template deployment — can run in parallel with hook implementation)

Deploy the hook into the templates so `build.py` propagates it automatically
to every consumer project.

- [x] AC-22: `templates/commit-guardian/check_ac_governance.py` is a verbatim
  copy of the final `scripts/commit_guardian/check_ac_governance.py` (ACS-400d
  deliverable: governance rules travel with the package). It is deployed to
  consumer projects by `build_commit_guardian()` in `build_phases.py` via the
  existing template-copy mechanism. <!-- signed: python-coder -->
- [x] AC-23: `templates/commit-guardian/commit_guardian.json` gains the same
  `check-ac-governance` entry in `hooks_manifest.hooks` as the source
  `scripts/commit_guardian/commit_guardian.json` (ACS-400d-2: no opt-in
  required; hook registered automatically alongside `check-ac-schema` and
  `check-test-ac-tags`). <!-- signed: python-coder -->
- [x] AC-24: `templates/CLAUDE.md.template` gains a new section headed
  `## AC Store — Write-Access Rules` that contains:
  - The list of authorized agents for protected fields:
    `product-owner-v3`, `business-analyst-v3`, `it-po-v3`, human user
  - The list of protected fields: `criteria`, `title`, `req_status`, `depends_on`
  - The list of open fields: `work_status`, `implemented_by`, `covered_by`
  - A one-sentence statement that violation blocks the commit (ACS-400d-1 IT
    requirement: human-readable and concise, suitable for an agent's context window).
  The section must not break existing `{{config.*}}` template placeholder
  resolution when `build.py` compiles the template (ACS-400d-1 IT requirement:
  "Must not break existing CLAUDE.md content"). <!-- signed: python-coder -->

**Delivers to pr-reviewer:** Deployed templates ready for consumer-project
propagation.

**Depends on test-writer:** Template deployment can proceed in parallel with
hook implementation; tests only gate `scripts/` deliverables.

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  | test_check_ac_governance.py:TestAuthorizedAgentAllowPath::test_ac1_authorized_agent_new_criteria_exits_0 | | |
| AC-2  | test_check_ac_governance.py:TestModificationAllowPath::test_ac2_it_po_v3_modifying_criteria_exits_0 | | |
| AC-3  | test_check_ac_governance.py:TestUnauthorizedAgentBlockPath::test_ac3_python_coder_criteria_change_blocked | | |
| AC-4  | test_check_ac_governance.py:TestHumanUserAllowPath::test_ac4_unknown_origin_agent_treated_as_human_user | | |
| AC-5  | test_check_ac_governance.py:TestImplementationAgentProgressFieldsAllowPath | | |
| AC-6  | test_check_ac_governance.py:TestProtectedFieldRejectionPath | | |
| AC-7  | test_check_ac_governance.py:TestMixedCommitRejectionPath::test_ac7_mixed_commit_blocked_acknowledges_both_fields | | |
| AC-8  | test_check_ac_governance.py:TestOriginAgentAuditCheck::test_ac8_new_ac_file_missing_origin_agent_blocked | | |
| AC-9  | test_check_ac_governance.py:TestAmendedByAuditCheck::test_ac9_criteria_changed_without_amended_by_update_blocked | | |
| AC-10 | test_check_ac_governance.py:TestStaleAmendedByCheck::test_ac10_stale_amended_by_distinguishes_no_new_entry_from_empty | | |
| AC-11 | test_check_ac_governance.py:TestFailOpenPath::test_ac11_yaml_parse_exception_exits_0_no_stdout | | |
| AC-12 | test_check_ac_governance.py:TestNoACStoreEarlyExitPath::test_ac12_no_ac_store_directory_exits_0_fast | | |
| AC-13 | test_check_ac_governance.py:TestStagedFilesOnlyScope::test_ac13_only_staged_files_parsed_not_all_on_disk | | |
| AC-14 | test_check_ac_governance.py:TestNonACFileNeutrality::test_ac14_non_ac_file_plus_unauthorized_ac_change_error_references_only_ac | | |
| AC-15 |      | scripts/commit_guardian/check_ac_governance.py created, all 14 tests pass | |
| AC-16 | test_check_ac_governance.py:TestConstantsAtModuleLevel::test_authorized_agents_from_registry | _load_registry() loads config/agent_registry.json once per invocation | |
| AC-17 | test_check_ac_governance.py:TestConstantsAtModuleLevel::test_constants_exist_at_module_level | _PROTECTED_FIELDS, _OPEN_FIELDS, _AUTHORIZED_AGENTS as module-level frozensets | |
| AC-18 |      | _load_yaml_safe() uses PyYAML safe_load for YAML-level comparison in _fields_changed() | |
| AC-19 | test_check_ac_governance.py:TestBlockOutputFormat::test_ac19_block_output_is_json_to_stdout | _emit_block_decision() outputs JSON to stdout, diagnostic to stderr | |
| AC-20 | test_check_ac_governance.py:TestFailOpenExceptionHandling::test_ac20_unexpected_exception_exits_0 | main() wrapped in try/except Exception with sys.exit(0) on error | |
| AC-21 |      | scripts/commit_guardian/commit_guardian.json: check-ac-governance entry added to hooks_manifest.hooks | |
| AC-22 |      | templates/commit-guardian/check_ac_governance.py: verbatim copy of implementation | |
| AC-23 |      | templates/commit-guardian/commit_guardian.json: check-ac-governance entry added to hooks_manifest.hooks | |
| AC-24 |      | templates/CLAUDE.md.template: ## AC Store — Write-Access Rules section appended | |

## Sign-offs

- [x] test-writer — 2026-06-05 14:00
- [x] python-coder — 2026-06-05 15:30
- [x] test-runner — 2026-06-05 15:32
- [x] pr-reviewer — 2026-06-05 15:35
- [x] commit — 2026-06-05 15:40
- [x] pull-request — 2026-06-05 15:45

## Risk & Safety

- Touches money? No.
- Touches data? No. The hook reads AC YAML files from the index; it never writes them.
- Reversibility? The hook is a standalone Python script added to
  `commit_guardian.json`. Removing it requires deleting the file and removing its
  entry from `hooks_manifest.hooks` — a single-commit rollback.
- Fail-open guarantee: any unexpected error in the hook exits 0, so no legitimate
  commit is ever blocked by a hook crash (ACS-400e-1-i).
- Risk of regressions: low for existing workflows. The hook only fires on
  `docs/acceptance-criteria/**/*.yaml` staged files. Projects without that
  directory exit early in under 100 ms (ACS-400d-2-i).
- The `CLAUDE.md.template` addition is a pure append with no placeholder tokens,
  so it does not interact with the existing `{{config.*}}` resolution path.

## Comments

### 2026-06-05 15:45 — pull-request (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  branch_pushed: true
  pr_opened: true
  pr_url_recorded: true
Branch feature/acs400-acstoregovernance pushed to origin. PR opened at https://github.com/urlmonitor/leafcutter-ai/pull/68 — "feat(commit-guardian): add AC store governance hook (ACS-400)".

### 2026-06-05 15:40 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Staged 7 files: scripts/commit_guardian/check_ac_governance.py (new), scripts/commit_guardian/commit_guardian.json (modified), templates/CLAUDE.md.template (modified), templates/commit-guardian/check_ac_governance.py (new), templates/commit-guardian/commit_guardian.json (modified), tickets/00_inbox/TICKET-20260605-ACS400-ACStoreGovernance.md (modified), unit_tests/commit_guardian/test_check_ac_governance.py (new). Commit message: feat(commit-guardian): add check_ac_governance.py write-lock hook (ACS-400).

### 2026-06-05 15:35 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_a5901fc2
completion_manifest:
  diff_matches_files_touched: true
  new_tests_pass: true
  no_regressions_in_passing_tests: true
  implementation_quality: true
Review pass. Diff: 7 files, 2692 insertions (+78 deletions on ticket). 24/24 new governance tests green. 9 pre-existing failures in test_check_ac_limits.py (CLI tests requiring hook at a path it doesn't live in this worktree) — not caused by this change. Implementation correctly implements fail-open, registry-driven auth, YAML-level comparison, JSON block output, and module-level constants. Templates deployed and CLAUDE.md.template updated per spec.

### 2026-06-05 15:32 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
24/24 tests pass in unit_tests/commit_guardian/test_check_ac_governance.py (exit 0, 1.23s). Suite: commit-guardian. Command: python3 -m pytest unit_tests/commit_guardian/test_check_ac_governance.py -v.

### 2026-06-05 15:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_08862b3a
completion_manifest:
  hook_implementation_created: true
  all_24_tests_green: true
  registry_driven_auth: true
  module_level_constants: true
  yaml_level_comparison: true
  json_block_output: true
  fail_open_exception_handling: true
  commit_guardian_json_updated: true
  template_hook_deployed: true
  template_json_updated: true
  claude_md_template_updated: true
Implemented `scripts/commit_guardian/check_ac_governance.py` (AC-15 through AC-21): write-locks criteria/title/req_status/depends_on to authorized agents; registry-driven human-user detection; YAML-level field comparison; JSON block decision on stdout; fail-open on all exceptions. Deployed template copy (AC-22), updated both commit_guardian.json files (AC-21, AC-23), appended ## AC Store — Write-Access Rules to CLAUDE.md.template (AC-24). All 24 tests green (exit 0).

red_baseline_results:
  - test_name: TestImportSuccess::test_module_imports_successfully
    result: green
  - test_name: all 23 remaining tests (previously skipped, now executed)
    result: green

### 2026-06-05 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_7ab6b377
completion_manifest:
  test_file_created: true
  all_14_acs_have_test_coverage: true
  tests_are_red: true
  ac_coverage_table_test_column_filled: true
  red_baseline_captured: true
Wrote `unit_tests/commit_guardian/test_check_ac_governance.py` with 24 test methods covering AC-1 through AC-14 (plus structural/import tests). Verification run confirms exit code 1 (red): `TestImportSuccess::test_module_imports_successfully` fails with AssertionError because `scripts/commit_guardian/check_ac_governance.py` does not yet exist; 23 further tests skip via `_requires_import` guard and will activate once python-coder creates the hook. Test structure follows the `test_check_ac_limits.py` pattern used in this codebase.

red_baseline:
  - test_name: TestImportSuccess::test_module_imports_successfully
    file: unit_tests/commit_guardian/test_check_ac_governance.py
    error: "AssertionError: False is not true : Hook script not found at /home/henzeh/projects/worktrees/acs400-acstoregovernance/scripts/commit_guardian/check_ac_governance.py. python-coder must create it before test-runner runs."
  - test_name: TestAuthorizedAgentAllowPath::test_ac1_authorized_agent_new_criteria_exits_0 (and 22 siblings)
    file: unit_tests/commit_guardian/test_check_ac_governance.py
    error: "SKIPPED: check_ac_governance not importable: [Errno 2] No such file or directory: '...check_ac_governance.py'"
    note: "23 tests skip via _requires_import guard — will execute once hook is implemented"
