---
title: "CI test shards install the web toolchain so runtime-dependent proof tests run"
status: todo
components:
  - build_pipeline
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
roadmap_phase: phase_1
tags:
  - ci
  - test-shard
  - vitest
  - done-proof
last_updated: 2026-10-06
files_touched:
  - .github/workflows/ci.yml
  - unit_tests/ac_store/test_done_proof_js_integration.py
---

# CI test shards install the web toolchain so runtime-dependent proof tests run

## Actor / Goal
In order that the re-enabled CI test gate (BP-1200b) reports real regressions rather than
environment gaps, we need every `test-shard` leg to install the same Node/vitest toolchain the
`done-proof` job already installs, so that the only end-to-end proof that real vitest assertions
drive a composite verdict (BO-2500a-6) runs and passes in CI instead of failing on a missing runtime.

## Context
- **Failing in CI, passing locally.**
  `unit_tests/ac_store/test_done_proof_composite_js.py::test_real_vitest_assertions_control_composite_verdict`
  fails in all three parametrizations on every shard run with
  "Required runtime proof cannot run: install web dependencies with npm ci …". The test
  (`:205-211`) asserts `node` is on PATH and `leafcutter-web/node_modules/vitest/vitest.mjs` exists.
  Locally (toolchain installed) the file is green: 12 passed.
- **The gap is the job, not the test.** The `test-shard` job (`.github/workflows/ci.yml`, job
  `test-shard`) installs only `requirements-dev.txt` and runs `build.py`. It has no
  `actions/setup-node` and no `npm ci --prefix leafcutter-web`. The `done-proof` job already does
  both (`ci.yml`, steps "Set up Node" / "Install leafcutter-web dependencies (provides vitest)",
  Node major `20`, npm cache keyed on `leafcutter-web/package-lock.json`).
- **The sibling file hides the same gap by skipping.**
  `unit_tests/ac_store/test_done_proof_js_integration.py:44-48` wraps its two unmocked seam tests
  (BO-2500e-2) in `@unittest.skipUnless(vitest installed)`. On the shards those tests are silently
  SKIPPED, so the gate has never exercised `run_vitest_and_parse` against the real binary.
  `docs/how-to/prove-ac-done.md` §"Skipped test" (`:151-159`) is explicit: a skip is not proof —
  "Resolve the dependency or make the test runnable".
- **The two siblings disagree on the rule.** The composite file FAILS on a missing runtime; the
  integration file SKIPS. They should follow one rule (see Design Decisions).
- **Windows cannot run the integration tests at all.** Verified 2026-10-06 on Windows 11 with the
  toolchain installed: `run_vitest_and_parse` launches `leafcutter-web/node_modules/.bin/vitest`
  directly, which on every platform is npm's POSIX `#!/bin/sh` shim. `CreateProcess` rejects it:
  `JsRunnerUnavailable: vitest OS error on launch: [WinError 193]`. With the current
  `skipUnless`, an installed Windows checkout therefore runs both tests and they FAIL (2 failed,
  12 passed) — the existing guard is wrong in both directions. The composite test avoids this by
  replacing only the launcher with `node vitest.mjs`; the integration tests cannot, because the
  production binary-path resolution is exactly what they exist to prove.
- Parent requirement: BP-1200b ("A pull request with failing tests is automatically stopped") —
  the shards can only be promoted to a required check once their reds are real regressions.

## Acceptance Criteria
- [ ] AC-1: Every `test-shard` matrix leg runs `actions/setup-node@v4` with `node-version: "20"`
  (the same major as `done-proof`), `cache: "npm"` and
  `cache-dependency-path: leafcutter-web/package-lock.json`, then `npm ci --prefix leafcutter-web`,
  both before the pytest step. Steps and versions are copied from `done-proof`, not re-invented.
- [ ] AC-2: The three `test_real_vitest_assertions_control_composite_verdict` cases
  (`mixed/passing` = `False/True`, `True/True`, `True/False`) pass in CI.
- [ ] AC-3: Both `test_done_proof_js_integration.py` tests RUN (are not reported as skipped) and
  pass on the Linux CI shards.
- [ ] AC-4: Shard wall-clock grows by no more than about 1 minute per leg (setup-node with a warm
  npm cache plus `npm ci`; measured 27 s for `npm ci` locally on a cold `node_modules`).
- [ ] AC-5: The `ci.yml` header comment for `test-shard` documents the web-toolchain dependency:
  what needs it, why it is installed on every leg, and that it mirrors `done-proof`.
