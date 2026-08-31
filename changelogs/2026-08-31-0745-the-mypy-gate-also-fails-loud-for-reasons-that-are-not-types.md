---
title: The mypy gate also fails loud for reasons that are not types
date: "2026-08-31"
time: "07:45"
type: manual
components: 
  - build_pipeline
summary: "Addendum to KI-BP-20260831-0620: the same job also aborts with exit 128 when the base branch moves, because a --depth=1 fetch feeds a three-dot diff that needs a merge base."
description: "Observed on PR #634. The step fetches the base with --depth=1 and then computes git diff origin/BASE...HEAD, which requires the merge base. When the base moves between checkout and fetch - another PR merging minutes earlier, logged as a forced update - the diff aborts before mypy runs. So the job has two independent ways of telling you nothing: fail-open via the pathspec bug, and fail-loud via this. The second is why the first survived: a check that reddens for reasons unrelated to its subject stops being read, and then its greens are not read either."
---

## Entry

`KI-BP-20260831-0620` recorded that the mypy job's pathspec selects no file directly in
`scripts/`, so it can report SUCCESS having checked nothing. Within the hour the same job
failed on the next PR — and not on a type error:

```text
+ f0d22094...9ad2aec2 main       -> origin/main  (forced update)
fatal: origin/main...HEAD: no merge base
##[error]Process completed with exit code 128.
```

The step fetches the base with `--depth=1` and then computes `git diff origin/$BASE...HEAD`.
The three-dot form needs the merge base. A shallow fetch does not reliably make it reachable,
and when the base branch has moved since checkout — here because another PR merged minutes
earlier, which git logs as a *forced update* — the diff aborts before mypy is invoked at all.

So the job has two independent ways of telling you nothing:

| | pathspec | shallow fetch |
|---|---|---|
| Direction | fails **open** — SUCCESS having checked nothing | fails **loud** — exit 128 |
| Trigger | a PR touching only a top-level `scripts/` file | base branch moves between checkout and fetch |
| Reader sees | a green check | a red check that is not about types |

**The second is why the first survived.** A check that goes red for reasons unrelated to its
subject trains everyone to discount it, and a discounted check's *greens* stop being read
carefully too. The pathspec bug needed exactly that inattention to last as long as it did.
Fixing one without the other leaves the signal untrustworthy in the opposite direction.

The fix is to drop `--depth=1` — the checkout already uses `fetch-depth: 0`, so the shallow
fetch buys nothing and costs the merge base. Switching to two-dot `origin/$BASE..HEAD` also
works but changes which commits are considered, and the intent here is genuinely "what this PR
adds relative to the fork point".

Worth noting where this surfaced: merging the PR that *filed* the original KI is what moved
`main` and broke the next PR's run of the same job. That makes the failure likeliest exactly
when PRs are being merged in sequence — which is when CI signal is being leaned on most.
