# test_judge: Jev triage prototype

Prototype for [docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md](../../docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md).
It chooses which attacks to run on a test first. **It does not decide whether a test is solid**:
only a mutation run can do that.

## What it does

1. **Pick.** Tests come from `--test`, a ticket's `files_touched` (`--ticket`) or a git diff
   (`--changed-since`). The code under test comes from the test's imports and any `.sql` paths it
   references, or from `--code`. With a diff, conditions on added lines become "gates".
2. **Static checks, in code** (`collect.static_flags`), never sent to the model:
   - skipped tests;
   - no assertions, or an always-true assertion;
   - only one-sided assertions (nothing pins an exact value or count);
   - assertions only inside loops that may run zero times;
   - a hardcoded localhost DB, or `.commit()` calls.
3. **Jev questions** (`questions.py`). One request per test function, sent `--runs` times in
   parallel with a fresh `uid` each time. The state is the test, its fixtures and a narrowed
   excerpt of the code it covers. The questions:
   - mock replaces the unit;
   - asserts only on mocks;
   - control case present;
   - capped batch with a static population;
   - time-dependent;
   - test kind;
   - a weakness score;
   - one "is this gate reached" question per gate.
4. **Aggregate.** Mean and spread per question across runs. The verdict is one of `SUSPECT
   (static)`, `ATTACK FIRST`, `UNCERTAIN -> escalate` or `no flags (still unproven)`, with the
   attacks to run in order.

## Usage

```bash
python judge.py --samples --runs 3 --env-file <path>/.env          # bundled labelled pairs
python judge.py --repo <repo> --test unit_tests/x/test_y.py --dry-run --show-request
python judge.py --repo <repo> --ticket tickets/.../T.md --runs 3
python judge.py --repo <repo> --changed-since origin/main --runs 3 --parallel 8 --out report.json
```

Files:
- `judge.py`: triage CLI and verdict rules (`v1` written before any data; `v2`, the default, fitted
  on bybit-trader).
- `collect.py`: picking, extraction and static checks.
- `questions.py`: the question catalogue, including the pre-registered `WIRING_QUESTIONS`.
- `eval.py`: runs the labelled-set evaluation, blind export and answer import, and scoring.
- `make_case.py`: builds one labelled case verbatim from git.
- [REPLICATE.md](REPLICATE.md): the step-by-step runbook for repeating the evaluation on
  leafcutter's own history.

The API key comes from `JEV_API_KEY` or `TYPESAFE_API_KEY`, read from the environment or from
`--env-file` (default `./.env`). `--dry-run` sends nothing and prints the request sizes. Use it
before pointing this at code you have not decided to send to TypeSafe.

## First results (2026-09-25, jev-1.13.0, samples, 3 runs)

Performance: 12 requests in 1.5 s for $0.00067. The spread across repeats was 0.10 or less on
every question.

| Sample | Truth | Gate question (weak = branch not reached) | Verdict |
|---|---|---|---|
| `test_freshness_bad` | vacuous: every row is NULL, so the branch never runs | 0.89 ✔ | ATTACK FIRST ✔ |
| `test_freshness_good` | control row + NULL row, exact assert | 0.03 ✔ | no flags ✔ |
| `test_config_cache_bad` | vacuous: an earlier `get()` set `_last_attempt`, so `retry_due` is False | 0.14 ✘ | ATTACK FIRST (from the static one-sided-assert flag and the weakness score, not the gate) |
| `test_config_cache_good` | both timers reset, `assert_called_once` | 0.08 ✔ | UNCERTAIN (`has_control_case` misfires on a test that is not a filter) |

Findings so far:

- **Jev missed the key ConfigCache case.** Seeing that state left by an earlier call keeps a gate
  false takes several reasoning steps, which TypeSafe documents as a weak spot ("Indirection").
  The gate-reached question needs a deterministic backstop: coverage of the branch, or the
  mutation run itself.
- **The static checks carried most of the correct flags.** Jev added value on the control-case
  and gate questions for filter-shaped code.
- **`has_control_case` only fits filter or gate tests.** It should be asked only when the code
  under test filters or branches on input rows.
- **The first version of the gate question produced a false positive.** "Are all inputs set" was
  read literally and flagged a correct control-plus-negative test. Rewording it as "is it true at
  least once at the asserted call" fixed that.

## Real-incident evaluation (2026-09-25, `eval.py`)

