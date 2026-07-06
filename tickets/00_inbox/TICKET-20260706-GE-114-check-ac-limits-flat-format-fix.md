---
ac_coverage: 7/7
advances_current_outcome: true
agents:
  architect-review: not_needed
  commit: signed_off
  documentation-expert: not_needed
  frontend-coder: not_needed
  pr-reviewer: signed_off
  pull-request: signed_off
  python-coder: signed_off
  test-runner: signed_off
  test-writer: signed_off
  user-surface-smoker: not_needed
complexity: simple
components:
  - guardrail-engine
created: '2026-07-06'
depends_on: []
files_touched:
  - templates/scripts/commit_guardian/hooks/check_ac_limits.py
  - unit_tests/commit_guardian/test_check_ac_count_limits.py
origin_agent: create-ticket-v2
out_of_scope:
  - "Hook id/script name mismatch (check-ac-tree-limits vs check_ac_limits.py) — deferred to BP-100b-11"
  - "Per-agent cap (7) enforcement on the v1-flat path; only the 20-total cap governs flat tickets"
  - "Any changes to the tree-depth hook at templates/scripts/commit_guardian/check_ac_limits.py"
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
status: done
title: "Fix silent skip of 20-total AC cap for v1-flat ticket format in check_ac_limits hook"
user_facing_surface: null
---

# Fix silent skip of 20-total AC cap for v1-flat ticket format in check_ac_limits hook

## Goal

`templates/scripts/commit_guardian/hooks/check_ac_limits.py` enforces a 20-total AC cap per ticket and
a 7-per-agent cap per agent block. In `_analyse_ticket`, when a ticket has no `## Agent Contracts`
section (v1 flat format), the hook currently sets `result.skipped = True` and returns — silently
bypassing all caps. A v1-flat ticket with 30 ACs is never blocked.

Fix `_analyse_ticket` so that when `## Agent Contracts` is absent, it counts all `- [ ] AC-N:` lines
across the **full ticket body** (whole-body count is more robust to heading-name variance) and applies
the 20-total cap instead of skipping. Hard-block on violation (exit 1), matching v2 behaviour. The
per-agent cap (7) is NOT applied on the v1-flat path — it requires the `### <agent>` subsection
structure.

**Multiple template copies exist on disk.** Before editing any file, the implementer must confirm which
copy `build.py` reads as its canonical source:

- `templates/scripts/commit_guardian/hooks/check_ac_limits.py` — the ticket-body AC count hook
  (contains the `_analyse_ticket` function with the bug described above)
- `templates/scripts/commit_guardian/check_ac_limits.py` — the AC tree-depth hook (different function,
  different scope — do NOT edit this one)
- `scripts/commit_guardian/check_ac_limits.py` — built output (do NOT edit; `build.py` regenerates it)

**Pre-fix required scan.** Before finalising the hard-block behaviour, the implementer must scan
`tickets/` for any v1-flat ticket currently exceeding 20 `- [ ] AC-N:` lines and add
`ac_limit_override: true` to those tickets' frontmatter so the new block does not break them. Report
the count of affected tickets in the sign-off comment.

**Verification must use direct invocation.** Because the hook id `check-ac-tree-limits` and the script
name `check_ac_limits.py` do not match (id/name cleanup deferred to BP-100b-11), the precommit wiring
may not invoke this specific hook. Verify the fix by invoking the hook directly:

```
HOOK_TEST_DIFF=/path/to/fixture-diff.txt python templates/scripts/commit_guardian/hooks/check_ac_limits.py
```

## Acceptance Criteria

- [x] AC-1: Given a staged ticket `.md` with no `## Agent Contracts` section and more than 20 lines
  matching `^\s*-\s*\[\s*\]\s*AC-\d+:` anywhere in the body, when `_analyse_ticket` runs, then
  `result.skipped` is `False`, `result.total_ac_count` is greater than 20, `result.total_violation`
  is `True`, and the hook exits 1.

- [x] AC-2: Given a staged v1-flat ticket with no `## Agent Contracts` section and 20 or fewer
  `- [ ] AC-N:` lines in the body, when `_analyse_ticket` runs, then `result.skipped` is `False`,
  `result.total_violation` is `False`, `result.violations` is empty, and the hook exits 0.

