---
title: "The wrong-version gate tests a different guess each run"
description: "Measured across three wrong-version rounds on BO-2900a-2-i and two on BO-2900a-1-ii (2026-10-23): the test-breaker turned the same must_catch name into a behaviourally different alteration for 6 of 13 preparable names on BO-2900a-2-i and 4 of 7 on BO-2900a-1-ii. Nothing reuses a manifest: the writer deletes the last one before writing the next. Two of the three latest survivors are equivalent to the code as written on the inputs of the test they were run against. Recommends pinning each work key's validated replacements, re-applied to the current code every run."
type: explanation
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md
  - docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-i.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-iv.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-ix.yaml
---

# The wrong-version gate tests a different guess each run

The wrong-version gate (TQ-500g-1) holds each guarding test to the wrong versions its own
`test_spec` entry names in `must_catch`. The names are prose. On every run the test-breaker,
an LLM agent, turns each name into concrete replacements. A deterministic writer applies
them, and the runner decides caught or survived from real pytest runs.

The runs and the writer are deterministic; the guess is not. On 2026-10-23 the same names
became different code on different runs, so verdicts could not be compared across runs and
the ticket had no fixed target to converge on.

Labels used below: **MEASURED** means read from a journal, a manifest or the code.
**INFERRED** means reasoned from the code, without being executed.

## Evidence

- Journals for drive `344eaa23`: `wf_f982c0ab-e94` (runs 1 and 2, resumed), `wf_466784ea-716`
  (run 3) and `wf_cdd3d484-ddb` (run 4). I read the `bf-wv-list`, `bf-wv-test-breaker` and
  `bf-wv-finish` results by matching `key` with a script, and summed per-agent token usage
  from the sibling `agent-*.jsonl` transcripts.
- The current manifests in the epic workspace:
  `.git/leafcutter/work/04_TICKET-20261022-BO-2900a-2-i/alterations.json` (written 16:59) and
  `.../01_TICKET-20261022-BO-2900a-1-ii/alterations.json` (16:49). They match the run 4
  replies entry for entry.
- The code in this workspace (origin/main `54efbdd3`) and the epic's uncommitted
  `_observer_startup_shim.py`, `run_observer.py`, `test_bo_2900a_2_i.py` and `BO-2900a-2-i.yaml`.

**Rounds.** BO-2900a-2-i went through test-breaker plus finish three times: **I** (`wf_f982`,
journal line 189), **II** (`wf_466784`, line 35) and **III** (`wf_cdd3`, line 39).
BO-2900a-1-ii was prepared twice: **a** (`wf_f982`, line 159) and **b** (`wf_cdd3`, line 23).
In round a the finish step never ran. The permission system denied the Bash call with
"[Security Test Removal]", so those alterations were never tested.

Between the rounds the tests and the AC changed outside these workflows. Before round III
the AC moved three `must_catch` claims to other tests ("IT PO NOTE 2026-10-23" in
`BO-2900a-2-i.yaml`) and replaced the argv name. That is part of the story below.

## 1. Per name: how many distinct alterations, and the verdicts (MEASURED)

"Distinct" counts behaviour, not text. Replies that differ only in spelling count as one:
`f_globals['__name__']` against `.get('__name__')`, `os` against `__import__("os")`, or a
longer `old` snippet for the same edit.

**BO-2900a-2-i** (14 names in rounds I and II, 13 in III):

