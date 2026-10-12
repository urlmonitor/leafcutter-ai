---
title: "KI-BO-010 — RESOLVED: `/quick-fix`'s divergence gate was a first-token substring match with a looping remedy; both halves were replaced on 2026-08-26 and the entry was never closed"
description: "KI-BO-010 — RESOLVED: the first-token substring check became a stopworded content-word disjointness test, and the halt gained an explicit `divergence_decision: 'continue'` resume path. Both landed in f1726aef (#602), eight days after filing. The entry stayed open for a further five weeks."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-010 — RESOLVED: `/quick-fix`'s divergence gate was a first-token substring match, and its own remedy looped

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14 and moved to `resolved/` on 2026-09-23. Index:
> [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **closed — fixed 2026-08-26 in `f1726aef` (#602), confirmed behaviourally 2026-09-23**
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Fixed:** 2026-08-26 · **Entry closed:** 2026-09-23
- **Where (then):** `templates/workflows-js/quick-fix.js:292-306` (the BP-600e-2 divergence check)
- **Where (now):** the block headed `// Check for root-cause divergence (BP-600e-2)` —
  `divergenceContentWords()`, `divergenceCheck`, and the `divergence_decision` branch,
  lines 554-651 at `9f783a26`

## The original report, unchanged

**Symptom.** After a confirmed red baseline, the workflow halts with "The test failure
suggests the root cause may differ from your diagnosis" — on diagnoses the tests
unanimously confirm. The whole check is:

```js
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])
```

It takes the **first whitespace-delimited token** of a prose diagnosis and asks whether
that literal string appears in the pytest output. Any leading markdown defeats it: a
`root_cause` beginning `` `handoff` `` yields the token `` `handoff` ``, backticks
included, which never appears in test output that says `handoff`. A leading article
("The adjudication branch…" → `the`) inverts the failure the other way — `the` appears in
essentially every pytest output, so the gate silently passes regardless of whether the
diagnosis is right. It is a coin flip decided by the first word's punctuation.

**Evidence.** Observed 2026-08-18 fixing the handoff-routing defect. The red phase
produced three failures that reproduced the diagnosis precisely — `test-writer` dispatched
once instead of twice in both drivers, and an unparseable handoff target advancing to
`pr-reviewer` instead of failing closed. The gate halted anyway on the backtick mismatch.
Re-running with the identical diagnosis reworded to open with a bare `handoff` cleared it.
Nothing about the analysis changed; one word lost two backticks.

**The stated remedy does not work.** The halt message reads *"To continue, re-run
/quick-fix with the same args."* The check is a pure function of `root_cause` and the
failure text, with no confirmation flag and no persisted state, so re-running with the
same args recomputes the same verdict and halts identically. The only exits are to reword
the diagnosis until the first token happens to match, or to abandon the workflow — and the
message advises neither.

**Why this matters more than it looks.** A gate this coarse trains people to defeat it.
The reliable way past it is to open `root_cause` with a common English word, which makes
the check pass unconditionally — so the failure mode it converges on is not false halts
but a permanently green gate that never reads the diagnosis at all.

**Fix direction.** Delete it or make it real. A first-token substring match cannot assess
whether a failure corroborates a diagnosis, so it should not be shaped like a verdict — at
minimum downgrade it to an advisory `log()` that never halts. If a genuine check is wanted,
it belongs with an agent that reads the failure and the diagnosis and judges them, and it
needs a confirmation path so an operator who has looked at both can proceed. Whatever
replaces it must make its own remedy reachable.

Filed as KI-BO-008 while this work sat uncommitted; renumbered to 010 on landing, main
having published a different KI-BO-008 and a KI-BO-009 in the interim.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check that cannot assess
correctness reporting a verdict anyway), in its fail-closed form.

---

## What replaced it

Both halves were rewritten in `f1726aef` (2026-08-26, PR #602 — *"fix the eight defects the
red baselines exposed, and three of the baselines"*).

**The comparison.** The first-token substring test is gone. The gate now reduces both the
diagnosis and the observed failure to their **content vocabulary** — lowercased, split on
non-alphanumerics, with a 35-word stoplist and 1-2 character fragments dropped, and common
inflectional endings stripped so `exhausted`/`exhausts` and `header`/`headers` compare
equal. It warns only on **total disjointness**:

```js
const divergenceCheck = comparable && sharedWords === 0
```

The two failure directions the entry described are both closed by this. A diagnosis opening
"The …" no longer matches everything, because `the` is a stopword and is never counted. A
correct diagnosis whose first word is punctuated or paraphrased away no longer diverges,
because the verdict rests on the whole vocabulary rather than one token.

`comparable` is `failureMsg.length > 0 && diagnosisWords.size > 0`, and the
not-comparable case logs *"Divergence check skipped: the diagnosed root cause carries no
content words to compare"* rather than inventing a verdict — which is the specific thing the
entry's Pattern line objected to.

**The remedy.** `divergence_decision` is destructured from the diagnosis args and read at the
branch:

```js
if (divergenceCheck && divergence_decision === 'continue') {
  log('Divergence acknowledged by an explicit continue decision — proceeding to the Fix phase.')
} else if (divergenceCheck) { … return blocked(…) }
```

The halt message names it: *"re-run /quick-fix with the same args plus
`divergence_decision: 'continue'`"*. The entry's closing requirement — *"Whatever replaces it
must make its own remedy reachable"* — is met.

## Evidence it works, not just that the code changed

`unit_tests/workflows/test_bp600e2_divergence_behavioral.py` covers exactly the three
behaviours this entry named. It executes the **real** `quick-fix.js` in a Node subprocess via
`_workflow_engine_harness.run_workflow_under_e2()` and records the agent dispatches —
nothing in it greps the JS source, which is how the original four tests passed on the broken
check (see BP-600e-2's own notes).

Run at `9f783a26` under `AC_ENFORCE_STRICT=1`, so nothing can be downgraded to `xfail`:

```text
test_ac_bp600e2_continue_decision_does_not_resume_the_halted_run              PASSED
test_ac_bp600e2_genuine_convergence_without_shared_first_token_is_falsely_flagged  PASSED
test_ac_bp600e2_shared_first_token_genuine_divergence_is_not_caught           PASSED
3 passed
```

The test names describe the **defects**, because they were authored as the red baseline for
them. All three passing is the assertion that none of the three behaviours still occurs.

## BP-600e-2 is NOT closed by this, and should not be

`docs/acceptance-criteria/build_pipeline/BP-600-quick-fix-workflow/BP-600e-2.yaml` stays
`work_status: todo`. Its `it_requirements` ask for *"LLM-based comparison of diagnosed
root_cause text with actual test failure output"*, and what shipped is lexical. The
implementation says so itself, in the comment above the check: one incidental shared word
suppresses the warning, *"the honest ceiling of a lexical comparison and the reason
BP-600e-2's it_requirements ask for a semantic one."*

So the two defects **this entry** recorded are fixed and the AC's stricter requirement is
not. Those are different claims and the register should not merge them — closing the AC off
this evidence would be the same phantom-done move that reopened it on 2026-08-25. That
record's `notes` still quote the old `:568-569` code as current; anyone picking BP-600e-2 up
should read this entry first.

## Why the entry stayed open for five weeks after it was fixed

The fix landed eight days after filing, in a commit that fixed eight unrelated defects at
once and named none of them by KI id. Nothing then connects a fix back to the register: the
index's own instructions say to close an issue by deleting its section and *"reference the
issue id in the commit message"*, which is an author-discipline step with no gate behind it.
The entry was then carried verbatim through the one-file-per-issue split (#817, 2026-09-15)
— stale line anchor, present-tense claims and all — because that migration moved files
rather than re-verifying them.

The cost is not tidiness. It sat as the **highest-severity open `/quick-fix` issue** in this
register for five weeks, with a *"delete it or make it real"* fix direction arguing for
roughly the design that had already shipped. A reader acting on it would have rebuilt a
working gate.

**Pattern:** a defect register with a documented close step and no mechanism behind it
accumulates entries that are wrong in the most expensive direction — they describe work as
outstanding that is done, so the next person spends their effort re-deriving a fix instead of
on the 48 entries that are still real. Same shape as `KI-CG-20260914-doc-length-blocks-registers`,
retracted in #824, which likewise outlived its own truth on a surface nobody re-reads.
