---
title: "Jev can pick which tests to attack, but it cannot tell whether a test is solid"
description: "Evaluation of TypeSafe's Jev model as a cheap triage layer for vacuous tests, on 13 real tests recovered from bybit-trader's history, against a blind Claude Haiku baseline. One question separates vacuous from fixed tests almost perfectly; the pre-registered verdict rule does not; both models fail on state carried across calls."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - testing_quality
---

# Jev can pick which tests to attack, but it cannot tell whether a test is solid

[The earlier analysis](2026-09-25-test-writers-prove-failure-not-discrimination.md) found that no
test agent in this package checks whether a test can tell a correct implementation from a wrong
one. It proposed a mutation phase, and asked whether a cheap classifier could decide which tests
to attack first. This page answers that question for **Jev** (TypeSafe's System One model,
`jev-1.13.0`). Jev takes a state plus typed questions and returns calibrated yes/no, choice or
score answers. It charges $42 per billion input tokens and output is free.

**Verdict: it's a useful triage layer, not a judge.** One question, "does this test set up the
failure the ticket describes?", separated vacuous tests from their fixed versions almost
perfectly. It beat a blind Claude Haiku baseline on that question and on three others, at roughly
1/30 of the cost and about 100× the speed. The verdict rule written before the data was weak
(3 of 5 vacuous tests flagged). Neither model can follow state that an earlier call leaves
behind, so the final verdict still has to come from a mutation run.

## What was measured

**The set:** 13 real tests from bybit-trader, recovered from git with `git show` and never
edited. The labels come from commit messages, ticket comments and the adopter's `CLAUDE.md`,
never from anyone's opinion.

| Incident | Vacuous | Fixed | Mechanism |
|---|---|---|---|
| MacroAvwaps anchor starvation (8 weeks in prod) | 2 | 2 | per-call cap plus `ORDER BY`; the tests used one anchor under a cap of 100 |
| ConfigCache DB-outage retry storm | 1 | 1 | the gate gained `and retry_due`; the test reset only `_last_refresh`, so the branch ran 0 times |
| UnblockResurrection/03 | 1 | 1 | the coverage test used a pool that drains under any ordering |
| Phase-2 router wrongly skipped | 1 | 1 | `@unittest.skip` on a live procedure's test |
| CVD window-delta epic | 0 | 3 | the vacuous versions were squash-merged away, so only the fixed tests survive |

**The pipeline** (prototype in `debugging/test_judge/`):
- One request per test function, holding the test body, the fixtures and helpers it reaches, a
  narrowed excerpt of the code under test, the gate conditions and the ticket intent.
- Comments and docstrings are stripped from the test, because three fixed tests describe their
  own fix ("…can silently go vacuous again…").
- Jev: 5 repeats per case. Claude Haiku: 2 runs as a sub-agent on anonymised, shuffled request
  files. A first Haiku attempt was thrown away because the filenames carried the labels.
- Checks that code can decide exactly (skips, missing or one-sided assertions, assertions only in
  loops) run in code and are never sent to either model.

**The measures.** Per question: AUC over all vacuous/fixed combinations (0.5 = no signal,
1.0 = perfect), and "pairs won", meaning the vacuous version scores clearly higher than its own
fixed version within one incident. Differences under 0.05 count as ties.

## Results

| Question | Jev AUC | Jev pairs | Haiku AUC | Haiku pairs |
|---|---|---|---|---|
| **Does the test exercise the ticket's failure scenario?** | **0.97** | **6/7** | 0.74 | 4/7 |
| Weakness score ("would a small wrong change still pass?") | 0.74 | 6/7 | 0.57 | 4/7 |
| Is the population static while the code caps batches? | 0.76 | 4/7 | 0.59 | 4/7 |
| Is the gate reached at the asserted call? | 0.73 | 5/7 | 0.60 | 4/7 |
| Is there a control case? | 0.55 | 3/7 | 0.72 | 4/7 |
| Mock questions, test kind | about 0.5 | | about 0.5 | |
| Static checks (code) | 0.54 | 1/7 | same | |

The set contains no mock-based cases, so the mock questions had nothing to detect.

Jev's answers were stable: the spread across 5 repeats was at most 0.10.

