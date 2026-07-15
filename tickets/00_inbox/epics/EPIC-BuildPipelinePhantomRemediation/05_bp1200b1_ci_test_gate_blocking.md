---
title: "CI test job must be a blocking gate (drop continue-on-error) without the baseline reds blocking every PR"
status: todo
components:
  - build_pipeline
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-1200b-1
ac_coverage:
  - BP-1200b-1
  - BP-1200b-1-i
  - BP-1200b-1-ii
files_touched:
  - .github/workflows/ci.yml
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Make the CI test gate actually block merges

## Actor / Goal

As the repository CI, I want a **blocking** test check on every pull request — one that
fails the PR when any test fails and is a hard required check, not advisory — so
BP-1200b-1 / -1-i / -1-ii are met and a PR carrying a failing test cannot merge.

## Remediation Context (audit 2026-07-14)

**Gate not blocking.** `.github/workflows/ci.yml` already has a `Test suite (pytest)` job
that runs `python -m pytest tests/ unit_tests/ -q --continue-on-collection-errors` after a
build/shim step — but it carries **`continue-on-error: true`** (with a header comment
"Promote to BLOCKING (drop continue-on-error) once the suite is green"). Because the job is
informational, the AC "the check is a hard, blocking check — not an advisory one" is unmet:
a red suite still lets a PR merge.

**Known baseline hazard.** Per CLAUDE.md, the "Test suite (pytest)" job currently fails on
`main` itself (build-guard: templates reference missing `scripts/feedback/*.py`), and PRs
merge UNSTABLE with only ruff + schema-diff required. Naively dropping `continue-on-error`
would block **every** PR on the pre-existing ~baseline reds. BP-1200b-1's it_requirements
make this an explicit hard prerequisite on BP-1200a-1 / ADR-016 (fresh-clone green via the
build step + `install_shims` shim bridge, decided Approach 1).

**Do: gate correctly, don't just flip the flag.** The ticket must address *how* to gate
without the baseline reds blocking everything — e.g. (a) land/verify the ADR-016 fresh-clone
fix so the suite is green on a clean checkout first, then drop `continue-on-error`; or
(b) scope the blocking gate to the green subset (a dedicated `test` job over the passing
directories/markers) while the legacy informational job stays until baseline is fixed.
Preserve existing ci.yml conventions (actions/checkout@v4, setup-python@v5 py3.13,
requirements-dev.txt, ubuntu-latest, pull_request→main). **Pin a stable job `name:`** — it
is the cross-AC contract BP-1200c-1 adds to the branch-protection required-status-checks
list; if the name changes, branch protection silently stops requiring it. The build/shim
prepare step must fail loudly (non-zero) rather than skip to a misleading green.

## Acceptance Criteria

Resolves BP-1200b-1, BP-1200b-1-i, BP-1200b-1-ii (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/BP-1200-ci-test-gate/`). Definition of done: a PR
with a deliberately-failing test drives the check red and is reported not-mergeable; a PR
whose suite passes drives the check green and is not blocked by this check; the check is
blocking (no `continue-on-error`) and its job name is stable for BP-1200c-1.

## Test Requirements

```yaml
tests:
  - name: test_ac_bp1200b1_test_job_is_blocking
    file: unit_tests/build_guards/test_ci_test_gate.py
    covers: [BP-1200b-1]
    asserts: the ci.yml blocking test job exists with a stable name and does NOT set continue-on-error.
  - name: test_ac_bp1200b1i_failing_test_blocks_merge
    file: unit_tests/build_guards/test_ci_test_gate.py
    covers: [BP-1200b-1-i]
    asserts: a run with a failing test yields a red (blocking) check conclusion / not-mergeable.
  - name: test_ac_bp1200b1ii_green_suite_does_not_block
    file: unit_tests/build_guards/test_ci_test_gate.py
    covers: [BP-1200b-1-ii]
    asserts: a green suite yields a passing check that does not, by itself, block the merge (no false-negative, no flap).
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