- [x] AC-3: Given a staged v1-flat ticket whose body exceeds 20 flat ACs and whose frontmatter
  contains `ac_limit_override: true`, when the hook runs, then `override_active` is `True`, the
  commit is not blocked (exit 0), and a warn-only message identifying the ticket is emitted to stderr.

- [x] AC-4: Given a staged v1-flat ticket exceeding 20 flat ACs without the override flag, when the
  hook emits the JSON violation payload to stderr, then the shape is
  `{"hook": "check_ac_limits", "fix_agent": "it-po", "violations": [{"type": "total", "count": N, "limit": 20}]}`
  with no `per_agent` violation entries, so precommit-autofix routing is unchanged.

- [x] AC-5: Given a staged ticket containing a `## Agent Contracts` section with `### <agent>`
  subsections, when `_analyse_ticket` runs after the fix, then per-agent counts and the total are
  computed identically to pre-fix behaviour — no regression on the v2 Agent Contracts path.

- [x] AC-6: `result.skipped = True` is set only when the ticket file cannot be read from disk
  (`OSError`) — never solely because `## Agent Contracts` is absent from the ticket body.

- [x] AC-7: All six new unit tests in `unit_tests/commit_guardian/test_check_ac_count_limits.py`
  pass under `pytest`; `ruff check templates/scripts/commit_guardian/hooks/check_ac_limits.py`
  exits 0 with no new E722/BLE001/TRY violations.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 | test_check_ac_count_limits.py::test_v1_flat_over_20_acs_not_skipped | _analyse_ticket: v1-flat branch counts body ACs, sets total_violation=True | pytest green; e2e exit 1 |
| AC-2 | test_check_ac_count_limits.py::test_v1_flat_within_20_acs_passes | _analyse_ticket: v1-flat branch, skipped=False, no violation at <=20 | pytest green |
| AC-3 | test_check_ac_count_limits.py::test_v1_flat_override_warns_not_blocks | override+v1-flat else branch: total_ac_count set from _count_acs_in_block | pytest green |
| AC-4 | test_check_ac_count_limits.py::test_json_payload_shape_v1_flat_violation | _build_json_payload: total violation, no per_agent entries | pytest green; stderr JSON verified |
| AC-5 | test_check_ac_count_limits.py::test_v2_agent_contracts_path_regression | v2 path unchanged: per_agent + total_ac_count via contracts_block | pytest green |
| AC-6 | test_check_ac_count_limits.py::test_oserror_sets_skipped_not_missing_contracts | skipped=True only in OSError except block | pytest green |
| AC-7 | (not testable: requires implementation + ruff to exist; verified by test-runner post-fix) | 6/6 tests pass; ruff check exits 0 | pytest 6/6 green; ruff exit 0 |

## Implementation Tasks

### python-coder

- [x] Confirm which copy of `check_ac_limits.py` is the canonical source that `build.py` reads; edit
  only that copy. (The ticket-body hook with `_analyse_ticket` lives in
  `templates/scripts/commit_guardian/hooks/check_ac_limits.py`.)
- [x] Scan `tickets/` for any v1-flat ticket currently exceeding 20 `- [ ] AC-N:` lines and add
  `ac_limit_override: true` to those tickets' frontmatter before the hard-block behaviour is
  finalised. Report the count in the sign-off comment.
- [x] In `_analyse_ticket`: when the Agent Contracts section is absent, count `_AC_LINE_RE` matches
  across the full ticket body (not just the AC section) and apply the 20-total cap
  (`_MAX_ACS_TOTAL`). Set `result.total_violation = True` and populate `result.total_ac_count`.
  Do NOT set `result.skipped = True` on this path.
- [x] Ensure the `ac_limit_override: true` branch also runs the flat AC count so the override path
  correctly identifies whether the total exceeds 20 (mirrors existing v2 override path behaviour).
- [x] Verify the fix by invoking the hook directly with a test diff fixture (not via precommit
  wiring) — see the Goal section for the invocation form.
- [x] Run `ruff check templates/scripts/commit_guardian/hooks/check_ac_limits.py` and confirm exit 0
  with no new E722/BLE001/TRY violations.

