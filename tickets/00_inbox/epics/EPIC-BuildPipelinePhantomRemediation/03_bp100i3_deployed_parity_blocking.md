---
title: "Hook parity: a manifest-referenced script missing from the deployed tree must BLOCK the commit (exit 1)"
status: todo
components:
  - commit_guardian
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-100i-3
ac_coverage:
  - BP-100i-3
files_touched:
  - templates/scripts/commit_guardian/check_hook_parity.py
  - unit_tests/commit_guardian/test_check_hook_parity.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 03: Missing deployed hook script must be a blocking parity violation

## Actor / Goal

As the pre-commit hook-parity check, I want a script that exists in the canonical
template but is absent from the deployed output directory to **block the commit with
exit 1** (naming the missing scripts and the deployed dir checked), so BP-100i-3 is
enforced instead of contradicted.

## Remediation Context (audit 2026-07-14)

**Opposite behaviour + test locks the inverse.** In
`templates/scripts/commit_guardian/check_hook_parity.py`, `check_deployed_parity`
deliberately **downgrades** missing-deployed-script findings to a non-blocking INFO
warning (decision M-3): it prints `check-hook-parity: INFO — the following scripts exist
in canonical template ... (Non-blocking.)` and returns no violation for the missing case.
Its test in `unit_tests/commit_guardian/test_check_hook_parity.py` asserts
`violations == []` for exactly the missing-script scenario — i.e. code **and** test assert
the opposite of BP-100i-3, whose criteria require the commit blocked with exit code 1 and
the missing script names listed.

**Do: reconcile toward the AC, don't rewrite the module.** Promote the missing-deployed
case from INFO to a **blocking** violation: `check_deployed_parity` must append a violation
string that (a) lists each script present in the canonical template but absent from the
deployed output and (b) names the deployed output directory checked, so the outer runner
exits 1. Preserve the genuine fail-open behaviour required by BP-100i-3's it_requirements —
still exit 0 on unexpected I/O errors (unreadable/nonexistent dir), determine the deployed
dir from `commit_guardian.json`/`skills_config.json` (not hardcoded), stay idempotent and
under the 2s budget. Then rewrite the inverted test that asserts `violations == []` for the
missing case so it asserts the blocking violation + the M-3 downgrade decision is reversed.

## Acceptance Criteria

