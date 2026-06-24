---
title: "Make the test suite green on a fresh clone so the CI test gate can become blocking"
status: todo
components:
  - testing_quality
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# Make the test suite green on a fresh clone so the CI test gate can become blocking

> **Wiring note:** this is a tracking ticket captured during the BP-1200a-1
> finalize. It has no `agents:` map yet — run it through `/plan-feature` →
> `/build-ac` (or split into an epic) before driving with `/build-feature`.
> The scope below is almost certainly epic-sized.

## Actor / Goal

As a maintainer, I want `pytest tests/ unit_tests/` to pass with zero failures
on a fresh checkout (after the documented build step), so that the CI `test`
job in `.github/workflows/ci.yml` can be flipped from informational
(`continue-on-error`) to **blocking**, and added to branch protection — the
remaining BP-1200b / BP-1200c deliverables.

## Context

BP-1200a-1 (PR #164, merged 2026-06-24) fixed the build-output/shim dependency:
`install_shims()` now bridges `scripts/{commit_guardian,doc_compliance,feedback}`
to `.leafcutter/scripts/...`, and CI runs `build.py` before pytest (ADR-016).
That was necessary but **not sufficient** — the suite is still not green on a
fresh checkout, so the `test` job was merged as `continue-on-error: true`
(informational). This ticket tracks the work to actually make it green.

Two independent classes of pre-existing breakage block the gate (diagnosed
2026-06-24 on `feature/bp-1200a-1`):

**A. 4 collection errors — test files importing modules that do not exist.**
These are abandoned TDD red-baselines whose production modules were never built:

| Test file | Missing module |
|-----------|----------------|
| `unit_tests/commit_guardian/test_check_test_fixture_bloat.py` | `check_test_fixture_bloat` |
| `unit_tests/test_link_feedback_resolve.py` | `link_feedback` |
| `tests/test_transform_decision_history.py` | `transform_decision_history` |
| `tests/test_known_failing_tests.py` | `known_failing_tests` |

With `pytest -x`, these abort the run at collection before any test executes.

**B. ~18 test failures** — attributed by the test-runner to missing hook
implementations (e.g. `check_agent_spawn_consistency.py`,
`check_ac_done_on_merge.py`) and related gaps. Enumerate precisely with
`pytest tests/ unit_tests/ --continue-on-collection-errors -q` after a build.

## Acceptance Criteria

```gherkin
Given a fresh clone of the repository (no local build outputs present)
When the documented CI test command runs (install requirements-dev.txt,
  run build.py, then pytest tests/ unit_tests/)
Then the full suite passes with zero failures and zero collection errors
  and the result is deterministic across repeated runs (incl. varied
  pytest-randomly seeds)

Given the suite is green and deterministic on a fresh clone
When .github/workflows/ci.yml is updated
Then the `test` job no longer carries continue-on-error (it is blocking) [BP-1200b]

Given the blocking test job is green
When branch protection on main is reviewed
Then the required status checks include both `lint` and the `test` check [BP-1200c]
```

## Implementation Tasks

- [ ] Decide per missing module: build the production module, delete/skip the
      stale red-baseline test, or convert to an explicit `xfail` with a tracking
      reference. Resolve all 4 collection errors.
- [ ] Triage and fix (or justify-and-mark) the ~18 failing tests.
- [ ] Confirm `pytest tests/ unit_tests/` is green + deterministic on a fresh
      `git worktree` of `origin/main` (build first).
- [ ] Flip the `test` job in `.github/workflows/ci.yml` to blocking (remove
      `continue-on-error`). [satisfies BP-1200b]
- [ ] Add the `test` check to branch-protection required status checks on `main`,
      keeping the admin emergency-override exception. [satisfies BP-1200c]
- [ ] Consider whether a `known_failing_tests` allowlist mechanism (one of the
      currently-missing modules) is the intended path for managing any residual
      accepted failures, vs. fixing them all.

## Notes

- Related AC store entries: BP-1200a (fresh-clone prerequisite, partially met by
  BP-1200a-1), BP-1200b (blocking test job), BP-1200c (branch protection).
- The pr-reviewer on PR #164 also flagged that the CI pytest command uses `-x`
  without `--continue-on-collection-errors`; reconsider that flag as part of
  making the suite green.