### test-writer

- [x] Create `unit_tests/commit_guardian/test_check_ac_count_limits.py`; load the ticket-body hook
  from `templates/scripts/commit_guardian/hooks/check_ac_limits.py` via `importlib` (same pattern as
  `test_check_ac_limits.py` uses for the tree-depth hook — see lines 31–40 of that file for the
  shim pattern).
- [x] Confirm RED baseline for each new test before the fix is applied; record the RED baseline in
  the sign-off comment.
- [x] Write `test_v1_flat_over_20_acs_not_skipped`: v1-flat ticket body with 21 `- [ ] AC-N:` lines
  → `skipped=False`, `total_ac_count=21`, `total_violation=True`.
- [x] Write `test_v1_flat_within_20_acs_passes`: v1-flat ticket with exactly 20 such lines →
  `skipped=False`, `total_violation=False`, `violations=[]`.
- [x] Write `test_oserror_sets_skipped_not_missing_contracts`: monkeypatch `Path.read_text` to raise
  `OSError` → `skipped=True`; AND assert that a successful read with no Agent Contracts does NOT
  produce `skipped=True` after the fix.
- [x] Write `test_v1_flat_override_warns_not_blocks`: v1-flat with 21 ACs and
  `ac_limit_override: true` in frontmatter → `override_active=True`, hook exits 0.
- [x] Write `test_json_payload_shape_v1_flat_violation`: `_build_json_payload` (or equivalent) for a
  v1-flat total violation produces `{"hook": "check_ac_limits", "fix_agent": "it-po", "violations": [{"type": "total", "count": N, "limit": 20}]}`
  with no `per_agent` entries.
- [x] Write `test_v2_agent_contracts_path_regression`: ticket with `## Agent Contracts` and a
  `### python-coder` subsection of 3 ACs → `per_agent = {"python-coder": 3}`, `total_ac_count=3`,
  `skipped=False`, `total_violation=False`.

## Test Requirements

```yaml
test_requirements:
  rationale: >
    The fix modifies a conditional branch in _analyse_ticket; unit tests must confirm
    the v1-flat path enforces the total cap at every boundary (over-limit, at-limit,
    OSError, override active) and must assert the v2 Agent Contracts path is not
    regressed. No existing test file covers the ticket-body hook
    (templates/scripts/commit_guardian/hooks/check_ac_limits.py).
  tests:
    - name: test_v1_flat_over_20_acs_not_skipped
      description: "v1-flat ticket body with 21 AC lines is not marked skipped and total_violation is True"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat path, total cap enforcement"

    - name: test_v1_flat_within_20_acs_passes
      description: "v1-flat ticket with exactly 20 AC lines produces no violation and exits 0"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat path, within cap"

    - name: test_oserror_sets_skipped_not_missing_contracts
      description: "skipped=True occurs only on OSError; absent Agent Contracts section alone does not set skipped=True after the fix"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — OSError path and skipped=True guard"

    - name: test_v1_flat_override_warns_not_blocks
      description: "v1-flat ticket with >20 ACs and ac_limit_override: true sets override_active=True and does not block"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v1-flat with override"

    - name: test_json_payload_shape_v1_flat_violation
      description: "JSON payload for a v1-flat total violation contains type:total with no per_agent violation entries"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_build_json_payload — v1-flat total violation shape"

    - name: test_v2_agent_contracts_path_regression
      description: "Ticket with ## Agent Contracts section produces correct per-agent counts and total — no regression from the flat-path fallback addition"
      type: unit
      target_dir: unit_tests/commit_guardian/
      covers: "_analyse_ticket — v2 Agent Contracts path regression guard"
```

## Open Questions

- The `test_requirements` block was synthesised during refinement (test-planner output was absent from
  the BA payload) and should be reviewed by `test-writer` before driving.
- Implementer must confirm and document the canonical source template path before editing any file —
  see the Goal section for the three candidate paths.
- Pre-fix ticket scan: report the count of v1-flat tickets that required `ac_limit_override: true`
  in the sign-off comment (per the hard-block resolution from the answered open question).

## Sign-offs