Resolves BP-100i-3 (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100i-3.yaml`). Definition
of done: given canonical has 5 scripts and deployed has 3, the parity check blocks with exit
1, the error lists the 2 missing scripts and names the deployed dir; unexpected-error paths
still fail-open (exit 0).

## Test Requirements

```yaml
tests:
  - name: test_ac_bp100i3_missing_deployed_scripts_block_commit
    file: unit_tests/commit_guardian/test_check_hook_parity.py
    covers: [BP-100i-3]
    asserts: canonical-minus-deployed scripts produce a blocking violation (exit 1) listing the missing names and the deployed dir; replaces the test that asserted violations == [].
  - name: test_ac_bp100i3_unexpected_error_still_fails_open
    file: unit_tests/commit_guardian/test_check_hook_parity.py
    covers: [BP-100i-3]
    asserts: an unreadable/absent deployed dir exits 0 (fail-open), distinguishing I/O errors from parity violations.
```

## Sign-offs

- [x] test-writer — 2026-08-18 14:02
- [x] python-coder — 2026-08-18 15:20
- [ ] test-runner
- [x] pr-reviewer — 2026-08-18 15:02
- [ ] commit
- [ ] pull-request

## Comments

### 2026-08-18 14:02 — test-writer (status: ok)
feedback-id: fb_2026-08-18_1e7e5f9d
completion_manifest:
  new_tests_written: true
  inverted_tests_reconciled: true
  red_baseline_confirmed: true
(classification: production_drift) — per the ticket's Remediation Context, `check_deployed_parity`
in `templates/scripts/commit_guardian/check_hook_parity.py` deliberately downgrades the
missing-deployed-script case to a non-blocking INFO warning (decision M-3), which is the opposite
of BP-100i-3's Gherkin (block with exit 1, list missing scripts, name the deployed dir). Production
is wrong relative to the approved AC; the three existing tests that asserted `violations == []` for
this scenario were mirroring the same bug, not testing a legitimate alternate contract. No
return-shape narrowing/widening is involved (still `list[str]`), so Rule 2 blast-radius enumeration
does not apply — only new violation-string entries are added to the list for a scenario that
previously produced none.

Wrote/rewrote tests in `unit_tests/commit_guardian/test_check_hook_parity.py` (TestDeployedParity,
TestDeployedParityContentHash):
- Replaced `test_script_in_canonical_absent_from_deployed_emits_warning` with
  `test_ac_bp100i3_missing_deployed_scripts_block_commit` — the ticket's AC scenario verbatim
  (canonical 5 scripts / deployed 3), asserts a blocking violation naming both missing scripts and
  the deployed dir.
- Renamed/reversed `test_script_in_canonical_absent_from_deployed_genuine_drift_exits_0` →
  `..._genuine_drift_blocks` — asserts blocking instead of `violations == []`.
- Renamed/reversed `test_only_in_canonical_missing_from_deployed_stays_nonblocking` →
  `..._now_blocks` — asserts blocking instead of `violations == []`.
- Added `test_ac_bp100i3_unexpected_error_still_fails_open` (new) — an unreadable (chmod 0o000)
  deployed dir must still return `[]` (fail-open), guarding against the coder's blocking fix
  conflating a genuine I/O error with "every canonical script is missing."
- Left the BP-100i-3-i "deployed dir absent entirely" tests untouched — that fail-open path is
  unaffected by this reversal.

Verification run: `python3 -m pytest unit_tests/commit_guardian/test_check_hook_parity.py -v` →
3 failed, 36 passed (36 pre-existing tests untouched by this ticket's scope stayed green; the 3
rewritten/new blocking-assertion tests are red as expected — production still has the M-3
downgrade). `test_ac_bp100i3_unexpected_error_still_fails_open` passed immediately against the
current (pre-fix) implementation — this is expected, not under-specified: the current code
treats every missing-script case as non-blocking, which trivially satisfies "unreadable dir must
not block" too; the test's purpose is to remain green after python-coder's fix, guarding against
a regression where the fix treats an I/O error the same as a genuine parity violation. Per the
red_baseline schema note, it is therefore omitted from the `red_baseline` block below (no
red_baseline entry for a passing test), but is called out here as the intentional exception.

### 2026-08-18 15:02 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_scenario_matches_gherkin: true
  blocking_violation_lists_names_and_dir: true
  fail_open_iid_error_path_preserved: true
  no_high_confidence_findings: true
  full_suite_green: true
Reviewed the diff to `check_deployed_parity` and its tests against BP-100i-3's verbatim
Gherkin. The missing-deployed-scripts case is now a genuine blocking violation string naming
each missing script and the deployed output directory, matching the AC's 5-canonical/3-deployed
scenario exactly (`test_ac_bp100i3_missing_deployed_scripts_block_commit`); the M-3
downgrade-to-INFO path was fully removed rather than left dormant. The new `deployed_dir.iterdir()`
readability probe correctly distinguishes a genuine I/O error (fail-open, exit 0 — verified via
the chmod-0o000 test) from "every canonical script missing," which is exactly the pitfall
`_collect_hook_scripts`'s own OSError-swallowing would otherwise have caused. Ran the full test
file directly (`python3 -m pytest unit_tests/commit_guardian/test_check_hook_parity.py -q`): 39
passed, 0 failed. `ruff check` is clean on both changed files. No high- or medium-confidence
findings. Two minor, non-blocking observations (not worth a finding): (1) `check_deployed_parity`
now calls `deployed_dir.iterdir()` twice (once for the readability probe, once inside
`_collect_hook_scripts`) — harmless given the 2s/50-script budget, but a `try/except` directly
around the existing `_collect_hook_scripts(deployed_dir, ...)` call would avoid the duplicate
listing; (2) the deployed runtime copy of this very script
(`scripts/commit_guardian/check_hook_parity.py`, dated Jul 14) has not yet been rebuilt from the
canonical template edited here — expected pre-merge/pre-build.py state, not a defect, but note
that the next `build.py` run (or the first commit attempted before it) will itself now trip the
newly-blocking content-hash/missing-script check against this ticket's own file until rebuilt.
Also noted: `test-runner` is still `needed` on this ticket ahead of `pr-reviewer` in the agents
list; I independently ran the full test file green as part of this review, but the supervisor
should still ensure `test-runner` completes its own sign-off pass.

red_baseline:
  - test_name: test_ac_bp100i3_missing_deployed_scripts_block_commit
    file: unit_tests/commit_guardian/test_check_hook_parity.py
    error: "AssertionError: [] == [] : BP-100i-3: scripts present in canonical but absent from an existing deployed dir must produce a BLOCKING violation."
  - test_name: test_script_in_canonical_absent_from_deployed_genuine_drift_blocks
    file: unit_tests/commit_guardian/test_check_hook_parity.py
    error: "AssertionError: [] == [] : BP-100i-3: genuine-drift case must now block (M-3 downgrade reversed)."
  - test_name: test_only_in_canonical_missing_from_deployed_now_blocks
    file: unit_tests/commit_guardian/test_check_hook_parity.py
    error: "AssertionError: [] == [] : BP-100i-3: script only in canonical (missing from deployed) must block."

### 2026-08-18 15:20 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  red_baseline_all_green: true
  no_prior_passing_test_broken: true
  fail_open_preserved: true
  real_artifact_spotcheck_run: true
  doc_enforcer: true
  complexity_check: true
red_baseline_results:
  - test_name: test_ac_bp100i3_missing_deployed_scripts_block_commit
    result: green
  - test_name: test_script_in_canonical_absent_from_deployed_genuine_drift_blocks
    result: green
  - test_name: test_only_in_canonical_missing_from_deployed_now_blocks
    result: green
Reversed the M-3 downgrade in `check_deployed_parity` (templates/scripts/commit_guardian/check_hook_parity.py):
a script present in canonical but absent from an existing deployed dir is now a BLOCKING
violation naming the missing scripts and the deployed dir, and the prior INFO-only path was
removed. Added an explicit `deployed_dir.iterdir()` readability probe before comparison so a
genuine I/O error (e.g. an unreadable/chmod 0o000 dir) still fails open (exit 0) rather than
being conflated with "every canonical script missing" -- this was necessary because
`_collect_hook_scripts` already swallows OSError into an empty set, which would otherwise have
made the new blocking path treat an I/O error as 100% drift. Updated the module docstring and
DECISION HISTORY. All 39 tests in unit_tests/commit_guardian/test_check_hook_parity.py pass,
including the 3 red_baseline tests (now green) and the new
test_ac_bp100i3_unexpected_error_still_fails_open (unaffected, per test-writer's note). Ran a
real-artifact spot-check of check_deployed_parity against this repo's actual
templates/scripts/commit_guardian vs .leafcutter/scripts/commit_guardian dirs in a fresh
process -- it correctly flagged this very file as content-diverged (not yet rebuilt), confirming
the function works against the real deployed tree, not just synthetic fixtures. ruff and the
check_complexity.py hook both pass clean on the modified file. A broader
unit_tests/commit_guardian/ run showed 89 pre-existing failures in unrelated files
(test_check_agent_spawn_consistency.py, test_done_proof_ci_changed_scope.py,
test_precommit_canary.py, test_transform_hooks_and_autofix_emission.py,
test_verify_precommit_active.py) that do not import or reference check_hook_parity.py --
confirmed pre-existing and out of this ticket's scope. submit_feedback.py is absent from this
worktree, so feedback-id is (submit-failed) per the documented fallback.
