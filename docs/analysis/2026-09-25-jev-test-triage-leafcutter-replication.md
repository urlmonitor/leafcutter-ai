---
title: "On leafcutter's own history, Jev ranks tests well but its verdict rule does not replicate"
description: "Out-of-sample replication of the Jev test-triage evaluation on 38 real tests recovered from leafcutter's git history (17 vacuous, 21 discriminating, 22 incidents). The ticket-scenario question still separates vacuous from fixed tests (AUC 0.84, beating a blind Haiku baseline at 0.77), but the pre-registered verdict rule raises 43 % false alarms, and both pre-registered wiring questions fail on the reachability, seam and authenticity incidents that dominate leafcutter."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - testing_quality
---

# On leafcutter's own history, Jev ranks tests well but its verdict rule does not replicate

This page is the out-of-sample run that
[the bybit-trader evaluation](2026-09-25-jev-test-triage-evaluation.md) asked for. It followed
[`debugging/test_judge/REPLICATE.md`](../../debugging/test_judge/REPLICATE.md). The success
criteria, the verdict rule `v2` and the two wiring questions were all fixed before any leafcutter
case existed. None of them were changed after the results came in.

## Verdict

**The benefit does not replicate as a verdict. It does replicate as a ranking.**

| Criterion from REPLICATE.md §0 | Result | |
|---|---|---|
| 1. `exercises_ticket_scenario` AUC ≥ 0.75 (Jev, comments stripped) | **0.84** | **met** |
| 2. Verdict `v2` flags ≥ 60 % of vacuous tests **and** ≤ 20 % false alarms | 17/17 flagged (100 %), but **9/21 false alarms (43 %)** | **not met** |
| 3. Jev's AUC ≥ Haiku's AUC − 0.05 | 0.84 vs 0.77 | **met** |
| B. A wiring question reaches AUC ≥ 0.75 on wiring-shaped incidents | `reaches_entry_point` **0.58**, `fixture_is_real_artifact` **0.70** | **not met** |

Criterion 2 fails, so under the pre-registered rules the benefit **does not replicate**.

What still holds:
- One question, "does this test set up the failure the ticket describes?", separates vacuous tests
  from their fixed versions on a second, unrelated codebase.
- Jev answers it better than a blind Claude Haiku baseline, at roughly 1/80 of the cost.

What does not hold:
- Turning that score into a flag with the v2 thresholds produces too many false alarms.
- The question is weakest on exactly the failure shape leafcutter suffers from most: code that
  is tested directly but never wired into a production entry point.

## The set

38 test functions recovered verbatim from git with `make_case.py`, across 22 incidents. Every
label is backed by a commit message, ticket comment, retrospective or known-issue entry.

| Shape (from the [test-angles failure catalogue](../testing/test-angles.md)) | Incidents | Vacuous | Fixed |
|---|---|---|---|
| **Reachability**: code never reached from a production entry point | BO-2400f-7..10 (claim, release), BO-1700 T02 (freshness, hooksPath), TQ-100 collection isolation | 5 | 5 |
| **Seam**: both sides tested, never wired together | BO-400c-3-i, ComputedQualityGates FP-1 layers 1 and 3 | 1 | 3 |
| **Authenticity**: the fixture was not the real artifact | PhantomDoneFilesTouched KI-1, ComputedQualityGates FP-1 layer 2 and FP-7, GenReviewFixes H-2, BO-1000b-1-i | 5 | 2 |
| **Other** (boundary, failure, negative control, inverted tests) | TKT-500f-15, ACD-1200a-14, BO-610 null and absent (inverted), BP-1200b, TKT-600a-1, TKT-500f-18-i, ACD-1200a-14-i, BO-610-3-i, FIN-100h, BO-1700e-3 | 6 | 11 |
| **Total** | 22 | **17** | **21** |

The pairs come in four kinds:
- **14 complete pairs** across 12 incidents. Both versions exist; 18 vacuous/fixed combinations
  counting the 2×2 incidents.
- **3 vacuous-only cases.** No fixed test was ever written: FP-7 and BO-1000b-1-i are still
  vacuous at HEAD, and H-2 has no fresh-process test.
