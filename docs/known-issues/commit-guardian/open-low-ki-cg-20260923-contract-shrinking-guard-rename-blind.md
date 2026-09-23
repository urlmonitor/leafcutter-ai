---
title: "KI-CG-20260923-contract-shrinking-guard-rename-blind — check-contract-shrinking correlates deleted test names against added test names, so a renamed test reads as a deleted one"
description: "medium. A rename of a test function landed concurrently with production changes is reported as a deleted test, with no fix that fits a rename; the practical response is SKIP=check-contract-shrinking, which erodes the guard's real defense against actual coverage loss."
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260923-contract-shrinking-guard-rename-blind — check-contract-shrinking correlates deleted test names against added test names, so a renamed test reads as a deleted one

> One known issue, filed directly into `commit-guardian/` on 2026-09-23. Index:
> [commit-guardian.md](../commit-guardian.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**`
> line below, unchanged — `medium` indexes as `low` per this register's own
> "How this register is stored" section.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1 (2026-09-22: committing a 25-ticket epic merge)
- **First seen:** 2026-09-22 · **Last seen:** 2026-09-22
- **Where:** hook id `check-contract-shrinking`, script
  `templates/scripts/commit_guardian/check_contract_shrinking.py`. `_find_deleted_tests`
  (around line 152) computes `removed - added` over test-function *names* matched by the
  removed/added `def test_...` patterns across the diff it is judging; a name that
  vanishes from the "removed" set only if it also appears in "added" is treated as
  covered. A rename removes one name and adds a different one, so the old name never
  reappears in "added" and is reported deleted — the hook has no step that correlates a
  removed name with an added one as the same test relocated.

**Symptom.**

Committing a 25-ticket epic merge, `check-contract-shrinking` blocked with "Staged diff
contains test-weakening changes concurrent with production code changes" and listed four
deleted test functions:

- `test_permitted_agent_is_resolved_from_the_registry_not_a_hardcoded_name`
- `test_setup_dispatch_to_a_read_only_agent_halts_before_any_authoring_agent`
- `test_unrecognized_final_action_causes_loop_redispatch`
- `test_unrecognized_final_action_returns_error_status`

**Evidence.**

All four were renames, not deletions, and total coverage GREW:

- `unit_tests/workflows/test_bo_1500f_1.py`: 4 tests on `origin/main`, 4 tests after.
  `test_setup_dispatch_to_a_read_only_agent_halts_before_any_authoring_agent` ->
  `test_setup_target_without_shell_permission_halts_before_any_authoring_agent`, and
  `test_permitted_agent_is_resolved_from_the_registry_not_a_hardcoded_name` ->
  `test_permission_follows_the_registry_not_a_hardcoded_agent_name`. The renamed cases
  are STRONGER: they now drive the real on-disk pre-flight script against the real
  registry instead of asserting against a hand-typed verdict literal.
- `unit_tests/test_final_gate_and_commit_message.py`: 2 tests became 3.
  `test_unrecognized_final_action_causes_loop_redispatch` ->
  `test_unrecognized_final_action_is_not_applied`;
  `test_unrecognized_final_action_returns_error_status` ->
  `test_unrecognized_final_action_does_not_return_success_status`; plus a new
  `test_unrecognized_final_action_does_not_commit`. The rename provenance is written
  into the tests' own docstrings.

**Why it matters.**

The hook compares test-function names present before and after. It has no notion of a
rename, so any rename of a test concurrent with production-code changes is
indistinguishable from deleting coverage. Two consequences, and the second is the
dangerous one:

1. **False positive.** A legitimate rename is blocked, and the documented remedy ("fix
   the test in a separate commit with no production code changes") does not fit a
   rename that exists precisely because the production code it covers was
   renamed/relocated.
2. **The real risk.** Because the finding is noisy and the remedy is impractical, the
   habitual response becomes `SKIP=check-contract-shrinking`. A hook that is routinely
   skipped cannot catch the genuine contract shrink it exists for. In this very session
   an ACTUAL contract shrink had already occurred earlier and was signed off by a human
   reading a green "5 passed" without noticing the file had gone from 7 tests to 5. So
   the guard's real quarry is real, and name-blindness is what erodes trust in it.

**Fix direction.** Not implemented — recorded for a future pass.

- Compare test-function COUNT per file alongside names, not names alone.
- Treat a deletion plus an addition within the same file as a candidate rename and
  report it as a rename for review, rather than as weakening.
- Honour an explicit in-file rename marker — the docstring provenance the renamed tests
  above already carry.

**Related.** `KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam`
is the AC-hook family's version of the same blind spot (a rename is invisible to a
`--diff-filter=AM` query); this is the distinct case of a hook that DOES see both halves
of the rename but has no correlation step, so it reports them as an outright deletion
instead of a relocation. `KI-CG-20260914-contract-guard-crashes-on-diff-bytes` is the
same script's other open defect (an unrelated encoding crash on the same code path).
`KI-CG-20260826-1612` records the AC-store guardians' rename blindness at the
query-filter level.

**Pattern:** a guard whose unit of comparison (a bare name) cannot represent the
operation the surrounding work legitimately performs (a rename), so it reports the
sharpest possible false positive — a change that strengthens coverage scores
identically to the failure mode the guard exists to catch — and the practical
fallback (skip the gate) defeats the guard's real purpose.

---
