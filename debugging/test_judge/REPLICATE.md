# Runbook: replicate the Jev test-triage evaluation on leafcutter's own history

This is written for a model working in the leafcutter-ai repository. Follow it top to bottom.
It repeats the bybit-trader evaluation
([docs/analysis/2026-09-25-jev-test-triage-evaluation.md](../../docs/analysis/2026-09-25-jev-test-triage-evaluation.md))
on leafcutter's own incidents. That makes this the **out-of-sample test**: the verdict rule `v2`
and the wiring questions were fixed before any leafcutter case existed.

## 0. What you are deciding, fixed in advance

Do not change these criteria after you have seen any result.

**The benefit replicates** if, on the Jev run with `--strip-comments`:
1. `exercises_ticket_scenario` has an AUC of at least **0.75**; and
2. verdict `v2` flags at least **60 %** of the vacuous cases, with at most **20 %** false alarms on
   the discriminating cases; and
3. Jev's AUC on `exercises_ticket_scenario` is at least Haiku's minus 0.05. In other words, it is
   not clearly worse than the baseline.

**Experiment B (`--wiring`)** is judged separately. A wiring question is useful if its AUC is at
least 0.75 on the cases whose incident is wiring-shaped (reachability, seam, authenticity).

Report every criterion as met or not met, with the numbers. "Partly" is not an answer.

## 1. Prerequisites

| Need | Where |
|---|---|
| Scripts | `debugging/test_judge/`: `judge.py`, `collect.py`, `questions.py`, `eval.py`, `make_case.py`. `debugging/` is **untracked** in the original clone. If the folder is missing in your checkout, stop and ask the user to commit it or copy it in. Never rewrite the scripts from memory. |
| Python | 3.10 or newer, plus `httpx` (`pip install httpx`). Nothing else is needed. |
| API key | `JEV_API_KEY` or `TYPESAFE_API_KEY` in the environment, or in a `.env` passed with `--env-file`. Never print it, log it or commit it. |
| Scratch space | Put case folders, requests and results **outside the repo** (your scratchpad or `%TEMP%`). Never write them under the project tree. |
| Authorisation | Every Jev call sends leafcutter test and code excerpts to TypeSafe, a third party. Confirm with the user before the first real call. `--dry-run` and `--export` send nothing. |

Smoke test, which sends no code of yours:

```bash
cd debugging/test_judge
python judge.py --samples --dry-run        # builds 4 requests from bundled samples; must print 4 test functions
python judge.py --samples --runs 3 --env-file <path-to>.env   # optional live check, about $0.0007
```

## 2. Rules that protect the result

Each rule exists because breaking it corrupted a real run.

1. **Read-only on git.** Use only `git log`, `git show`, `git diff`, `git grep` and `git reflog`.
   No checkout, stash, reset or branch switch; sibling sessions share this clone.
2. **Cases come from git verbatim.** Build every case with `make_case.py`, which copies the test
   and code files with `git show <sha>:<path>`. Never hand-edit a test to make a "bad" version.
   If a vacuous version was squash-merged away, record it as not recoverable and move on.
3. **Every label needs written evidence**: a commit message, ticket text, retrospective, known-issue
   entry or doc, quoted in `--evidence`. Your own judgement is not evidence.
4. **Test and code come from the same commit.** Never pair a test from one commit with code from
   another; that manufactures a result.
5. **Both halves of a pair share `--incident` and `--ticket-intent` verbatim.** The intent
   describes the failure the test should catch. It must not describe either test.
6. **Always `--strip-comments`.** Fixed tests narrate their own fix ("…can go vacuous again…"),
   which leaks the label. Also report the raw run, so the size of that effect is visible.
7. **Only ever hand another model the blind export** (`req_NN.json`). Case folder names carry the
   label (`x_bad`, `x_good`). The mapping file stays with you. In the bybit-trader run, labelled
   filenames contaminated the first Haiku attempt, and it had to be thrown away.
8. **Use the same flags everywhere.** `--strip-comments`, `--wiring` and `--no-ticket` change the
   question set. Use identical flags for the Jev run, the export and the answer import.
9. **Do not retune `v2` or the thresholds on this data.** If you think a better rule exists, write
   it down as `v3` and pre-register it for the *next* dataset.

## 3. Pick incidents

