---
title: "Main was already breaking one of its own required gates, and nothing could see it"
date: "2026-08-26"
time: "10:58"
type: manual
components:
  - build_pipeline
  - testing_quality
summary: "BP-900e-3 sat on origin/main as an approved code AC with no test contract — the exact state the required `AC store valid` check rejects. It survived because the AC hooks read a commit's index, not the store, and nobody had staged the file. Authoring its test_spec also turned up a criterion that names a script which has never existed."
description: "BP-900e-3 was byte-identical to origin/main while already violating `AC store valid`, one of the six required status checks. The record is readiness: approved, work_status: not_started, assigned_agent: python-coder — which makes it a leaf code AC under check_ac_schema's validate_test_contract regardless of its change_target: pipeline, since _is_code_ac treats a coder assignment as sufficient on its own. It carried no test_spec and no test_required: false. Reproduced directly: the gate exits 1 on the pre-change record with 'approved code AC must declare a test contract', and exits 0 on the enriched one. WHY IT SURVIVED. The hook derives its file set from `git diff --cached --name-only --diff-filter=AM`, so it only ever sees files a commit actually stages. A record can therefore be invalid on disk indefinitely and no commit will notice, because no commit touches it. This is the same structural blind spot CLAUDE.md's 'stage the parent alongside the child' rule describes, seen from the other side: the hook's silence is not a pass, it means the hook was never handed the file. PR #495 touched BP-900e-3 incidentally to add a doc_links cross-reference, which staged it for the first time and turned a latent violation into a red check. WHAT WAS AUTHORED. Five test descriptors, deliberately not five restatements of the Gherkin. BP-900e-3 is a pure no-false-positive AC — every Then clause is a negative assertion that some script is never flagged — and a registry-completeness check that returns an empty verdict unconditionally satisfies all of them. So the contract is anchored on a positive control sharing one fixture with the negative cases: a genuinely promised-but-undeployed script must still make the verdict ok=false. Without it the other four descriptors are green against a check that does nothing. The remaining four are charged across the set-cover angles: real_artifact (feed the actual on-disk commit_guardian.json and templates/ tree, because build.py is a live unregistered, unreferenced, template-less script that a wrong implementation flags today); criterion (a never-before-seen script name, which a hard-coded exemption list cannot satisfy — only a promised-set-first derivation can); seam (set equality on the candidate set against both promise sources computed independently, catching both a superset from tree enumeration and a silently dropped source); and reachability (run the production entry point in a subprocess and assert exit 0, since a helper-level filter the CLI re-derives around leaves the merge blocked while every direct-import test stays green). AN AMBIGUITY WORTH RECORDING. The criteria name scripts/epic_lock.py as one of two source-only scripts, and an existing it_requirement instructs that a regression test pin it out of the verdict. That path does not exist in this repository and never has — no addition commit for it on any ref. A test asserting a non-existent script stays out of a list passes vacuously, so following that instruction would have produced a fabricated green. The criteria were left untouched, as they are the BA's and are approved; the correction is recorded as a new it_requirement pointing the pin at build.py, which is real. Three it_requirements were added in total: that correction, the negative-control obligation, and a constraint that the exemption derive from the data rather than a script name so an unseen script inherits it with no code change."
breaking: false
---

## Entry

`BP-900e-3` was byte-identical to `origin/main` and already failing `AC store valid` — one of the six required checks. Nothing had noticed.

**The state.** `readiness: approved`, `work_status: not_started`, `assigned_agent: python-coder`, no `test_spec`, no `test_required: false`. Its `change_target` is `pipeline`, not `code`, but that does not save it: `_is_code_ac` returns true on a coder assignment alone. Reproduced both directions —

```
# pre-change record
[check-ac-schema]: approved code AC must declare a test contract …   exit: 1
# enriched record
                                                                      exit: 0
```

**Why it survived.** The hook takes its file set from `git diff --cached --diff-filter=AM`. It sees what a commit stages, never the store. So a record can be invalid on disk forever provided no commit touches it — the same blind spot as the "stage the parent alongside the child" rule, viewed from the other side. Hook silence is not a pass; it means the hook was never given the file. PR #495 staged this record incidentally and made the latent violation visible.

**The contract.** Every `Then` clause here is a *negative* — "X is never flagged". A check that flags nothing satisfies all of them. So the five descriptors are anchored on a **positive control** sharing a fixture with the negative cases: one genuinely promised-but-undeployed script must still produce `ok=false`. Without it, the rest are green against a no-op.

| angle | what it would catch |
|---|---|
| `real_artifact` | `build.py` flagged against the **real** registry + `templates/` tree — it is live, unregistered, unreferenced, template-less |
| `criterion` | a never-before-seen script name — defeats a hard-coded exemption list |
| `seam` | candidate set ≠ registry ∪ template-refs, in either direction |
| `reachability` | filter correct in a helper, re-derived at the entry point the gate calls |
| `failure` | the positive control — proves the exclusion narrows the verdict rather than emptying it |

**An ambiguity worth recording.** The criteria name `scripts/epic_lock.py`, and an existing `it_requirement` says to pin a regression test on it. **That path has never existed in this repository** — no addition commit on any ref. Asserting a non-existent script stays out of a list passes vacuously. Following the instruction as written would have produced exactly the fabricated green this store exists to prevent.

The `criteria` field was left untouched — it is the BA's and it is approved. The correction is recorded as a new `it_requirement` redirecting the pin to `build.py`, which is real.