| | Jev (13 cases × 5 repeats) | Haiku (13 cases, one pass) |
|---|---|---|
| Wall time | 3.5 s | 85–108 s (as a sub-agent) |
| Cost | $0.0175 (about $0.0035 per pass) | about $0.10–0.15 per pass at API list price (estimate from about 83k input tokens) |

**Per incident:**
- **MacroAvwaps:** a clean catch. On the ticket-scenario question the vacuous tests scored 0.95
  and 0.94, the fixed tests 0.08 and 0.09. The static-population question named the exact
  mechanism: 0.93 and 0.94 against 0.27.
- **ConfigCache:** a weak hint only (0.29 vs 0.07 on the ticket question). The gate question
  missed it again (0.18 vs 0.15). This matches TypeSafe's documented weak spot, "indirection".
- **Resurrection:** a partial signal (0.45 vs 0.12). Haiku saw nothing.
- **Phase-2 skip:** caught only by the static skip check.

**Verdict rules** (flags counted as `SUSPECT` or `ATTACK FIRST`):

| Rule | Jev | Haiku |
|---|---|---|
| v1, written before any real data | 3/5 vacuous, 1/8 false alarms | 3/5, 2/8 |
| v2, revised on this data: static finding, OR ticket-scenario ≥ 0.40, OR any gate ≥ 0.70 | 4/5, 0/8 | 3/5, 1/8 |

v2 was fitted to these 13 cases, so its score here is not evidence. It is pre-registered, together
with success criteria, for the out-of-sample run in `debugging/test_judge/REPLICATE.md`.

## What this means

1. **The valuable question is about intent, not mechanics.** "Does the test set up the failure
   the ticket describes?" needs the ticket, and it catches the most expensive failure in the set: a
   green test that is about something else. The mechanical questions (gate reached, control case)
   are weaker. Where they matter, something deterministic answers them better: a branch-coverage
   run for "reached", and a mutation run for "discriminates".
2. **Jev beats a small LLM on this task.** It was better on 4 of the 5 questions that carried any
   signal, far cheaper, fast enough for every commit, and stable across repeats. The price-to-signal
   argument holds.
3. **It is not a judge.** Both models missed the ConfigCache case. That test has exact
   assertions, reaches the real code and names the right scenario; only its fixture's timing is
   wrong. That class of defect is visible to execution, not to reading.

## What we must do

> **Update (2026-09-25):** the leafcutter replication has run. See
> [2026-09-25-jev-test-triage-leafcutter-replication.md](2026-09-25-jev-test-triage-leafcutter-replication.md).
> The ticket-scenario question held up (AUC 0.84, still ahead of Haiku). The v2 verdict rule did
> not (43 % false alarms), and neither did the wiring questions.

1. **Replicate on leafcutter's own history before building anything,** following
   `debugging/test_judge/REPLICATE.md`. Leafcutter's incidents are mostly wiring-shaped
   (reachability, seam, authenticity), so this tests whether the result transfers. Two wiring
   questions are pre-registered behind `--wiring`.
2. If it replicates, **wire the three layers into the planned mutation phase:** code checks, then
   Jev's ticket-scenario question on every changed test, then mutation runs only on flagged tests.
   Jev chooses where to spend the expensive runs; it never signs anything off.
3. **Drop `has_control_case` and use branch coverage for "gate reached".** Both were weak model
   questions with exact alternatives.
4. **Keep test comments out of the state.** Fixed tests narrate their own fix, which flatters any
   reader, model or human.

## Limits

- 13 cases from one adopter, 4 incidents with both versions, 5 vacuous tests in total. One
  changed answer moves an AUC visibly.
- Two labels rest on weaker evidence. `avwap_good_2` is "discriminating" per its own docstring
  only. `resurrect_bad` was vacuous against an intermediate procedure that was never committed;
  the procedure in its case is the final version.
- The two MacroAvwaps vacuous tests are vacuous only relative to the starvation bug. They check
  what they claim to check (equivalence, dedup).
- Haiku ran as a sub-agent, not through the API at temperature 0. Its cost is an estimate from
  token counts.
- The case files contain bybit-trader code and are not in this repository. `make_case.py`
  rebuilds any case byte-for-byte from the commit and path recorded in its `meta.json`.