Start from the failure catalogue in
[docs/testing/test-angles.md](../../docs/testing/test-angles.md) ("Failure catalogue — the
evidence base"). Then look at `docs/retrospectives/`, `docs/known-issues/` and `git log --grep`.
Leads with references, not yet verified to be recoverable:

| Incident | References | Shape |
|---|---|---|
| BO-2400f-7..10: lifecycle functions reachable by no CLI and no workflow | `8f0c55c2b` (#411) → `9c58f4550` (#422) | reachability |
| BO-1700 T02: `check_hook_freshness()` result discarded | `50e28cc1`, EPIC-BOPhantomDoneRemediation | reachability |
| EPIC-PhantomDoneFilesTouched KI-1: `files_touched` parser a no-op on real tickets | PR #209 / `17c538fe` | authenticity |
| GenReviewFixes H-2: `importlib.reload()` hid a cold-import `NameError` | PR #372 / `439b74007` | authenticity |
| BO-1000b-1-i: count-guard regex blind to template-literal calls | fix `17735a2ed` | authenticity / discrimination |
| FIN-100h: a refused status recorded as a clean merge | `a0bcb8a6c` (#437) | failure / negative control |
| EPIC-BOPhantomDoneRemediation T03: `_check_risk_surface` lacked the empty-list guard | T03 ticket | boundary |
| EPIC-ComputedQualityGates FP-1: call sites passed no axes | PR #201 | seam |
| BO-400c-3-i: the production call site still passed one argument | EPIC-BOPhantomDoneRemediation T04 | seam |

**Scope limits of the prototype:**
- **Python tests only.** The extractor parses Python with `ast`, so skip JS/vitest workflow tests.
- **Pytest fixtures in `conftest.py` are not followed.** Fixtures defined in the test file are
  followed through its parameter names. If a test's meaning lives in a conftest fixture, say so in
  the case's `why` field, or skip the case.
- **At most 3 code files per case,** and only the ones the test exercises.
- **Aim for at least 8 vacuous and 8 discriminating cases,** with as many complete pairs as the
  history allows. Fixed-only cases are allowed, but only pairs feed "pairs won".

### Archaeology with sub-agents

The search is slow and parallelises well. Give each incident group to one general-purpose agent,
running in the background, with this prompt (fill in the placeholders):

```text
You are building a LABELLED EVALUATION SET of real unit tests from git history.
Read-only on the repo: never checkout, stash, reset, commit or switch branches. Use only
git log / git show <sha>:<path> / git diff / git grep / git reflog and file reads.

Repo: <leafcutter repo path>
For each incident below, find (a) the VACUOUS version of a test function -- a test that stayed green
although it could not detect the bug it was meant to catch -- and (b) the FIXED, DISCRIMINATING
version (or its replacement). Each must be paired with the production code AT THE SAME COMMIT.
Labels must be backed by written evidence (commit message, ticket, retrospective, known-issue, doc)
-- never your opinion. If a version only existed in squash-merged-away commits, report it as not
recoverable; do NOT reconstruct or hand-edit anything.

Incidents: <list with references from the table>

Do not write case folders yourself. For every recoverable version, output one line of arguments
for make_case.py:
  --case-id <incident>_bad|_good --sha <sha> --test <path> --test-function <Class.test or test>
  --code <path> [--code <path>] --label vacuous|discriminating --incident "<same for the pair>"
  --gate "<condition verbatim from the code>" --ticket-intent "<identical for the pair>"
  --evidence "<quote + source>" --why "<one sentence>"
Finish with a table: case-id, label, sha, evidence source; plus the incidents you could not recover and why.
```

Run `make_case.py` yourself with the returned arguments, so every case is copied straight from git:

```bash
python debugging/test_judge/make_case.py --repo . --out <scratch>/cases <arguments from the agent>
```

`make_case.py` refuses a test function that is not in the file. It warns when a `--gate` is not
found verbatim in the code at that commit; fix the gate text rather than ignoring the warning.

## 4. Check the set before spending anything

```bash
cd debugging/test_judge
python - <scratch>/cases <<'EOF'
import sys, json, argparse, re
from pathlib import Path
import eval as E
a = argparse.Namespace(max_code_chars=12000, max_test_chars=8000, model="jev-latest",
                       ticket=True, strip_comments=True, wiring=True)
for c in sorted(p for p in Path(sys.argv[1]).iterdir() if (p / "meta.json").is_file()):
    meta, body, t = E.build(c, a)
    leaks = re.findall(r"(?i)vacuous|mutation|pre-fix|old code|_bad|_good", json.dumps(body["state"]))
    print(f"{c.name:<24} {meta['label'][:4]} req={len(json.dumps(body)):>6} "
          f"fixtures={len(t.fixtures):>2} static={list(t.static_flags)} leaks={leaks}")
EOF
```

Every case must load. `leaks` must be empty. Each request should be under about 100k
characters; Jev's limit is 32k tokens for the state plus the longest question. A test whose body
is a one-line call to a helper should show `fixtures>0`; if it doesn't, the extractor missed the
helper, so fix the case or drop it.

## 5. Run Jev

Get the user's go-ahead first (see §1). Each run below costs well under $0.10.

```bash
cd debugging/test_judge
E=<path-to>.env; C=<scratch>/cases; R=<scratch>/results; mkdir -p $R
python eval.py --cases $C --runs 5 --strip-comments           --env-file $E --out $R/jev_stripped.json
python eval.py --cases $C --runs 5                            --env-file $E --out $R/jev_raw.json
python eval.py --cases $C --runs 5 --strip-comments --wiring  --env-file $E --out $R/jev_wiring.json
```

## 6. Run the Haiku baseline, blind

```bash
python eval.py --cases $C --strip-comments --export $R/requests_blind
# writes $R/requests_blind/req_01.json ... and $R/requests_blind_mapping.json
```

Start **two** background agents with `model: haiku`. Each gets this prompt, with its own output
file name (`haiku_1.json`, `haiku_2.json`):

```text
You are acting as a judge model in a benchmark. Answer typed questions about unit tests.
Input: JSON request files req_01.json ... req_NN.json in <R>/requests_blind/
Each file has `state` (a test function with its fixtures, excerpts of the code under test, and
usually `ticket_intent`) and `questions` (a map of question id -> question with `type`,
`instructions`, `criteria`).
RULES -- strict: read ONLY the req_*.json files in that folder. Do not list, open or search any other
file or folder (including sibling folders), do not run git. Judge each file independently from its
own content.
Answer format per question (TypeSafe API shapes):
- "noul":   {"type":"noul","noul": <probability 0..1 that the answer is yes/true per its criteria>}
- "choice": {"type":"choice","choice":"<best key>","probabilities":{<every key>: p, summing to 1},"confidence": <0..1>}
- "score":  {"type":"score","score": <expected level index as float, 0 = first level>,"legend":{"0":"...","1":"...",...}}
Write ONE JSON file to <R>/<haiku_N.json> shaped {"req_01": {"<question id>": <answer>, ...}, ...}
with every file and every question id verbatim (ids may contain colons). Validate it parses with
python. Reply "done" plus any file you could not answer.
```

Import both runs:

```bash
python eval.py --cases $C --strip-comments --from-answers $R/haiku_1.json --from-answers $R/haiku_2.json \
    --mapping $R/requests_blind_mapping.json --answers-model "claude-haiku blind x2" --out $R/haiku.json
```

Before you import, check that each answer file has every `req_NN` and every question id.
`eval.py` skips missing answers silently, and a skipped answer lowers the score without any error.

## 7. Score

```bash
python eval.py --cases $C --score $R/jev_stripped.json --score $R/haiku.json \
    --score $R/jev_raw.json --score $R/jev_wiring.json
```

Read, for each result file:
- the per-question table (AUC, pairs won, mean weak value for each label);
- the `verdict v1` and `verdict v2` lines (flags among vacuous, false alarms among discriminating);
- the per-case grid, to find which incident each hit or miss comes from.

For experiment B, compute the AUC of `reaches_entry_point` and `fixture_is_real_artifact` on the
wiring-shaped incidents only. Filter the cases by their `incident` value, and do not change the
data.

## 8. Write it up

Publish a new page `docs/analysis/<date>-jev-test-triage-leafcutter-replication.md` in the same
shape as the bybit-trader page:
1. The verdict first, against the §0 criteria, each marked met or not met.
2. The case table: incident, counts, mechanism, evidence source.
3. The results tables: Jev vs Haiku per question, the verdict rules, cost and time.
4. What changed relative to bybit-trader, and why.
5. "What we must do".
6. Limits, including the incidents you could not recover.

Link it from the bybit-trader page. Update this folder's `README.md` results section.

## Pitfalls already hit (so you don't repeat them)

- **Label leak through filenames.** Only ever give another model `req_NN` files.
- **Tests that describe their own fix.** Hence `--strip-comments`.
- **Thin test bodies** such as `self._run_eventual_service()`. The extractor follows inherited
  and module helpers up to 3 hops; check `fixtures>0`.
- **Large SQL or Python files.** Only windows around the gates, or the definitions the test
  reaches, are sent. If a gate string is not found verbatim, the excerpt falls back to the file
  head and the gate may be missing. `make_case.py` warns about this.
- **CRLF on Windows.** `make_case.py` writes with `newline=""`, so the files stay byte-identical
  to git.
- **Shell escaping.** Edit Python files with an editor tool, not with heredoc string
  replacement: `\n` and `\b` turned into literal characters twice.
- **An empty `python -` heredoc** starts an interactive REPL that hangs the shell.
- **A Haiku sub-agent given many files writes a script instead of judging.** On the 38-case
  leafcutter set, one run wrote a keyword heuristic that produced every answer. The other ran on
  too few tokens to have read all its files. Give each agent at most 10 files and forbid code that
  generates answers. After a run, check the folder for stray scripts, check that token use fits
  the input size, and check every `req_NN` for its own question IDs. One batch shifted its gate
  answers by one request.
- **Cost is not the risk; leakage and overfitting are.** A whole run costs cents. A contaminated
  or retuned run wastes the dataset, because a set that has been tuned on cannot be used as a test
  again.