- [x] python-coder — 2026-07-06
- [x] test-writer — 2026-07-06 17:01
- [x] test-runner — 2026-07-06
- [x] pr-reviewer — 2026-07-06 18:30
- [x] commit — 2026-07-06 16:29
- [x] pull-request — 2026-07-06

## Comments

### 2026-07-06 — python-coder (status: ok)
canonical_source_path: templates/scripts/commit_guardian/hooks/check_ac_limits.py
canonical_source_confirmed: >
  build_commit_guardian() in scripts/build_phases.py reads from
  TEMPLATES_DIR / "scripts" / "commit_guardian" and uses rglob("*") —
  this copies the hooks/ subdirectory too. So the canonical template is
  templates/scripts/commit_guardian/hooks/check_ac_limits.py. The other
  candidates (templates/scripts/commit_guardian/check_ac_limits.py = tree-depth
  hook; scripts/commit_guardian/hooks/check_ac_limits.py = built output) were
  NOT edited.
pre_fix_scan:
  v1_flat_tickets_over_20_acs: 0
  tickets_requiring_override: []
  note: "No existing ticket needs ac_limit_override: true — safe to enable hard-block."
red_baseline_results:
  - test_name: test_v1_flat_over_20_acs_not_skipped
    result: green
  - test_name: test_v1_flat_within_20_acs_passes
    result: green
  - test_name: test_oserror_sets_skipped_not_missing_contracts
    result: green
  - test_name: test_v1_flat_override_warns_not_blocks
    result: green
  - test_name: test_json_payload_shape_v1_flat_violation
    result: green
  - test_name: test_v2_agent_contracts_path_regression
    result: green (was already green — regression guard preserved)
e2e_fixture_invocation:
  over_20_flat_acs: "exit 1 (BLOCKED, JSON payload confirmed, type=total, no per_agent entries)"
  within_20_flat_acs: "exit 0 (passes)"
ruff_check: "exit 0, no violations"
doc_enforcer: "all 14 functions have docstrings; MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE present"
complexity_reduction: "ruff C901 exit 0; _analyse_ticket complexity unchanged vs pre-fix (added 1 branch)"

### 2026-07-06 10:42 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_file_created: true
  red_baseline_confirmed: true
  all_six_tests_written: true
  v2_regression_guard_green: true
  implementation_tasks_checked: true
Created `unit_tests/commit_guardian/test_check_ac_count_limits.py` with 6 tests loading
the ticket-body hook via importlib shim. 5 tests are RED (implementation not yet written);
1 test (v2 regression guard) is GREEN (existing behavior). Exit code: 1 (non-zero).
red_baseline:
  - test_name: test_v1_flat_over_20_acs_not_skipped
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: True is not false : v1-flat ticket with 21 ACs must NOT be skipped (skipped=True reserved for OSError only)"
  - test_name: test_v1_flat_within_20_acs_passes
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: True is not false : v1-flat ticket with exactly 20 ACs must NOT be skipped"
  - test_name: test_oserror_sets_skipped_not_missing_contracts
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: True is not false : A readable ticket with no ## Agent Contracts section must NOT set skipped=True. skipped=True must be reserved exclusively for OSError."
  - test_name: test_v1_flat_override_warns_not_blocks
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: 0 != 21 : total_ac_count must be 21 (the flat AC count) even when override is active so the warning emission can identify the excess; got 0"
  - test_name: test_json_payload_shape_v1_flat_violation
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: 0 != 1 : Expected 1 ticket entry in payload violations for the v1-flat total violation; got 0. Currently FAILS because _analyse_ticket skips v1-flat tickets, leaving payload violations empty."

### 2026-07-06 — test-runner (status: ok)
suite: unit_tests/commit_guardian/test_check_ac_count_limits.py
result: 6/6 passed
exit_code: 0
ruff_check: "templates/scripts/commit_guardian/hooks/check_ac_limits.py — exit 0, no violations"

### 2026-07-06 — pr-reviewer (status: ok)
verdict: approved
findings: none — implementation is a clean additive branch in _analyse_ticket; no regression on v2 path; ruff and tests green; scope matches files_touched exactly