| must_catch name (shortened) | Distinct | I | II | III |
|---|---|---|---|---|
| answers reached for every proof | 1 | A caught | A caught | A caught |
| answers not_reached for every proof | 1 | A caught | A caught | A caught |
| reads the launched argv and accepts a zero exit | 0 | could_not_prepare | could_not_prepare | (name replaced) |
| keyed on `frame.f_globals['__name__']` | 1 | A caught | A caught | A caught |
| only sees the in-process case | 2 | A `by_node.get → []` caught | B drop the child-merge loop, caught | B caught |
| credits any spawn of the unit | 1 | A caught | A caught | A caught ×2 |
| propagation that reaches only one level deep | 2 | A drop `or _STATE.inherited` in `_spawn_under_entry_point`, **survived** | B children skip `_patch_popen()`, **survived** | B **survived** |
| ancestry join credits code reached anywhere | 1 | A `if kind[1]:` **survived** | A **survived** | A caught |
| run-level or file-level record, both tests reached | 2 | A every test joined to all processes, caught | A caught | B `self.reached` moved from `reset()` to `__init__`, **survived** |
| records keyed on the proof file path | 1 | A caught | A caught | A caught |
| relies on environment inheritance | 2 | A caller's env passed unmerged, caught | B no merge on either Popen path, caught | A caught |
| reports unwatched for any test supplying its own env | 3 | A `events = -(10**9)`, caught | B = the env-inheritance edit A, caught | C an `unwatched` flag zeroes `events`, caught |
| naive chain re-invokes the previous sitecustomize | 2 | A `rest = list(sys.path)`, caught | B drop the `_lc_obs_installed` guard, **survived** | A **survived** |
| guard suppresses installation after the first child | 1 | A caught | A caught | A caught |

Of the 13 names that could be prepared, **6 received behaviourally different alterations
across the three rounds.** Verdicts changed for 4 names. One of those changes is
convergence, not noise: the ancestry-join alteration stayed the same in all three rounds,
and it moved from survived to caught once a test aimed at it existed.

**BO-2900a-1-ii** (9 names; round a was never run):

| must_catch name (shortened) | Distinct | a | b |
|---|---|---|---|
| still returns `eligible: False` on the direct-import fixture | 2 | False only when a finding was collected | False always; caught |
| passes the verdict through but announces nothing | 2 | the `print` and collector append removed | `return {}` before the cause list; caught |
| leaves eligible alone, writes refusal_cause or reason | 2 | conditional, writes both | unconditional, refusal_cause only; caught |
| a fixture on which no entry point resolves | 1 | **prepared**: `_module_defines_main` returns False | could_not_prepare |
| announces a finding for a proof that did enter | 1 | `elif … → else:` | same; caught |
| a rule never reached on any fixture | 2 | the call replaced by `pass` | `if False and _module_defines_main(unit)`; caught |
| announcement names an env var to silence it | 1 | message text | same; caught |
| suppression path exists, text mentions nothing | 1 | env check, `return {}` | same; caught |
| an assertion that reads the source file | 0 | could_not_prepare | could_not_prepare |

That is 4 of the 7 names prepared both times. The status itself changed too: the fixture
name was prepared in round a and refused in round b. Round a's alteration for it is, in
behaviour, round b's alteration for "a rule never reached".

The agent's own rule did not stop this: `test-breaker.md`:131 makes a name with "more than
one reading" could_not_prepare, but the agent sees one reading per run and never applied it.

## 2. Why it happens mechanically (MEASURED, from the code)

1. **Every run dispatches the preparer.** `wvRuns` in `templates/workflows-js/build-feature.js`
   (lines 1828-1851) runs `list`, then dispatches `test-breaker` whenever `listed.owed` is
   non-empty (line 1839), then `finish`. It never asks whether a manifest already exists.
   The prompt carries no earlier reply.