- **7 fixed-only cases.**
- **One test used twice.** `TestEndToEndGeneratorComputedMap` at `8aeb37d4` is labelled
  discriminating for FP-1 layer 1 (it drives the real generator) and vacuous for layer 2 (it
  feeds a hand-built AC). Each label has its own evidence. The two cases differ only in their
  ticket intent, which makes them a direct test of whether the ticket-scenario question uses the
  intent at all.

## Results

**Jev** (`jev-latest`, 5 repeats per case) against **Claude Haiku** (2 blind runs on shuffled,
anonymised `req_NN` files). Comments and docstrings were stripped for both.

| Question | Jev AUC | Jev pairs won | Haiku AUC | Haiku pairs won |
|---|---|---|---|---|
| **exercises_ticket_scenario** | **0.84** | **14/18** | 0.77 | 8/18 |
| gate reached (any gate) | 0.70 | 11/18 | 0.73 | 8/18 |
| weakness (score) | 0.55 | 6/18 | 0.59 | 9/18 |
| test_kind | 0.57 | 2/18 | 0.59 | 3/18 |
| has_control_case | 0.43 | 0/18 | 0.34 | 3/18 |
| fixture_is_static_population | 0.46 | 0/18 | 0.48 | 0/18 |
| mock questions, time_dependent | 0.44–0.51 | | 0.46–0.53 | |
| static checks (code) | 0.41 | 1/18 | same | |

Two cross-checks:
- **Raw (comments not stripped):** Jev's ticket-scenario AUC was 0.83, so leaking comments made no
  difference here. On bybit-trader it had mattered.
- **With `--wiring`:** the ticket-scenario AUC was unchanged (0.84).

**Verdict rules:** a test counts as flagged when the rule returns `SUSPECT` or `ATTACK FIRST`.

| Rule | Jev | Haiku |
|---|---|---|
| v1, written before any data | 14/17 vacuous, 13/21 false alarms | 12/17, 12/21 |
| **v2, pre-registered**: hard static finding, OR ticket-scenario ≥ 0.40, OR any gate ≥ 0.70 | **17/17, 9/21** | 9/17, 4/21 |

Jev's 9 false alarms have two sources, and neither is the static checks:
- **5 from the ticket-scenario threshold:** `bo2400f_release_good` 0.77, `tq100_isolation_good`
  0.63, `phantomdone_ki1_good` 0.61, `bp1200b_good` 0.55, `computedgates_fp1_layer2_good` 0.45.
- **4 from the gate threshold:** `tkt600a1_good`, `bo1700_hookspath_good`, `fin100h_good`,
  `acd1200a14_good`.

Haiku's lower false-alarm count is not a better result. Its probabilities are compressed toward 0
(mean ticket-scenario weakness of 0.23 on vacuous tests, against 0.59 for Jev), so it clears the
0.40 threshold only 9 times.

**Experiment B.** These are the wiring questions scored only on the wiring-shaped incidents: 11
vacuous and 10 discriminating tests.

| Question | Wiring (all) | Reachability | Seam | Authenticity | Other |
|---|---|---|---|---|---|
| reaches_entry_point | **0.58** | 0.64 | 0.67 | 0.40 | 0.46 |
| fixture_is_real_artifact | **0.70** | 0.56 | 0.83 | 0.85 | 0.49 |
| *exercises_ticket_scenario, for comparison* | *0.69* | *0.62* | *1.00* | *0.65* | *0.96* |

The seam and authenticity subsets have only 1–5 cases on one side, so those columns are
indicative only.

**Cost and time**

| | Jev (38 cases × 5 repeats) | Haiku (38 cases, one pass) |
|---|---|---|
| Wall time | 7.3 s for 190 requests | 60–110 s per 10-file batch agent (4 in parallel) |
| Cost | $0.027 total, about **$0.0054 per pass** (130k input tokens) | about $0.40–0.50 per pass (about 390k tokens including agent overhead) |

## Per incident, on the ticket-scenario question

Values are Jev's mean weakness value; higher means "does not set up the ticket's failure".

- **Clean catches:**
  - the inverted tests: BO-610 null 0.86 vs 0.03, absent 0.93 vs 0.03;
  - ACD-1200a-14: 0.82 vs 0.18;
  - TKT-500f-15: 0.55 vs 0.04;
  - BP-1200b: 0.87 vs 0.55;
  - BO-1700 hooksPath: 0.85 vs 0.09;
  - BO-2400f claim: 0.84 vs 0.38;
  - GenReviewFixes H-2, a vacuous-only case: 0.87.