### 2026-07-06 — commit (status: ok)
commit: feee67e4
message: "fix(guardrail-engine): enforce 20-total AC cap on v1-flat ticket format (GE-114)"
files: templates/scripts/commit_guardian/hooks/check_ac_limits.py, unit_tests/commit_guardian/test_check_ac_count_limits.py, tickets/00_inbox/TICKET-20260706-GE-114-check-ac-limits-flat-format-fix.md

### 2026-07-06 — pull-request (status: ok)
pr_url: https://github.com/urlmonitor/leafcutter-ai/pull/207
pr_title: "fix(guardrail-engine): enforce 20-total AC cap on v1-flat ticket format (GE-114)"

### 2026-07-06 16:05 — test-runner (status: ok)
feedback-id: fb_2026-07-06_10421088
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
6/6 new tests in test_check_ac_count_limits.py pass; 43/43 pre-existing tree-depth hook tests in test_check_ac_limits.py pass with no regression; 6 failures in the broader commit_guardian suite are pre-existing and unrelated to GE-114 (affected files not in diff: test_build_precommit.py, test_check_ac_governance.py, test_check_ticket_signoff_parity_done_folder.py, test_transform_hooks_and_autofix_emission.py).

### 2026-07-06 16:15 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  no_high_confidence_blockers: true
  medium_findings_documented: true
  v2_path_regression_checked: true
  skipped_semantics_verified: true
  json_payload_shape_verified: true
  error_handling_compliant: true
  ac_coverage_all_7_verified: true
Review of diff on branch fix/GE-114-ac-limits-flat-format vs origin/main. No high-confidence blocking issues found. Two medium-confidence findings documented: (1) the BUSINESS CONTEXT docstring in check_ac_limits.py (line 9) still says "v1 tickets are skipped transparently" — stale after the fix; ARCHITECTURE section was updated but BUSINESS CONTEXT was not. (2) AC-4's documented JSON shape is a simplified representation that omits the per-ticket wrapper present in `_build_json_payload` output — the implementation and test are correct but the AC text could mislead a future payload consumer. Medium count = 2, below the >3 Opus escalation threshold; no escalation performed. All AC-1 through AC-7 verified against implementation: skipped=True is reserved exclusively to the OSError path, flat-body count is applied correctly on the no-Agent-Contracts path, per-agent cap is not applied on the flat path, override branch populates total_ac_count, JSON payload omits per_agent violations on flat path, v2 path is unmodified. Ruff and 6/6 unit tests confirmed green by test-runner.

### 2026-07-06 16:29 — commit (status: ok)
feedback-id: fb_2026-07-06_b739e9ca
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed SHA 44a6ff90: docstring correction to BUSINESS CONTEXT section (stale "v1 tickets skipped transparently" → correct flat-ticket cap description), plus test-runner and pr-reviewer sign-off entries. All 34 pre-commit hooks passed (most skipped as file-type filters; Check Feedback ID, Check Secrets, Check ADR Coverage, Check Agent Registry, Check Exception Handling, Check Contract Shrinking, Check Mermaid Diagram Complexity all passed explicitly). No hook failures, no autofix required.

### 2026-07-06 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  h1_tests_added: true
  original_6_still_passing: true
  two_red_tests_confirmed: true
  three_green_tests_confirmed: true