2. **Every finish rewrites the manifest.** `wrong_version_gate.py finish` (line 97) always
   calls `wrong_version_writer.py write`. The writer's first action is `_clean`
   (`_wvw_write.py`:52-57, called at :133), which deletes `alterations.json` and `copies/`.
   That is deliberate (TQ-500g-1-ix: "an unreadable reply can never leave an old manifest to
   be read in its place"). Its consequence is that earlier guesses are destroyed. Only the
   last manifest per work key exists, which is why rounds I and II could be read only from
   the journals.
3. **No reader of an old manifest exists.** The runner reads only the `--alterations` path
   the writer just printed (`wrong_version_runner.py`:320). It applies each entry's whole
   `altered_copy` file (`_wvr_scope.py`:319), not the replacement.
4. **What TQ-500g-1-iii keeps is a different thing.** -iii keeps the *as-written* copies and
   an apply/put-back journal under `leafcutter/wrong-version-runs/<run-id>/`. A resumed drive
   uses them to restore an altered file (`bf-wv-recover`, which ran first in runs 3 and 4 and
   returned `restored: []`). TQ-500g-1-i says the per-work manifests "survive a crash, and
   let a resumed drive find them". No step does find them and use them again. A resumed
   workflow can replay a journalled agent result only within the same workflow run. Runs 3
   and 4 were new workflows, with new journals.
5. **The writer's determinism does not reach the reply.** TQ-500g-1-ix promises
   "same reply, owed names and code give a byte-identical manifest". That holds, but the
   reply is the part that changes.

## 3. Consequences

**(a) The gate cannot converge (MEASURED).** A test written to catch round N's alteration is
judged in round N+1 against a new one. The `must_catch` comment on
`test_ac5_a_grandchild_is_credited_only_through_inherited_ancestry` describes round I's
alteration ("a grandchild of a child that never entered the entry point is no longer
credited"). Rounds II and III ran a different one against it. The "naive chain" claim was
moved to `test_a_second_install_in_one_interpreter_is_a_no_op` because round II's guess
(dropping the guard) survived the shim test. Round III then went back to round I's guess,
which the shim test had caught in round I and which the new test cannot reach. The one name
that converged is the one whose alteration stayed the same.

**(b) A "caught" proves only that run's guess (MEASURED).** "run-level record" was caught in
rounds I and II and survived in III. The tests did not change in between. The guess did.

**(c) Cost per round (MEASURED; totals include cache reads).** The gate steps for
BO-2900a-2-i cost 436k tokens in round I (list 88k, test-breaker 86k, finish 263k), 601k in
round II and 338k in round III. Whole workflows: run 3 cost 3.53M and run 4 cost 3.55M, most
of it outside the gate (documentation-verifier alone 0.45-0.80M per dispatch). Runs 1 and 2
together cost 46.1M. The test edits and AC edits between rounds were made in the main session
and are not in these figures. I could not reproduce the "~1.3M per round" figure from the
transcripts. Every non-convergent round repeats at least the gate's 0.34-0.60M, and in
practice a whole workflow run.

**(d) A fresh guess can be an unfair survivor (INFERRED, by reading the code, not executed).**

- *propagation, round III, against `test_ac5`.* The proof calls `unit_mod.main` in the host,
  so the host's patched Popen gives `mid.py` an environment with
  `LC_OBS_PARENT_UNDER_EP=1`, the `LC_OBS_*` variables and the boot directory on
  `PYTHONPATH`. With `_patch_popen()` skipped in children, `mid.py` spawns `direct_child.py`
  without `env=`, so the grandchild inherits that same environment. It installs the
  observer, has `inherited` true, and reaches the handler. That is the same record as on the
  code as written. **The mutant is equivalent on this test's inputs.** It differs only when a
  child replaces the environment, or enters an entry point that its parent had not.
  It is also weaker than its name, because propagation still reaches the grandchild by
  inheritance. This is the no-op family of
  KI-BO-20261023-test-breaker-no-op-alterations. Round I's alteration was faithful to the name.
- *naive chain, round III, against `test_a_second_install…`.* That test loads the shim by
  path and calls `install()` twice. It never generates a `sitecustomize.py` and never calls
  `chain_sitecustomize`. So the altered line `rest = list(sys.path)` is never executed.
  **The mutant is equivalent on this test's inputs.** It is a real defect: the boot
  `sitecustomize` finds itself again and recurses. The shim test caught it in round I, but
  that test no longer claims the name.
- *run-level record, round III, against `test_two_tests_in_one_file…`.* Under the
  alteration, `reset()` no longer clears `self.reached`. In this pair, the host's `reached`
  is never filled: the spawn test reaches the handler only in a child, and the direct-import
  test has no live entry frame and no inherited ancestry. So the host leaks nothing between
  the two tests. **The mutant is equivalent on these inputs, but not in general.** An
  in-process proof followed by a direct-import proof in one file would expose it. This
  survivor is fair: it shows a real gap in the test. The fresh guess found something, but
  only by moving the target.

So two round-III survivors point at a test that cannot exercise the altered line or value,
and one at a real gap. In the gate's output the three look the same.

## 4. Names that describe a defect in a test, not in the code

BO-2900a-1-ii names "a fixture on which no entry point resolves, so the report-only branch is
never reached and the test passes vacuously" and "an assertion that reads the source file
rather than the emitted line…". `must_catch` means *a wrong version of the code that this
test must catch*. No change to the code is a wrong fixture or a wrong assertion. The
test-breaker may not touch test files (`test-breaker.md`:167-170), so these names can only
come back as could_not_prepare. TQ-500g-1-i (it_requirements, line 124) counts that as
unfinished, so the gate fails on every run.

**Is "unfinished = fail" right?** It is right as fail-closed for a name the code *should*
have but does not, and it worked here: the argv name was replaced by the AC author with an
expressible name, and that name was caught. For test-defect names it is the wrong signal.
The work is not unfinished. The requirement is mis-specified, and no coder or test-writer
round can resolve it.

**What the AC author should do (INFERRED).** Name the wrong version of the code that the
defective test would let through. Both names already have such a counterpart in the same
entry:

- The vacuous fixture lets through "a rule that is never reached at all on any fixture".
  Round a's preparation of the fixture name was exactly that alteration.
- The source-reading assertion lets through "a rule that passes the verdict through but
  announces nothing", a rule that never emits.

So both names are redundant and should be deleted from `must_catch`. Where the test-defect
concern has to stay on record, it belongs in the entry's `description` or in review, not in
`must_catch`. An authoring check could refuse a `must_catch` string whose subject is a
fixture, an assertion or a test, before a drive ever starts.

**Follow-up (TQ-500f-2-iii).** The authoring side is now handled where `must_catch` is
filled, and it is not a keyword refusal. The code-aware test designer
(`templates/agents/test-designer.md`, TQ-500f-2-ii; judgement rationale in
`docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md`) puts one
question to each candidate name: can a change to the code under test be this name? A name
that fails it is left out of `must_catch`, the code-side wrong version it would let through
is named instead (not added twice), and the concern stays in that test entry's `description`.
A keyword filter was ruled out because names about assertions and fixtures are legitimate
where the code under test analyses tests (TQ-500g-3-iii). As a backstop, a name of this
kind that still reaches a drive is answered by the preparer
(`templates/agents/test-breaker.md`, TQ-500g-1-iv) as could_not_prepare with a fixed reason
saying it names a defect in a test rather than in the code, so a reader sees the requirement
must be corrected, not the code or the tests. Related sibling failure:
`docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md`.

## 5. Remedy options compared

| | (i) Pin | (ii) Deterministic preparation | (iii) AC carries the alteration | (iv) Leave as is |
|---|---|---|---|---|
| Fixes | Same alteration on every run of a work key. A test can be written against it and stay caught. Saves the test-breaker dispatch for unchanged names. | Nothing reliably | Exact, reviewable alteration for the names that matter; no LLM in the loop for them | Nothing |
| Does not fix | A bad first guess stays bad (no-op, equivalent mutant). Loses the "new reading" exploration that found the round III gap. | Inputs change as the code changes, so the reply changes anyway | Prose names stay unpinned; the AC goes stale as code moves | Non-convergence, cost, unfair survivors |
| Cost | Writer and route change; a pin file per work key; re-validation each run (cheap, deterministic) | Not available: the agent frontmatter (`model`, `tools`, …) and the workflow `agent()` options used in `build-feature.js` (`agentType`, `schema`, `label`, `phase`) carry no temperature or seed. Even at temperature 0, LLM output is not guaranteed identical across calls. | AC authoring effort per name; a schema field and writer path | 0.34-0.60M tokens per round for the gate, plus the rework |
| Invariant that must hold | See below | — | The declared `old` must still match the current code exactly once, or the name becomes unfinished, never silently skipped | — |

**Invariants for a pin (i).** These come from the code and are not optional:

1. **Pin the replacements, never the copies.** The runner writes the whole `altered_copy`
   over the file (`_wvr_scope.py`:319). A stored copy from an earlier run would also revert
   every code change made since. So each run must re-apply the pinned `{path, old, new}` to
   the *current* file and rebuild the copy. Today the manifest stores the diff and the
   copies, not the replacements, so the reply's replacements must be kept as well.
2. **Re-validate against the current code on every run.** `old` must occur exactly once.
   The result must load (`did_not_load` otherwise) and must change bytes (`not_applied`
   otherwise). If `old` no longer matches, the target changed: re-prepare that name and say
   so in the row. Never fall back to the stale copy, and never drop the name.
3. **Re-check effect, not only form.** As the code moves, a pinned edit can land on a line
   that the tests no longer execute, and silently become a no-op. The KI's proposed
   `not_executed` check (changed lines not executed by any in-scope test on the as-written
   run, so the row is unfinished rather than survived) would have flagged the round-III
   naive-chain survivor. A pin needs it more than a fresh guess does.
4. **Prepare only what is new.** Dispatch the test-breaker only for names that are absent
   from the pin, whose `old` no longer matches, or whose `must_catch` string changed.
5. **Keep history.** Keep every manifest a work key produced (append-only, by run id), and
   name the alteration (a hash of its replacements) in every result row. Then "caught" means
   caught *this* alteration. This replaces `_clean`'s delete with a move. The guard
   "never read an old manifest by mistake" still holds because the runner reads only the
   path it is given.
6. **An explicit reset.** An operator command that drops a name's pin, for when a pinned
   alteration is judged unfaithful (round I-III propagation shows that a bad first guess
   would otherwise be locked in).

## 6. Recommendation

Adopt **(i) pinning with the six invariants**, add **(iii) as an optional declared
replacement** on a `test_spec` entry for names whose reading is contested, and fix the
**test-defect names in the ACs** (section 4) now, by hand. (ii) is not available. (iv) gave
a ticket that could not pass in three rounds.

Pinning gives up the exploration. The AC author can recover it deliberately: when two
readings of one name matter (round I's and round III's "propagation" are both real defects),
write two names. They are then two pinned wrong versions, each held to a test.

Acceptance criteria this needs (prose only; the YAML is for /plan-feature):

1. **Reuse.** Given a work key whose earlier run prepared name N, and whose `old` text still
   occurs exactly once in the current file, the next run applies the same replacement to the
   current file and does not send N to the test-breaker. This holds in a new workflow, not
   only on resume.
2. **Re-prepare on change.** When N's `old` no longer matches, or N's `must_catch` string
   changed, only N is re-prepared. Its row says "re-prepared: target changed", and the
   stored copy is never applied.
3. **Rebuilt from current code.** Every applied alteration is built from the current file
   plus the pinned replacements. A test proves that an unrelated change made elsewhere in
   the same file after pinning survives the alteration.
4. **Effect check.** An alteration, pinned or fresh, that changes no line executed by the
   in-scope tests on the as-written run is reported unfinished (`not_executed`), never
   survived. This is shared with the no-op KI.
5. **Traceable verdicts.** Each result row carries the alteration's identity. The manifests
   of earlier runs are kept, not deleted, and the runner still reads only the one it is
   handed.
6. **Declared replacement.** A `test_spec` entry may carry, per `must_catch` name, an exact
   replacement. The writer uses it in place of the test-breaker. If its `old` does not match,
   the name is unfinished with a reason that names the AC.
7. **Reset.** One command removes the pin for a named wrong version (or a whole work key),
   and the next run re-prepares it.
8. **Authoring refusal.** At AC authoring, a `must_catch` string that names a defect in a
   test (a fixture, an assertion) is refused, with a pointer to the code-side wrong version
   it should name instead.

## What this page does not establish

The round-III equivalence was decided by reading the code, not by running it; trace each in a
scratch copy before relying on it. That the between-round tests failed under an earlier
altered copy happened outside these journals and is not verified here.
