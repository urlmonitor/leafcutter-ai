---
title: "Test Angles — Failure Catalogue (the evidence base)"
type: reference
status: active
created: 2026-09-21
last_updated: 2026-10-07
components:
- testing_quality
- build_orchestration
related_docs:
- docs/testing/test-angles.md
- docs/testing/README.md
- docs/architecture/components/phantom-done-prevention.md
description: "Per-mechanism catalogue of observed repo incidents — reachability, seam, authenticity, deployment, and negative-control gaps — that justify each core test angle in test-angles.md, plus the concentrated evidence for the `boundary` and `failure` conditional angles. Covers both failure families of the eight-angle taxonomy: wiring-shaped (reachability, seam, authenticity, deployment, negative-control) and discrimination-shaped (incidents 1-4 and 8 from one adopter, plus the `discrimination` angle rule)."
---
> **Parent document:** [test-angles.md](test-angles.md)

# Test Angles — Failure Catalogue (the evidence base)

Grouped by mechanism. Every core angle in [test-angles.md](test-angles.md) is justified by
incidents observed *in this repository*.


## Reachability gap — never invoked from a production entry point

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| BO-2400f-7..10 (`8f0c55c2b` #411 → `9c58f4550` #422) | lifecycle functions had no CLI subcommand and no workflow call | tests imported the functions directly |
| fast lane, 2026-07-22 (CLAUDE.md "Gate / Workflow ACs") | `fast-lane-build.js` never executed its red/green gates; `fast_lane.py` had no CLI, so the runner's `select_batch` call was a silent no-op | grep-only structural tests assert a string is *present* — they pass on dead code |
| BO-1700, EPIC-BOPhantomDoneRemediation T02 (2026-07-15, `50e28cc1`) | `check_hook_freshness()`'s return value silently discarded; `resolve_hooks_path(cwd)` re-resolved internally and ignored | tests called the helpers directly, never via `run_checks()` |
| BO-2300 Interactive Pause/Resume — phantom-built **twice** | dispatch happened; the instruction payload and the on-disk effect did not | tests keyed on dispatch topology — presence, labels, counts of dispatched helpers that a mock controls (`docs/architecture/components/phantom-done-prevention.md`) |
| `finalize-feature.js` (EPIC-FinalizeFeatureHardening F2, 2026-06-24; EPIC-PrecommitSafetyNet KI-3) | legacy `async function run({...})` wrapper with no top-level body — the Workflow tool **never invokes it**; the agent fallback was dead, all 6 finalize steps done by hand | nothing executed the script through the real Workflow tool; a never-called entry function looks fine statically |
| TQ-100 collection isolation, `2a377f91` (2026-07-08) | CI's `-x` aborted at the first failure; the guarantee was inert in real CI | per-ticket tests built their own subprocess calls *without* `-x` — never the production invocation |

## Seam gap — both sides tested, never wired together

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| EPIC-ComputedQualityGates FP-1 layer 1 (2026-07-08, PR #201) | all three real call sites invoked `_build_agents_map(assigned_agent)` with no axes, so the computed path was dead code | tests called the function with the new kwargs; no test ran the generator end-to-end |
| BO-400c-3-i, EPIC-BOPhantomDoneRemediation T04 (2026-07-15) | the sole production call site (in `check_ticket_signoff_parity.py`) still passed one argument | all unit tests called the extended function correctly |
| EPIC-ComputedQualityGates FP-1 layer 3 | hook's `ALLOWED_CHANGE_TARGETS` and `guardrail_gates.yaml` keys were **disjoint** vocabularies | each side was tested against its own copy; no cross-source set-equality contract test existed |
| EPIC-PrecommitSafetyNet FP-1 (2026-06-17, `656b6d6`, PR #89) | tier lookup read a field from a file the re-dispatch path never opened; 4 of 7 `blocking_hook_ids` had no manifest entry, so lookup returned `null` and judgment-tier failures never routed | producer and consumer each green in isolation; the cross-ticket `delivers_to`/`expects_from` contract was never traced, and the consumer mocked the dependency |
| EPIC-AcPipelineDeployGaps inbound gap 4 (2026-06-17) | finalize step 3's output schema did not match step 6a's reader — the whole failure-tracking loop was dead code | writer and reader covered in isolation; no test round-tripped a real artifact between them |

## Authenticity gap — the fixture was not the real artifact

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| EPIC-PhantomDoneFilesTouched KI-1 (2026-07-07, PR #209 / `17c538fe`) | `files_touched` parser was a **complete no-op on every real ticket** — PyYAML emits list items at column 0; the regex required indented dashes | every fixture was hand-typed with indentation, reproducing the exact bias that hid the bug. The *first* remediation spot-check reused indented fixtures and missed it again |
| EPIC-ComputedQualityGates FP-1 layer 2 (2026-07-08) | **no AC in the 1,802-record store carried `change_target`/`risk_surface`** — the computed path returned `None` for every real AC even after the call sites were wired | every test fed hand-built AC dicts that already contained the axes; no test loaded a real on-disk AC |
| GenReviewFixes H-2 (2026-07-21, PR #372 / `439b74007`) | forward-reference `NameError` in `_load_migration_map`'s cold-import fallback — fires only in a genuinely fresh process | tests used `importlib.reload()`, which re-executes in an already-populated namespace, so names that would raise on true first import were already bound |
| GenReviewFixes root `conftest.py` (2026-07-21) | a repo-root `conftest.py` silently hijacked `from conftest import load_fixture` in an unrelated test tree | per-file runs resolve conftest relative to that file and passed; only the full strict suite reproduced real collection order |
| EPIC-ComputedQualityGates FP-7 (2026-07-07) | the `[NO-FEEDBACK-CHECK]` bypass reads `GIT_COMMIT_MSG`, which git only writes *after* the pre-commit stage — the bypass never fires | the tests set the env var themselves, reproducing a state git never produces at pre-commit time |
| EPIC-InFlightVisibility FP-1 / FP-7, `BO-1000b-1-i` (2026-07-23, fix `17735a2ed`) | every skipped step double-recorded in `stepOutcomes[]` | the count-guard regex matched only quoted-string first args and was blind to the template-literal calls it was meant to catch |

## Deployment gap — source tree green, deployed copy broken

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| `done_proof.py`, 2026-07-22 (CLAUDE.md "New Hook / Gate Dependencies") | omitted from `build_ac_store`'s `deploy_map`; the deployed hook raised `ModuleNotFoundError` — would have blocked **every** merge once required | unit tests import from the source tree; caught only when the hook fired on its own commit |
| BP-811, EPIC-AcPipelineDeployGaps Finding #3 (2026-06-17) | the shim wrote workflows to `output_root/workflows/`, not `.claude/workflows/` — the deployed file was unreachable at the invocation path | **the AC asserted the copy tier ("file present in build output"), never the reachability tier ("the command resolves and executes")**. This is the cleanest statement in the corpus of why `deployed` and `reachability` are separate angles |
| EPIC-AcPipelineDeployGaps inbound gap 2 | `plan-feature.js` was absent from `templates/workflows-js/`, so `build.py` never deployed it to any consumer | all tests ran the workflow from the source tree; nothing asserted the build manifest contained it |
| EPIC-FinalizeFeatureHardening F4-2 (2026-06-24) | the committed deployed mirror `scripts/workflows/plan-feature.js` diverged from its template source | the mirror relationship is codified nowhere an agent can check; the only detecting test lives in main's CI |
| EPIC-DocumentationCoverageGuarantee FP-2 (2026-08-10) | missing `requires_verification: true` failed `install_shims`, blocking the pytest gate *before any test ran* | the failure is in the build step, which no unit test exercises |

## Negative-control gap — the guard could not actually block

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| BO-1700, EPIC-BOPhantomDoneRemediation (2026-07-15) | the gate was **fail-open**; had to be flipped to fail-closed | no test fed known-bad input through the gate and asserted a block |
| FIN-100h, `a0bcb8a6c` (#437) | finalize Step 2's final `else` was the *success* path, so an observed `{"status":"refused"}` recorded a clean merge that never happened — directly upstream of merge-to-main | no test fed a refusal or unrecognised status through the branch |
| EPIC-InFlightVisibility FP-5 (2026-07-23) | merging origin/main silently deleted main's H-1/H-2 deploy-parity guards from `finalize-feature.js`; a malformed test run could then merge to main | the guards had no test feeding a failing/contradictory post-merge state, so deleting them broke nothing observable. All 353 tests stayed green |
| TQ-100 L-4 / BP-1200b (2026-07-08) | the CI pytest job is `continue-on-error: true` — the gate fires and merges proceed anyway | the plugin's own tests pass; nothing asserts the verdict is *consumed* by CI |

## Discrimination-shaped failure family

A green test can be useless in two different ways.

- **Wiring-shaped** — the test is right about the unit, but the unit is not connected to
  anything real. Closed by `reachability`, `seam`, `real_artifact` and `deployed`; the
  incident evidence is in the catalogue below and in
  [test-angles-failure-catalogue.md](test-angles-failure-catalogue.md).
- **Discrimination-shaped** — the test reaches the real code, but its fixture and
  assertions cannot tell a correct implementation from a wrong one. It passes on the fix
  and would also pass on the bug. Closed by the `discrimination` angle.

The red baseline does not close the second family: it proves the test fails against one
wrong program (the implementation is absent), and an `ImportError` already satisfies
that. See the
[analysis](../analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md) for
the full argument; this section is the lookup. The wiring-shaped family is the sections above.

### The `discrimination` angle (summary)

| Property | Value |
|---|---|
| Kind | Eighth angle; the third conditional angle (after `boundary` and `failure`) |
| Fires when | The work fixes a bug; **or** adds or changes a condition of a gate or guard; **or** a `test_spec` entry carries `must_catch` |
| Question | Would this test go red under a named plausible wrong version, not only when the code is absent? |
| Slot rule | Never one of the four slots by default. It may share a test with `criterion` — a single test can answer both |
| Rule | The test is red under **at least one named plausible wrong version** of the code (for example "revert the fix", "drop the second gate condition", "new column is NULL"), not only under absence |
| Declared via | `angle: discrimination` and/or `must_catch` on a `test_spec` entry — see [ac-schema.md](../reference/ac-schema.md) |
| Enforced at | The fast lane red-baseline reader refuses an import/name/attribute-error red as evidence for an entry that declares `must_catch` or `discrimination` (`verify_red_baseline` with `--ac-root`, `scripts/build_orchestration/_fl_red_baseline_support.py`) |

### Discrimination-shaped incidents (catalogue)

> **Provenance.** These incidents come from **one adopter's written record** (the
> bybit-trader `CLAUDE.md` § Testing, its test READMEs and maintainer memory). They were
> **not re-verified** against that adopter's git history. The mechanism and cost columns
> restate what its write-ups record; the "would have caught it" column is this page's
> reading against the three questions and checklist items in the analysis (Q1 smallest
> change that keeps the test green but brings the bug back; Q2 what result shows this
> assertion can fail; Q3 does the control row pass for the same reason the negative row
> fails; checklist: exact-count assertions, a control row, new inputs seeded distinct from
> old, a call-count on the collaborator the branch must reach, a sweep of every consumer
> test, capped loops tested under continuous inflow).

| # | Incident | Mechanism | Cost | Would have caught it |
|---|---|---|---|---|
| 1 | ConfigCache DB-outage retry storm (PR #612) | Gate changed from `if refresh_due:` to `if refresh_due and retry_due:`; two of three tests were updated to satisfy both conditions, the third reset only the old variable, so the branch under test ran **0 times** | The branch the ticket existed to fix could be deleted with the suite still green | Q1, Q2; call-count on the collaborator the branch must reach |
| 2 | EPIC-CvdWindowDeltaNormalisation (six occurrences) | Gate input moved from `cvd` to `cvd_delta_30`; fixtures still seeded only `cvd`, so the control row was excluded for the same reason as the negative row; shadow tables omitted the new column; one consumer suite missed; a fix-probe used `buy_volume >= 0`, which drops NULLs and passes best when the pipeline is dead | Correct code turned suites red, and the natural response was to "fix" working code | Q3; a control row; new inputs seeded distinct from old; consumer-test sweep |
| 3 | MacroAvwaps anchor starvation (`b8f47a12f` to PR #605) | `ORDER BY` added to a loop with a per-call cap of 5 and no resume cursor; every test used a fixed population | The same 5 anchors won every call; the rest starved in production for 8 weeks | Q1; capped loops tested under continuous inflow |
| 4 | EPIC-UnblockResurrection/03 | The coverage test for the starvation fix used a pool that emptied under any ordering, so fixed and reverted code both passed | Caught only because `pr-reviewer` re-derived the guarantee by hand | Q1 (run the reverted code); exact-count assertions |
| 8 | Context parity check at "live = 100%" | Measured that values were present, not that they were correct | False confidence in production data | Q2; exact-count / denominator assertions |

**Incidents 5, 6 and 7 belong elsewhere** and are deliberately not catalogued here:
5 (a production-covering integration test later `@unittest.skip`-ped) is **skip
hygiene**; 6 (about 395-468 stale SQL-suite failures from unreconciled column drops) is a
**process** failure — see "What this taxonomy does NOT fix" in [test-angles.md](test-angles.md); 7 (DB tests
hardcoded to a developer's local address) is a question of **where the test database
address comes from** (it belongs in the project's testing configuration, not in a test
template).

## The `boundary` and `failure` conditional angles: real but concentrated evidence

Evidence for `boundary` and `failure` exists, but it comes from **two sources only** —
GenReviewFixes (PR #372) and EPIC-PhantomDoneFilesTouched rounds 1-2. Five other
retrospectives mined contribute none.

- `boundary` — TKT-500f-15: a scalar-string `components` value was iterated
  per-character instead of wrapped in a single-element list (the one-vs-many shape
  boundary). PhantomDone round-1 defects #3-#6: quoted paths, multi-ticket union, flow-list
  YAML (`[a, b]`) vs block list, `lstrip` path mangling. EPIC-BOPhantomDoneRemediation
  T03: `_check_change_target` had an empty-list guard, the identically structured
  `_check_risk_surface` did not, and all 22 tests passed because none exercised
  `risk_surface: []`.
- `failure` — PhantomDone round-1 #2: an `OSError` path did not honour the hook's
  fail-open contract. Round 2 then inverted it: a wrong-shape `commit_guardian.json`
  raised an uncaught exception and **blocked commits**. TKT-500f-18-i and ACD-1200a-14-i:
  malformed/unavailable mapping source and `git rev-parse` fallback both had to be made to
  degrade without raising.

**Two honest caveats.** Nearly every one of these was found by post-merge adversarial
review, not by a boundary test someone had identified in advance — the AC simply never
specified the edge case, so the fix is AC-authoring coverage at least as much as a test
angle. And both angles were caught by `pr-reviewer`, which already exists. That is why
they are **conditional and trigger-fired**: never mandatory, and never worth one of the
four angle slots by default.
