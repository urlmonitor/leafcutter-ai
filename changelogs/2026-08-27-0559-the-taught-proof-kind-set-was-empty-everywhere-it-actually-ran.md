---
title: "The taught proof-kind set was empty everywhere it actually ran"
date: "2026-08-27"
time: "05:59"
type: manual
components:
  - build_pipeline
  - testing_quality
summary: "BP-1100g-3 resolved its schema with a hand-counted parent depth that is only correct in the source tree. From the deployed copy — the one the commit-time and merge-time checks run — it loaded zero taught kinds and reported every correctly-tagged test as a violation. Fixed in two parts, and the tests were falsified before being trusted."
description: "BP-1100g-3-ii. done_proof.py resolved config/ac_store_schema.json as Path(__file__).resolve().parent.parent.parent. The distance from the module to the repository root is NOT the same in the two layouts it runs in: <repo>/scripts/ac_store/ is parents[2], <repo>/.leafcutter/scripts/ac_store/ is parents[3]. So the deployed copy resolved to .leafcutter/config/ac_store_schema.json, which is not there; _load_permitted_angle_kinds fail-softs to an empty set on a read failure; and an empty permitted set makes EVERY declared kind unrecognised. Measured against 2f740cc4: source tree returned all seven kinds and accepted a valid criterion tag, deployed copy returned zero and reported that same valid tag as a violation. A 100% false-positive rate in the layout that matters, and the third Then clause of BP-1100g-3 -- an unrecognised kind is reported, naming the test and the value -- was therefore true in the source tree and false in the installed one. WHY BP-1100g-3'S OWN REACHABILITY TEST MISSED IT: that test exercised collect_test_tag_records through the deployed copy and passed; the sibling function added in the same commit reads a different file by a different path and was never reached from that layout. The angle was right and the coverage was partial -- one function proven reachable, one assumed. THE FIX IS TWO PARTS AND ONE ALONE IS NOT ENOUGH. First, the module resolves the schema by an upward search for the directory that actually holds it, never by a fixed parent count, because no integer is correct in both layouts; it falls back to the old candidate when nothing is found so the caller's existing cannot-read branch reports a real path rather than inventing a plausible one. Second, build_phases.py deploys config/ac_store_schema.json alongside the deployed scripts, because the upward search alone is NOT sufficient in the self-hosting workspace: there .leafcutter/ sits BESIDE leafcutter-ai/ rather than inside it, so no ancestor of the deployed module holds the package's own config/. That second gap was caught by checking the workspace layout rather than assuming the worktree shape generalised -- the first version of this fix passed in a worktree and would still have been broken in the install tree. Additionally find_unrecognised_angle_tags now treats an empty permitted set as could-not-check and reports nothing, loudly, instead of reporting everything: turning one unreadable file into a report against every tagged test in the repository is indistinguishable from the check being broken, and the reasonable response to that is to switch it off. Deliberately fail-soft, which is safe here and only here because this output is advisory and feeds no verdict (the BP-1100g-3-i boundary, whose tests remain green). THE TESTS WERE FALSIFIED BEFORE BEING TRUSTED, AND THE FIRST VERSION FAILED THAT CHECK: the initial fixtures deployed the schema to .leafcutter/config/, which is exactly where the BROKEN code looks, so 3 of the 4 tests passed against the unfixed module and proved nothing. Caught by running them against it rather than by reading them. The fixtures now use the layout that discriminates. AC BP-1100g-3-ii authored for the defect and marked done with its test contract; BP-1100g-3's covered_by extended to include it, staged together per the AC-store parent rule."
breaking: false
---

## Entry

`BP-1100g-3` taught the system to read a set of proof kinds from one authoritative file. It read that file by counting parent directories — and the count is only right in one of the two places the module runs.

```
<repo>/scripts/ac_store/done_proof.py               root is parents[2]
<repo>/.leafcutter/scripts/ac_store/done_proof.py   root is parents[3]
```

Measured, not inferred:

| layout | taught kinds | a **valid** `criterion` tag |
|---|---|---|
| source tree | all 7 | accepted |
| **deployed** | **0** | **reported as a violation** |

The deployed copy is the one the commit-time hook and the CI gate run. So the clause *"an unrecognised kind is reported, naming the test and the value"* was true where nobody runs it and false where everybody does.

**Why the reachability test didn't catch it.** It exercised `collect_test_tag_records` through the deployed copy and passed. The sibling function added in the same commit reads a *different* file by a *different* path. One function proven reachable, one assumed.

**Two parts, and one alone is not enough.** The module now searches upward for the directory that actually holds the schema — no fixed count is right in both layouts. But the upward search alone is still broken in the self-hosting workspace, where `.leafcutter/` sits *beside* the package rather than inside it, so no ancestor holds `config/` at all. The build now deploys the schema alongside the scripts. My first attempt had only the search, passed in a worktree, and would have shipped broken to the install tree.

**An unreadable file is no longer "nothing is taught".** That equivalence is what turned one missing file into a report against every tagged test in the repo — and a check that fires on everything gets switched off. It now reports nothing and says loudly why.

**The tests were falsified, and the first version failed.** The initial fixtures deployed the schema to `.leafcutter/config/` — precisely where the broken code looks — so three of four passed against the unfixed module. Running them against it is the only reason that was found. Against the pre-fix module now: `deployed` subfails on the discriminating layout, `real_artifact` fails, `boundary` fails, and `failure` correctly passes because it guards against over-fixing to "report nothing".