- [ ] AC-6: One recorded rule for runtime-dependent proof tests (Design Decisions below), followed
  by both sibling files: a missing runtime FAILS the test with an actionable
  "Required runtime proof cannot run: …" message; it never skips. The only permitted skip is a
  platform on which the code path under test cannot execute at all, with a reason naming that
  platform limitation. `test_done_proof_js_integration.py` is changed to follow it.

## Design Decisions

### Rule: runtime-dependent proof tests fail, they do not skip, when the runtime is missing
A test that serves as proof for an acceptance criterion (`# covers:`) and needs an external runtime
(Node, vitest, a service) must **fail** with an actionable message naming what to install when that
runtime is absent. A skip is not proof (`docs/how-to/prove-ac-done.md` §"Skipped test"), and a
skip keyed on "toolchain installed?" turns an environment gap into a silent green.

The one exception is a **platform** where the code path under test cannot run at all, whatever is
installed. Such a skip must be keyed on the platform, not on the presence of the runtime. Its reason
must name the platform limitation, and the proof must still run on CI.

Applied:
- `test_done_proof_composite_js.py` — already conforms (asserts `node` and `vitest.mjs`; on Windows
  it swaps only the launcher, so it runs everywhere). No change.
- `test_done_proof_js_integration.py` — `skipUnless(vitest installed)` is replaced by a
  runtime check that fails with the same "Required runtime proof cannot run" wording, plus
  `skipIf(os.name == "nt")` whose reason cites `[WinError 193]` and the POSIX shim. This is the
  only escape, and it is genuine: the production seam itself cannot launch on Windows (verified).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | `python -c "yaml.safe_load(...)"` + actionlint over `ci.yml` | `ci.yml` `test-shard` steps | local; CI run after push |
| AC-2 | `test_done_proof_composite_js.py::test_real_vitest_assertions_control_composite_verdict` | `ci.yml` `test-shard` steps | CI run after push |
| AC-3 | `test_done_proof_js_integration.py` (2 tests; check the shard log shows no `s` for them) | `ci.yml` + integration file | CI run after push |
| AC-4 | Compare shard durations with the previous main run | `ci.yml` (npm cache) | CI run after push |
| AC-5 | Review of the `ci.yml` header | `ci.yml` header comment | review |
| AC-6 | Local run of the integration file (Windows: 2 skipped with WinError 193 reason; no toolchain on Linux: 2 failed with install message) | integration file | local; CI run after push |

## Comments

## Implementation Tasks
- [ ] `ci.yml` `test-shard`: add "Set up Node" and "Install leafcutter-web dependencies (provides
  vitest)" after "Install dev dependencies", copied from `done-proof`.
- [ ] `ci.yml` header: document the dependency under `test-shard`.
- [ ] `test_done_proof_js_integration.py`: replace `skipUnless` with the fail-on-missing-runtime
  check plus the Windows-only platform skip; update the module docstring to state the rule.
- [ ] Verify: `yaml.safe_load` on `ci.yml`, actionlint, local run of the changed test file.
- [ ] After push: confirm AC-2, AC-3 and AC-4 from the shard logs.

## Out of Scope
- Making `run_vitest_and_parse` launch on Windows (resolve `vitest.cmd`, or run `node vitest.mjs`).
  This is a production gap for the done-proof oracle on Windows hosts (it fails closed there), and
  it needs its own ticket. (2026-10-08: filed as
  `TICKET-20261008-DoneProofLaunchesVitestOnWindows.md`.)
- `.github/workflows/test-durations.yml` has the same missing toolchain. There, the vitest-backed
  tests fail fast, so their recorded durations will be near zero, which affects only shard balance.
  It should mirror `test-shard` in a follow-up. (2026-10-08: filed as part (a) of
  `TICKET-20261008-BuildPipelineHygiene.md`.)
- Raising the Node major. Node 20 is kept to match `done-proof`. Moving both jobs (and
  `atlas-contracts`, which uses 22) to one supported LTS is a separate change.

## Risk & Safety
- Touches money? No.
- Touches data? No. CI configuration and one test file's skip policy.
- Reversibility? Fully reversible (revert the two steps and the test-file change).
- Side effect: `leafcutter-web/node_modules/` now exists during the shard run. Repo-walking tests
  already exclude `node_modules` (and local dev checkouts already have it installed), so no
  behaviour change is expected beyond the newly-running JS proof tests.