- **Intent sensitivity confirmed:** the same `TestEndToEndGeneratorComputedMap` scored 0.15
  under the layer-1 intent (discriminating) and 0.44 under the layer-2 intent (vacuous).
- **Misses, all reachability-shaped:**
  - **BO-2400f release** is inverted: the vacuous test scored 0.12 and the fixed CLI test 0.77.
  - **TQ-100 isolation** is inverted: 0.28 vs 0.63.
  - **BO-1700 freshness** is only a weak win: 0.21 vs 0.05.

  In each of these, the vacuous test calls the right function with the right input and asserts
  the right outcome. What it misses is that production never calls that function. Reading the
  test alone cannot show that; the evidence sits in `main()`, the CI YAML or the workflow.
- **PhantomDone KI-1:** 0.87 vs 0.61. It counts as a win, but the fixed test still scored high
  enough to be a false alarm.

## What changed relative to bybit-trader, and why

| | bybit-trader (in-sample for v2) | leafcutter (out-of-sample) |
|---|---|---|
| ticket-scenario AUC, Jev / Haiku | 0.97 / 0.74 | 0.84 / 0.77 |
| v2 false alarms | 0/8 | 9/21 |
| effect of stripping comments | large | none (0.83 → 0.84) |

1. **The failure shape changed.** Bybit-trader's vacuous tests used the wrong data, for example
   one anchor under a cap of 100. That is visible in the test body. Leafcutter's vacuous tests are
   mostly well-formed tests of code that nothing calls. Deciding that needs the call graph, not
   the test.
2. **v2's thresholds were fitted to 13 cases and overfit.** Both the ticket-scenario threshold of
   0.40 and the gate threshold of 0.70 produced false alarms on fixed leafcutter tests. This is
   what pre-registration was meant to reveal.
3. **The ranking signal survived the change of codebase.** A drop from 0.97 to 0.84 on a
   different domain, with more than twice the cases, is a real result.

## What we must do

1. **Do not wire Jev into leafcutter as a gate or verdict.** The pre-registered rule failed, and
   retuning it on this data is not allowed. At most, it can be an **optional, advisory ranker**:
   it orders changed tests by the ticket-scenario score so the planned mutation phase attacks the
   likely-vacuous ones first. It must never block or sign anything off.
2. **Answer reachability deterministically, not with a model.** Neither Jev, Haiku nor the wiring
   questions can see that a function has no production caller. A static check that the function a
   test targets is reachable from a registered entry point (a CLI subcommand, a workflow step, a
   hook) addresses leafcutter's dominant failure directly. It needs a ticket through
   `/plan-feature`.
3. **Drop the gate component from the verdict, and drop `has_control_case` and the wiring
   questions.** Here the gate threshold caused 4 of the 9 false alarms, and the gate question sat
   at AUC 0.70–0.73 for both models. Jev's `has_control_case` never carried signal (0.55 on
   bybit-trader, 0.43 here). The wiring questions failed their pre-registered test. If a `v3` rule is wanted, write it down now and judge it only on a
   third dataset, not on the 51 cases seen so far.
4. **Fix the Haiku-baseline procedure in REPLICATE.md.** See "Protocol deviations" below. It may
   also affect the bybit-trader Haiku numbers.

## Development pass: letting Jev abstain, and giving it the callers

This pass was run **after** the results above, on the same 38 cases, so it is in-sample and only
shows direction. Every run used Jev with 5 repeats and stripped comments. Two changes are behind
flags in `debugging/test_judge/`:
- `--abstain` turns the noul questions into `choice` questions. The options are `yes`, `no`,
  `need_production_callers`, `need_fixture_source` and `need_more_code`. The yes/no criteria are
  copied word for word. The weak value is P(`no`), and the combined P(`need_*`) is scored
  separately.
- `--callers` adds `production_callers` to the state. For each function the test calls directly,
  it lists the real call sites at the case's commit, found with `git grep` and then confirmed as
  AST `Call` nodes. Tests, docs and tickets are excluded.

| Variant | ticket-scenario AUC | same, yes-vs-no only | AUC of the need_* mass | v2 flags / false alarms |
|---|---|---|---|---|
| baseline (noul) | 0.84 | – | – | 17/17, 9/21 |
| `--abstain` | 0.84 | 0.86 | 0.59 | 11/17, 8/21 |
| `--callers` | 0.83 | – | – | 17/17, 10/21 |
| `--abstain --callers` | 0.83 | 0.85 | 0.48 | 12/17, 8/21 |

