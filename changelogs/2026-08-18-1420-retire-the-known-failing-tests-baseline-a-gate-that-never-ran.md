---
title: "chore(commit-guardian): retire the known-failing-tests baseline, a gate that never ran"
date: "2026-08-18"
time: "14:20"
type: manual
components:
  - build_pipeline
  - commit_guardian
summary: "A complete pytest-with-baseline pre-commit gate — 16 passing tests, a how-to guide, an agent-template procedure, deployed by build.py — was registered in no hook config and its baseline file never existed. It has never run. Deleted rather than wired, because TQ-100d-1 already specifies the replacement with the expiry and staleness semantics it lacks."
description: "templates/scripts/commit_guardian/known_failing_tests.py implemented a pytest-with-baseline gate: run the suite, load a baseline of already-failing test ids, block only on the difference. Every quality signal around it was green — 16 passing unit tests in tests/test_known_failing_tests.py, docs/how-to/known-failing-tests-baseline.md indexed in docs/INDEX.md, a 'When Tests Fail at Pre-Commit' procedure in templates/agents/commit.md, and deployment by build.py into .leafcutter/scripts/commit_guardian/. It was connected to nothing: grep -rn 'run-tests-with-baseline' across every .json and .yaml in the repository returns no results, so it appeared in no commit_guardian.json and pre-commit never invoked it, and find -name known_failing_tests.json returns nothing, so the baseline it diffs against has never existed. The tests passed because they tested the functions; nothing tested that the hook runs. Two guards held contradictory beliefs about the same file: unit_tests/test_build_guard_real_package.py asserted it MUST be present in templates/, while scripts/build_propagation_audit.py allowlisted it with the comment 'The script does not yet exist as a package deliverable'. The propagation audit had also independently diagnosed the operational risk — 'commit.md has no documented fallback when the script is absent and explicitly forbids --no-verify as an escape path'. Deleted rather than registered, for two reasons. TQ-100d-1 (readiness approved, priority high) specifies the replacement capability with expiry dates, ticket references and stale-entry detection that this script lacks entirely, and its settled design puts the allowlist at config/known_failing_tests.yaml read by a new module under scripts/ — so wiring the old one would ship a weaker competitor to an approved criterion and collide with its replacement's name. And its collect_failing_tests() returns an empty set when pytest fails to launch (OSError), which the caller reads as 'no failures', so a wired version would pass a suite it never ran. Removed: the module, its 16 tests, the how-to, and the commit.md procedure. Repaired: the build guard's required_scripts list (transform_decision_history.py and check_test_fixture_bloat.py remain asserted and were not weakened) and the propagation-audit allowlist. commit.md's section was replaced rather than deleted, because the question it answers is real: the new text states that no baseline mechanism exists, that --no-verify remains forbidden, what to do instead, and names TQ-100d-1 as the pending replacement. Deliberately left alone: config/commit_message_patterns.json, scripts/commit_classifier.py and unit_tests/test_mixed_set_detection.py reference known_failing_tests.json as a commit-message path-classification rule — a rule for how to classify a path if it appears, not a claim that it exists — so removing them would edit a passing test for no behavioural gain."
pr: null
commits: []
---

## Entry

A pre-commit gate that has never run has been removed.

`known_failing_tests.py` did something sensible on paper. When a suite has
pre-existing failures, a naive "block on any failure" hook blocks everybody, so
people reach for `--no-verify` — which switches off *all* hooks, not just the
test one. A baseline of already-failing tests, with the gate blocking only on
the difference, is the standard answer.

Every signal around it was green:

- the module, written and documented
- **16 unit tests, all passing**
- a how-to guide, indexed in `docs/INDEX.md`
- a procedure in the commit agent's template
- deployed by `build.py` into the live tree

And it was connected to nothing. `grep -rn "run-tests-with-baseline"` across
every `.json` and `.yaml` in the repository returns nothing, so it was in no
`commit_guardian.json` and pre-commit never called it. `find -name
known_failing_tests.json` returns nothing, so the baseline it diffs against was
never created.

The tests passed because they tested the functions. Nothing tested that the
hook runs.

### Two guards, opposite beliefs

`unit_tests/test_build_guard_real_package.py` asserted the script **must** be
present in `templates/`. `scripts/build_propagation_audit.py` allowlisted it
with the comment *"The script does not yet exist as a package deliverable."*
Same file, same repository, contradictory claims, both green.

The propagation audit had also already worked out the operational risk, in a
comment nobody acted on: *"commit.md has no documented fallback when the script
is absent and explicitly forbids `--no-verify` as an escape path — so absence
causes a hard failure."*

### Why deleted rather than wired

Registering it looked like the cheap fix. Two reasons not to.

`TQ-100d-1` is approved and high priority: *"A failing test on a valid,
unexpired allowlist entry does not block the run."* Its siblings specify expiry
enforcement, ticket references, and flagging entries whose test has started
passing. This script has none of that — its baseline is a flat list of node ids
with a "when regenerated" date stamp. Nothing expires; nothing links to a
ticket. A baseline with no expiry is a permanent amnesty list, and permanent
amnesty lists grow. `TQ-100d-1`'s settled design also puts the allowlist at
`config/known_failing_tests.yaml` read by a *new* module under `scripts/` — so
wiring the old one would collide with its own replacement.

Second, `collect_failing_tests()` catches `OSError` from launching pytest and
returns an **empty set**, which the caller reads as "no failures". A wired
version would pass a suite it never ran.

### What changed

Removed: the module, its 16 tests, the how-to, and the `commit.md` procedure.
Repaired: the build guard's `required_scripts` list and the propagation-audit
allowlist. `transform_decision_history.py` and `check_test_fixture_bloat.py`
remain asserted — that guard was not weakened.

`commit.md`'s section was **replaced, not deleted**. The question it answers is
real and a commit agent will hit it. The new text says plainly that no baseline
mechanism exists, that `--no-verify` is still forbidden, what to do instead
(establish whether the failure is yours; if it isn't, surface it as a blocker
rather than bypassing the gate), and names `TQ-100d-1` as the pending answer.

Left alone deliberately: `config/commit_message_patterns.json`,
`scripts/commit_classifier.py` and `unit_tests/test_mixed_set_detection.py`
match `known_failing_tests.json` as a commit-message path-classification rule.
That is a rule for how to classify a path *if it appears*, not a claim that it
exists. Removing it would edit a passing test for no behavioural gain.

### Verified

Full suite over `tests/` and `unit_tests/` under `AC_ENFORCE_STRICT=1`:
**4383 passed, 8 skipped, 2 xfailed, 0 failed, 0 collection errors.** `ruff`
clean. The build guard and propagation guard both pass with the entries removed
— checked empirically, not assumed.

### Found on the way out

`build.py` does not delete a deployed artifact when its template source is
removed. After deleting the template, the build dropped the entry from
`.build_manifest.json` and reported "no stale files found", while
`.leafcutter/scripts/commit_guardian/known_failing_tests.py` remained on disk.
`.leafcutter/` is gitignored so nothing here is affected, but any install that
ever received this script still has an orphaned copy of it. That is the same
shape as the defect being removed — a deployed thing nothing references — and
it is not fixed here. Recorded for a follow-up; it is the inverse of `BP-900g-9`
(a declared deploy entry whose source is missing fails the build), and nothing
currently covers this direction.
