---
title: "The test READMEs get the falsifiability rules they were missing, and a probe that can't tell not-installed from couldn't-look gets a known issue"
date: "2026-09-01"
time: "17:57"
type: manual
components: 
  - testing_quality
  - commit_guardian
  - precommit_hooks
summary: "Wrote down, in the two places engineers actually look before touching a test, the specific ways a test in this repository can pass while checking nothing, and filed a known issue for a pre-commit health check that reports a hook as missing when it actually could not tell."
description: "unit_tests/README.md was the single line `# Unit Tests`; it is now a ten-section guide covering the red-baseline-unavailable case for negative controls (mutation proof required instead), the mutation-copy trap where mutating templates/ instead of the deployed scripts/commit_guardian/ makes a dead test report green, fixture realism vs failure capability, asserting over emitted artifacts rather than source text, per-item reporting, and a pre-done checklist. tests/README.md's only runnable instruction was a stale `unittest discover` pointing at a path that does not resolve from the repo root and bypasses both pytest plugins (pytest_ac_enforcement's xfail-masking and --continue-on-collection-errors), so following it ran a weaker suite than CI; it now defers to unit_tests/README.md and covers what is specific to this root: conftest.py blast radius and fixture construction. docs/known-issues/commit-guardian.md gains KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look: verify_precommit_active.py --json reports git_hook: false when run from a directory that is not a git repository, byte-identical to the output of a genuinely unprotected worktree; medium severity because it fails safe, with the remedy (an `unverified` state) already modeled in config/verification_flow.schema.json."
breaking: false
---

## Entry

`unit_tests/README.md` was one line: `# Unit Tests`. It is now a ten-section guide to the
ways a test in this repository can look correct, pass, and constrain nothing — most of them
defects that actually shipped, several inside the machinery built to prevent exactly that.

The spine: a passing test is not evidence until you know it can fail. A **negative control**
asserts an absence, is green on arrival by construction, and has no red baseline to capture —
so `CLAUDE.md`'s rule that a green test-writer phase is a TDD-order violation **inverts** for
this class, and the one mechanism that would have asked "can this fail?" is documented to mean
the opposite. Where no red baseline is possible, the README now says what is owed instead: a
mutation proof, with the injection named.

The operational trap sits underneath that rule, not beside it: **mutate the copy the test
imports.** Commit-guardian modules exist twice — `templates/scripts/commit_guardian/…` (source)
and `scripts/commit_guardian/…` (deployed build output) — and tests load the deployed copy. A
mutation applied to `templates/` lands nowhere the test can see it, and **reports green**,
indistinguishable from the dead test the proof exists to catch. Observed live on `BP-1100g-5-i`:
same injection, `templates/` gives 4 passed, `scripts/` gives 3 failed / 1 passed.

The rest: fixture realism is not failure capability (anti-vacuity assertions catch an empty
fixture, not one that misses the failure mode); assert over emitted artifacts, never source
presence (a grep-only test passes on dead code); report per item, never one aggregate verdict;
a guard is only real if the deployed copy runs and is registered to a hook; and a check that
examined nothing must not look like a check that found nothing.

`tests/README.md` was ten lines whose only runnable instruction was `unittest discover` against
a path that does not resolve from the repo root — and that, even if it had, bypasses both
pytest plugins CI relies on (`pytest_ac_enforcement`'s xfail-masking of not-done ACs, and
`--continue-on-collection-errors`). Following it silently ran a weaker suite than CI does. It
now points at `unit_tests/README.md` for the rules that apply to both roots, and covers what is
specific to this one: the blast radius of a root `conftest.py` shared by every test collected
beneath it, and building `tests/fixtures/` with the project's own writer rather than by hand.

Both README rewrites are transcriptions, not new findings — the knowledge already existed,
scattered across `docs/known-issues/testing-quality.md` and one agent's head, and the two
folders where someone would look before writing a test said nothing, one of them actively
misleading.

`docs/known-issues/commit-guardian.md` gets one new entry:
`KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look`.
`verify_precommit_active.py --json` answers "are pre-commit hooks live in this working tree."
Run from a directory that is not a git repository, its stderr says plainly that the hooks path
could not be resolved and a fallback was used — but the JSON payload reports `"git_hook":
false` and lists it under `failing_checks`, byte-identical to what a genuinely unprotected
worktree produces. The one consumer built to act on the machine-readable answer is the one
consumer that cannot tell "not installed" from "I could not look." It fails in the safe
direction, hence medium, not high. `config/verification_flow.schema.json` already models the
remedy — an `unverified` state, distinct from pass or fail — and the payload uses two states
where the vocabulary has four.