What this shows:
1. **Abstaining did not improve the ranking.** It did produce meaningful abstentions:
   - On gates, Jev abstained most on tests that run the code in a subprocess, such as
     `bo2400f_claim_good` at 0.90 and `bo2400f_release_good` at 0.78. The gate cannot be traced
     from the test there.
   - It also abstained where the code excerpt is JavaScript (`inflight_bo1000b1i_bad`, 0.90).

   Abstaining is not the same as being vacuous, so an AUC of 0.5 on the need_* mass is expected.
   The value lies in routing: an abstention says which context to fetch, or that a deterministic
   check is needed.
2. **Caller context changed nothing on the model side.** `bo2400f_release_bad` still scored
   0.14, even though its state said "no call sites outside tests". The question asks whether the
   test sets up the ticket's scenario, and the vacuous test does set it up. That production never
   reaches the function is a different question, and the wording never asks it.
3. **The caller context works as a deterministic check.** "A function the test calls directly
   has no production call site" is true for 4 of the 17 vacuous tests and 0 of the 21 fixed ones:
   claim, release, freshness and hooksPath. Those include all three reachability misses
   described above. It is the reachability check proposed in "What we must do", point 2, and
   needs no model.

Two slips to note:
- `has_control_case` was converted to a choice as well, because it shares the inverted polarity.
  v2 ignores it, so the verdict numbers are unaffected.
- The caller finder needed one fix before any run: log strings and docstrings had been counted as
  callers. This was a correctness fix made before the cases were scored, not tuning to labels.

## Protocol deviations

- **The Haiku baseline was run twice.** In the first attempt, one single-agent run over all 38
  files wrote a keyword-heuristic script instead of judging. For example, it scored the
  ticket-scenario question by searching for strings like `core.hooksPath`. The second run used
  too few tokens to have read all 38 files. Both runs were discarded unscored.
- **What the valid baseline did instead:** 4 batches of 9–10 files per run, and a prompt line
  forbidding code that generates answers. One batch wrote gate answers under the wrong request
  IDs and was re-run with an added instruction to copy each file's own question IDs.
- **Nothing that affects scoring changed.** The questions, the blind export, the answer format and
  the scoring are exactly as in the runbook. Each case has exactly 2 Haiku answers.
- **One leak-check hit was accepted.** It is a fixture filename `test_good_{idx}.py` inside
  `tq100_isolation_bad`'s own test body. It is part of the verbatim test and carries no label.

## Limits

- **Most vacuous halves come from squash commits.** PRs #201, #209, #281 and #372 were
  squash-merged, and their pre-fix commits no longer exist in any ref or the reflog. Several
  vacuous tests were therefore taken from the fix commit, where they sit next to already-fixed
  code: BO-400c-3-i, PhantomDone KI-1 and FP-1 layer 2. They are vacuous relative to the bug, not
  to the code shown.
- **Four labels rest on weaker evidence:**
  - `tkt500f15_bad` and `acd1200a14_bad`: batch-level retrospective evidence ("none of the
    defects had been caught by the per-ticket TDD cycle").
  - `bp1200b_bad`: indirect evidence ("the plugin's own tests pass").
  - `phantomdone_ki1_bad`: a surviving indented-fixture test that stands in for the rewritten
    originals.
- **Some cases were not recoverable at all:**
  - BO-1700's intermediate "return value discarded" state;
  - the vacuous halves of FP-1 layers 1 and 3 and of BO-610-3-i's empty-list guard;
  - EPIC-PrecommitSafetyNet FP-1 and AcPipelineDeployGaps gap 4, which have no Python tests;
  - FIN-100h's vacuous half: no test targeted the branch before the fix.
- **Three cases send JavaScript or YAML as the code under test,** while the test is Python:
  `finalize-feature.js`, `ci.yml`.
- **The subsets are small.** The experiment-B subsets have 1–5 cases per side, and one changed
  answer moves an AUC visibly.
- **Haiku ran as batched sub-agents,** not through the API at temperature 0. Its cost is an
  estimate.
- **The case files are not in the repo.** They live in the session scratchpad. Each `meta.json`
  records the commit, paths and evidence, so `make_case.py` can rebuild any of them.
