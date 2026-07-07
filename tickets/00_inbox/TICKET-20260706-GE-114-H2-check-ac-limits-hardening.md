---
status: open
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
components:
  - guardrail-engine
agents:
  test-writer: needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architect-review: not_needed
  adr: not_needed
  diagram: not_needed
files_touched:
  - templates/scripts/commit_guardian/hooks/check_ac_limits.py
  - unit_tests/commit_guardian/test_check_ac_count_limits.py
depends_on:
  - TICKET-20260706-GE-114-check-ac-limits-flat-format-fix
ac_coverage: 0/8
---

# check_ac_limits: harden decoy-heading cap evasion (Gap 1), fence cross-boundary undercount (Gap 2), and add override+fence test coverage (Gap 3)

## Summary

Three residual hardening items deferred from GE-114 (PR #207):

- **Gap 1 (primary defect):** A ticket with an empty `## Agent Contracts` heading evades the 20-total AC cap because `_analyse_ticket` routes to the v2 path on heading presence alone, then counts ACs only inside that section's block — yielding zero when the block is empty, even if AC lines exist elsewhere in the body.
- **Gap 2:** The H-1 `re.DOTALL` fence-strip regex can pair an unterminated opening fence with a later closing fence from a different block, silently stripping real AC lines and producing a false under-count.
- **Gap 3:** No test covers the `ac_limit_override: true` + fenced-code-block combination path; H-1 test additions carry `# covers: UNKNOWN` markers.

Files: `templates/scripts/commit_guardian/hooks/check_ac_limits.py` and `unit_tests/commit_guardian/test_check_ac_count_limits.py`. Pure stdlib Python. No conftest, `build_phases`, or `commit_guardian.json` changes required.

## Background

`check_ac_limits.py` enforces a 20-total AC cap and a 7-per-agent cap on staged tickets. GE-114 fixed silent skipping of v1-flat tickets that lack an `## Agent Contracts` section; its H-1 follow-up added fenced-code-block stripping so example `- [ ] AC-N:` lines inside code fences are not miscounted.

**Gap 1 — decoy/empty heading evades cap.** `_analyse_ticket` dispatches to the v2 path whenever an `## Agent Contracts` heading is present. The v2 path counts ACs only within that section's block. A ticket with an *empty* `## Agent Contracts` heading followed by 30 real `- [ ] AC-N:` lines in the body outside that heading counts `total=0` and exits 0 — evading the cap.

The binding behavioral contract is: (a) the 20-total cap applies regardless of where AC lines sit; (b) well-formed v2 tickets preserve identical per-agent counts and behavior. The implementation approach is not pinned — either "fallback to fence-stripped full-body count when the Agent Contracts block yields zero AC lines" or "always use full-body count for the total" is acceptable, provided both (a) and (b) are satisfied.

**Gap 2 — cross-boundary fence strip.** The H-1 pattern `re.compile(r"```.*?```", re.DOTALL)` pairs the *first* opening fence with the *next* closing fence in the document. A malformed ticket with an unterminated opening fence will reach into a later, independently opened fence block and strip real AC lines between them, producing an under-count that lets an over-limit ticket pass silently. The fix must restrict stripping to properly terminated fences only.

**Gap 3 — test coverage and cosmetic.** No test exercises `ac_limit_override: true` combined with a fenced-code-block containing `- [ ] AC-N:` lines. GE-114 AC store entries exist at `docs/acceptance-criteria/guardrail-engine/GE-114-1..4.yaml`, so `# covers: UNKNOWN` markers in H-1 additions should be updated.

**Verification path:** HOOK_TEST_DIFF direct invocation of `check_ac_limits.py` against fixture diffs. The hook id vs. script name mismatch (`check-ac-tree-limits` vs `check_ac_limits.py`) is tracked as BP-100b-11 and is **out of scope** here.

## Acceptance Criteria

<!-- Gap 1 — primary defect (enforce cap regardless of AC placement) -->
- [ ] AC-1: Given a ticket fixture containing an empty `## Agent Contracts` heading and exactly 30 `- [ ] AC-N:` lines in the body outside that heading, when `check_ac_limits.py` is invoked via HOOK_TEST_DIFF, it exits non-zero with `total_ac_count=30` and `has_violations=True`.
- [ ] AC-2: Given every pre-existing well-formed v2 test fixture in `test_check_ac_count_limits.py`, when the test suite is run after the Gap 1 change, all pre-existing v2 test cases pass with the same per-agent counts and exit codes as before the change.
- [ ] AC-3: A new unit test for the AC-1 scenario exists in `test_check_ac_count_limits.py`, is named or labelled to identify it as the decoy-heading cap evasion case (Gap 1), and is confirmed red before the implementation change and green after.

<!-- Gap 2 — cross-boundary fence undercount -->
- [ ] AC-4: Given a ticket fixture with an unterminated opening fence followed by a separately closed fenced block (mimicking a malformed ticket), when `check_ac_limits.py` is invoked via HOOK_TEST_DIFF, the AC count reported equals the count produced by the equivalent well-formed fixture that has no unterminated fence — no real AC lines are silently stripped.
- [ ] AC-5: A new unit test for the AC-4 scenario exists in `test_check_ac_count_limits.py`, is named or labelled to identify it as the cross-boundary fence handling case (Gap 2), and is confirmed red before the implementation change and green after.

<!-- Gap 3 — override + fence coverage and cosmetic -->
- [ ] AC-6: A new unit test in `test_check_ac_count_limits.py` exercises `ac_limit_override: true` together with a fenced-code-block containing `- [ ] AC-N:` lines; the test asserts the hook exits 0 and the fenced lines are not counted toward the cap.
- [ ] AC-7: Every `# covers: UNKNOWN` marker introduced in the H-1 additions to `test_check_ac_count_limits.py` is replaced with a real GE-114 AC ID (from `docs/acceptance-criteria/guardrail-engine/GE-114-1..4.yaml`) or a descriptive placeholder referencing the behaviour under test.

<!-- Full suite green -->
- [ ] AC-8: The full test suite in `unit_tests/commit_guardian/test_check_ac_count_limits.py` passes with zero new failures after all Gap 1, Gap 2, and Gap 3 changes are applied (test-runner green phase confirmed; see Known Baseline for pre-existing failures that are excluded from this count).

## Test Requirements

**Test-first (red phase):** `test-writer` must author failing tests for AC-1/AC-3, AC-4/AC-5, and AC-6 before `python-coder` touches `check_ac_limits.py`. Tests must be self-contained inline fixtures — no shared conftest additions.

**Fixture design — Gap 1 (AC-1, AC-3):**
- A string fixture representing a ticket with an empty `## Agent Contracts` heading followed by exactly 30 `- [ ] AC-N:` lines outside that heading.
- A second fixture representing a well-formed v2 ticket with a correctly populated Agent Contracts block (for non-regression, AC-2).
- HOOK_TEST_DIFF invocation required for AC-1; unit-test function interface sufficient for AC-3.

**Fixture design — Gap 2 (AC-4, AC-5):**
- A string fixture with an unterminated `` ``` `` block followed by a complete `` ```...``` `` fence containing non-AC content, with real `- [ ] AC-N:` lines placed between the stray opening and the next fence.
- An equivalent fixture without the unterminated fence. Assert counts match.
- HOOK_TEST_DIFF invocation required for AC-4; unit-test function interface sufficient for AC-5.

**Fixture design — Gap 3 (AC-6):**
- A string fixture with `ac_limit_override: true` in YAML frontmatter and a fenced code block containing `- [ ] AC-N:` lines. Assert hook exits 0 and fenced lines are excluded from the count.
- Unit-test function interface sufficient.

**Error-handling constraints:** Implementation changes must not introduce `E722` (bare except), `BLE001` (blind exception), or `TRY`-family violations. Only stdlib modules may be used in `check_ac_limits.py`.

**Green phase:** `test-runner` runs `pytest unit_tests/commit_guardian/test_check_ac_count_limits.py -v` and confirms zero failures in that file.

## Known Baseline

The following pre-existing failures exist in `unit_tests/commit_guardian/` and are **not** regressions attributable to this ticket. `ticket-supervisor` must not halt on them:

- `unit_tests/commit_guardian/test_build_precommit.py` — pre-existing failures
- `unit_tests/commit_guardian/test_check_ac_governance.py` — pre-existing failures
- `unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py` — pre-existing failures
- `unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py` — pre-existing failures

The CI "Test suite (pytest)" job also fails at the build step due to pre-existing unresolvable skill-registry refs (`documentation-expert→direct-write`, `python-coder→run-tests`). This is not a regression.

The TDD baseline for this ticket is scoped to the new tests in `test_check_ac_count_limits.py` only.

## Comments

<!-- Phase agents append status comments here using the canonical heading schema. -->

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 | `test_check_ac_count_limits.py` (Gap 1 decoy-heading HOOK_TEST_DIFF fixture) | `check_ac_limits.py` `_analyse_ticket` | — |
| AC-2 | Pre-existing v2 test cases in `test_check_ac_count_limits.py` | `check_ac_limits.py` `_analyse_ticket` | — |
| AC-3 | `test_check_ac_count_limits.py` (Gap 1 unit test, named, red→green) | `check_ac_limits.py` `_analyse_ticket` | — |
| AC-4 | `test_check_ac_count_limits.py` (Gap 2 cross-boundary HOOK_TEST_DIFF fixture) | `check_ac_limits.py` fence-strip logic | — |
| AC-5 | `test_check_ac_count_limits.py` (Gap 2 unit test, named, red→green) | `check_ac_limits.py` fence-strip logic | — |
| AC-6 | `test_check_ac_count_limits.py` (Gap 3 override+fence unit test) | `check_ac_limits.py` override path | — |
| AC-7 | `test_check_ac_count_limits.py` (UNKNOWN markers resolved) | — | — |
| AC-8 | `pytest unit_tests/commit_guardian/test_check_ac_count_limits.py` green | All changed files | — |
