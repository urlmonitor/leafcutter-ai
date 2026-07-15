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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
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

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
