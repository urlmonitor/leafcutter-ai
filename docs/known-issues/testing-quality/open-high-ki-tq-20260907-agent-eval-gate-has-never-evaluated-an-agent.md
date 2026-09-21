---
title: "KI-TQ-20260907-agent-eval-gate-has-never-evaluated-an-agent — it fast-passes when nothing is affected and dies on a missing API key when something is"
description: "high — a required-looking green badge that has never once run the thing it names."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20260907-agent-eval-gate-has-never-evaluated-an-agent — it fast-passes when nothing is affected and dies on a missing API key when something is

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

**Severity:** high — a required-looking green badge that has never once run the thing it names.
**Found:** 2026-09-07, on `fix/product-truth-resync` (PR #738).
**Component:** testing-quality / CI (`Agent Evals` workflow, `scripts/evals/eval_selector.py`,
`scripts/evals/run_agent_eval.py`, `check_eval_staleness` pre-commit hook).

The `Agent evals (affected)` check has two branches and **neither one evaluates an agent.**

**Branch 1 — nothing affected, fast pass.** The selector diffs changed files against each
agent's declared `triggers` closure. When none match it prints, verbatim:

```
AFFECTED   (will run): <none>
UNAFFECTED (skipped as unaffected): flow-author mock-data-author pt-classifier
No affected agents — nothing to eval. Fast pass.
```

Every one of the twelve most recent `Agent Evals` runs before PR #738 took this branch. The
check was green on all of them. Zero evals ran on any of them.

**Branch 2 — something affected, infrastructure failure.** PR #738 touched
`docs/product-truth/index.json` and `docs/product-truth/flows/**`, which sit in the trigger
closures of `flow-author`, `mock-data-author` and `pt-classifier`. So the evals actually ran,
for what appears to be the first time. Every single row failed:

```
WARNING run_agent_eval: Row clf-017: model invocation/parse failed: claude CLI exited 1:
ERROR   run_agent_eval: claude CLI exited 1
subprocess.CalledProcessError: Command '['claude', '-p', ... ]' returned non-zero exit status 1
```

The job's environment dump shows `ANTHROPIC_API_KEY:` — empty. The CLI cannot authenticate, so
no row gets a model response.

**The score is the dangerous part, and it is worth understanding exactly.** Every failed
invocation yields `got=none`. The gate then reported:

```
GATE: FAIL — score 22.22% < threshold 70.00%
```

22.22% is 4 of 18. Those four are **not** partial successes. They are the rows whose *expected*
outcome happens to be `none`, matching the failure default by coincidence. A reader who sees
"22%" will reason about a degraded agent and go looking for a prompt regression. There is no
agent behaviour in that number at all. **A gate that cannot invoke its subject must score 0 or
error out — never a plausible-looking percentage**, because a plausible percentage sends the
next person to debug the wrong layer.

**Why nobody noticed.** The two branches conceal each other. Ordinary work does not touch
`docs/product-truth/**` or an agent template, so the check is green essentially always, and
that green is read as "the evals pass". The one branch that does trigger it reads as "this
branch broke the evals" rather than "the evals have never run". Both readings are locally
reasonable and both are wrong.

**A second-order effect worth its own attention.**
`docs/product-truth/scripts/generate_product_truth.py` is itself inside those trigger closures,
and its entire job is to rewrite the files the closures watch. Meanwhile
`check-product-truth-validate` fails the store whenever its derived data is stale and tells you
to run exactly that script. So one gate demands regeneration and the other charges three Opus
artifact evals (900s per-row timeout) for performing it. Keeping the store valid is expensive
by construction — which is a plausible reason the store sat drifted for seven weeks before
PR #738. The closures likely want to distinguish **derived** fields (`impl_status`,
`impl_asof`, `impl_summary` — written by the generator) from **authored** ones (steps, screens,
scenarios — written by `flow-author`). Only the latter can change an eval's verdict.

**Trap.** Do not "fix" this by relaxing the trigger closures alone. The closures are defensible:
`flow-author`'s eval declares `sandbox_copy: ["docs/product-truth"]`, so the whole store
genuinely is its input environment. The missing credential is the primary defect; the
over-broad closure is the secondary one. Fixing only the second would make the gate quieter
while leaving it just as incapable of evaluating anything.

**Fix direction.**
1. Provision the eval job's credential, and make a missing one a hard, named error at job
   start — never a per-row warning that degrades into a score.
2. Make an unrunnable eval distinguishable from a failing one in the gate's own output. "0 of
   18 rows invoked" and "4 of 18 rows passed" must not print the same shape.
3. Consider asserting the negative: a periodic run that proves the harness can invoke a model
   at all, so branch 1's green is backed by something.
4. Separately, split derived from authored paths in the trigger closures.

**Related.** `KI-TQ-010` (nothing asks whether a passing test is *able* to fail — this is that
question asked of a whole CI gate). The `CLAUDE.md` "Pre-Drive Checklist" already records three
instances of the same shape: the `feedback_categories.yaml` path that reported missing on every
worktree, the AC-store validator's bare-directory glob that exited 0 having checked zero files,
and the stale `origin/main` ref that made a merge audit agree with itself. This is the fourth
and the most complete: the other three examined the wrong thing, whereas this one has never
examined anything.

**Pattern:** a check that examined nothing must not look like a check that found nothing — and
when it cannot examine anything, it must not emit a number that looks like a measurement.

---