**The set:** 13 real tests recovered from bybit-trader's git history, 5 vacuous and 8
discriminating. Four incidents have both a vacuous and a fixed version: MacroAvwaps starvation
(2 × 2 tests), ConfigCache retry storm, UnblockResurrection/03 and the phase-2 wrongful skip.
Three CVD tests are fixed versions only, because their vacuous versions were squash-merged away.
Labels come from commit messages and ticket text. The case files hold bybit-trader code and live
in the session scratchpad, not in this repo.

**The conditions:**
- Comments and docstrings are stripped from the tests, because three fixed tests describe their
  own fix.
- The ticket intent is included.
- Jev: 5 repeats per case. Claude Haiku: 2 blind runs on anonymised, shuffled request files. An
  earlier Haiku run was discarded because the filenames revealed the labels.

**Scores.** AUC runs from 0.5 (no signal) to 1.0 (perfect separation); differences under 0.05
count as ties. "Pairs" counts vacuous/fixed pairs within one incident where the vacuous test
scores clearly higher.

| Question | Jev AUC | Jev pairs | Haiku AUC | Haiku pairs |
|---|---|---|---|---|
| exercises_ticket_scenario | **0.97** | 6/7 | 0.74 | 4/7 |
| weakness (score) | 0.74 | 6/7 | 0.57 | 4/7 |
| gate reached | 0.73 | 5/7 | 0.60 | 4/7 |
| fixture_is_static_population | 0.76 | 4/7 | 0.59 | 4/7 |
| has_control_case | 0.55 | 3/7 | 0.72 | 4/7 |
| mock questions, test_kind | about 0.5 (no mock-based cases in the set) | | about 0.5 | |
| static checks (code) | 0.54 | 1/7 | same | |

**Cost and speed.** One Jev pass over all 13 cases costs about $0.0035 and takes about 0.7 s.
All 65 requests together took 3.5 s and cost $0.0175. Haiku as a sub-agent took 85–108 s per
pass. At API list price a Haiku pass would cost roughly $0.10–0.15 (about 83k input tokens at
$1/M plus output), which is about 30–40× Jev's cost.

**Verdict rule as written before the real set** (`judge.verdict`): 3 of 5 vacuous tests flagged,
1 of 8 fixed tests flagged. The rule is dragged down by `has_control_case`, which misfires on
almost everything.

**Per incident:**
- **MacroAvwaps (8 weeks of starvation in prod):** clear catch. On `exercises_ticket_scenario`
  the vacuous tests scored 0.95 and 0.94, the fixed ones 0.08 and 0.09. On the static-population
  question they scored 0.93 and 0.94 against 0.27.
- **ConfigCache:** a weak signal on `exercises_ticket_scenario` (0.29 vs 0.07). The gate
  question missed it again (0.18 vs 0.15): both models fail to follow state left by an earlier
  call.
- **Resurrection:** a partial signal (0.45 vs 0.12 on exercises). Haiku saw nothing.
- **Phase-2 skip:** caught only by the static skip check.

## Leafcutter replication (2026-09-25, out-of-sample)

Full write-up:
[docs/analysis/2026-09-25-jev-test-triage-leafcutter-replication.md](../../docs/analysis/2026-09-25-jev-test-triage-leafcutter-replication.md).
The set was 38 tests from leafcutter's git history (17 vacuous, 21 discriminating, 22 incidents),
with Jev at 5 repeats and a blind Haiku baseline at 2 runs.

| | Jev | Haiku |
|---|---|---|
| exercises_ticket_scenario AUC / pairs | **0.84** / 14 of 18 | 0.77 / 8 of 18 |
| verdict v2 (flags / false alarms) | 17/17 / **9/21** | 9/17 / 4/21 |
| wiring questions on wiring-shaped incidents | reaches_entry_point 0.58, fixture_is_real_artifact 0.70 | n/a |

Against the REPLICATE.md §0 criteria:
- Criteria 1 and 3 are **met**.
- Criterion 2 is **not met**: the false-alarm rate is 43 % against a limit of 20 %.
- Experiment B is **not met**.

The ranking signal transfers to leafcutter; the verdict rule and the wiring questions do not. The
misses are the reachability incidents: tests that call the right function correctly, while
production never calls that function.

## Next steps

- Build a labelled set from the real bybit-trader incidents: pre-fix and post-fix versions of
  each test.
- Ask `has_control_case` only when the code filters or branches.
- Add a branch-coverage check (`coverage.py` on the single test) to answer the gate question
  exactly.
- Feed the ranked attacks into a mutation runner (`test-breaker`).