Added 5 H-1 tests to unit_tests/commit_guardian/test_check_ac_count_limits.py.
Tests 1–2 (fence-stripping) are RED — the H-1 fix (strip ``` blocks before counting)
is not yet implemented. Tests 3–5 (main() end-to-end) are GREEN — they confirm
existing GE-114 behavior through main() for the first time. All original 6 tests
continue to pass (9 passed, 2 failed, exit 1).
red_baseline:
  - test_name: TestH1FenceStripping::test_fenced_acs_not_counted
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: 6 != 3 : total_ac_count must be 3 (only real ACs outside fenced blocks); got 6. Current code counts all AC lines including those inside ``` fenced blocks."
  - test_name: TestH1FenceStripping::test_fenced_acs_do_not_cause_false_block
    file: unit_tests/commit_guardian/test_check_ac_count_limits.py
    error: "AssertionError: 21 != 18 : total_ac_count must be 18 (real ACs only, fenced excluded); got 21. Before fix: 21 counted (18 real + 3 fenced lines inside ``` block)."
green_baseline_tests_3_4_5:
  - test_name: TestMainEndToEnd::test_main_exits_1_on_flat_over_limit
    status: green (existing behavior confirmed via main())
  - test_name: TestMainEndToEnd::test_main_exits_0_on_flat_within_limit
    status: green (existing behavior confirmed via main())
  - test_name: TestMainEndToEnd::test_override_warning_message_emitted
    status: green (existing behavior confirmed via main())

### 2026-07-06 — python-coder (status: ok) [H-1 follow-up fix]
h1_fix_description: >
  Strip fenced code blocks before counting AC lines on the v1-flat path and
  flat-override path. Added _FENCED_BLOCK_RE compiled regex constant and
  _strip_fenced_code() pure helper. Both call sites in _analyse_ticket that
  count flat ACs now call _count_acs_in_block(_strip_fenced_code(content)).
  v2 Agent Contracts path is unaffected (counts within contracts_block only).
  DECISION HISTORY updated with H-1 entry.
red_baseline_results:
  - test_name: TestH1FenceStripping::test_fenced_acs_not_counted
    result: green (was: AssertionError 6 != 3; now passes — 3 real ACs counted, 3 fenced excluded)
  - test_name: TestH1FenceStripping::test_fenced_acs_do_not_cause_false_block
    result: green (was: AssertionError 21 != 18 + exit 1; now passes — 18 real ACs, exit 0)
original_6_still_green: true
total_suite: 11/11 passed
direct_invocation:
  fixture_18_real_3_fenced: "exit 0 (correct — fenced lines excluded, 18 < 20 cap)"
  fixture_21_real_no_fenced: "exit 1 (correct — genuine over-limit ticket still blocked)"
ruff_check: "exit 0, no violations (E/F/E722 rules per ruff.toml)"
doc_enforcer: "module docstring has MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE; _strip_fenced_code has full docstring with Args/Returns; all other functions unchanged"
complexity_reduction: "ruff C901 exit 0; _strip_fenced_code is complexity 1 (single return)"

### 2026-07-06 17:53 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
H-1 fence-stripping re-verification: 11/11 tests in test_check_ac_count_limits.py pass (includes 2 new TestH1FenceStripping tests and 3 new TestMainEndToEnd tests added by test-writer for the H-1 followup); 43/43 pre-existing tree-depth hook tests in test_check_ac_limits.py unchanged; full commit_guardian directory suite yields 464 passed, 50 skipped, 6 failed. The 6 failures are exactly the known pre-existing baseline (test_build_precommit.py x2: import-error on scripts.build_precommit; test_check_ac_governance.py x1: hook script not found at scripts/commit_guardian/check_ac_governance.py; test_check_ticket_signoff_parity_done_folder.py x1: done-folder-move check not yet implemented; test_transform_hooks_and_autofix_emission.py x2: transform hooks absent from manifest). No new failures introduced by the H-1 change. Verdict: GREEN.

### 2026-07-06 18:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  h1_delta_reviewed: true
  high_confidence_findings: false
  medium_findings_count: 2
  opus_escalation: false
  unterminated_fence_risk_assessed: true
H-1 re-review (fence-stripping delta only): no high-confidence blockers found. Fix is correct for all well-formed ticket inputs. Two medium findings noted: [M-1] unterminated fence cross-boundary over-stripping — when a ticket has a stray opening ` ``` ` with no close and a later fence's opening acts as the regex close, real ACs between them are eaten (false NEGATIVE, under-count); this requires malformed markdown and is unlikely in production; [M-2] override+fenced-AC test gap — neither H-1 test exercises the override path with fenced content, though the code change is symmetric and correct by inspection. The non-greedy `.*?` pattern is confirmed correct for terminated fences (language tags, adjacent blocks, inline code all handled correctly). The v2 Agent Contracts path is confirmed unaffected. Error-handling Rule 4 satisfied (pure function, no try/except). 11/11 tests green per test-runner. Medium count = 2, below the 3-finding Opus escalation threshold.