---
title: "The harvester's --state default is relative to the working directory and can break every build"
date: "2026-10-08"
time: "17:00"
type: manual
components: 
  - knowledge_management
  - build_pipeline
summary: "A new known-issue entry records a latent build-breaker: the knowledge harvester's --state default resolves against the working directory, so a run without the flag can leave a gitignored file in the package root, and the build's closure guard then refuses every later build. Documentation only."
description: "One content commit (53025616f), documentation only. Files KI-KM-20261008-harvest-state-default-is-cwd-relative (open, high, latent) under docs/known-issues/knowledge-management/ and adds it to that component's index. scripts/knowledge/harvest_cli.py defaults --state to Path(\"debugging/logs/harvest_state.json\"). Once that file exists under the package root, the BP-900g-8 closure guard treats the literal as an undeployed dependency and build.py exits 1. Reproduced on origin/main fbf0c5223: exit 1 with the file present, exit 0 without it. The entry covers why this depends on test order, the PR #877 --marker precedent (merge 3f31757f), the near-miss test helpers and the four non-test invocation sites that omit --state, and the fix direction."
commits: 
  - 53025616f
breaking: false
---

## Entry

New known issue **KI-KM-20261008-harvest-state-default-is-cwd-relative**, filed under
`knowledge-management` because the fix belongs in the harvester.

`scripts/knowledge/harvest_cli.py` defaults `--state` to
`Path("debugging/logs/harvest_state.json")`, which resolves against the working directory. If a
harvester run that routes an event leaves that file under the package root, `build.py`'s
closure guard (AC BP-900g-8) aborts every later build with
`[CLOSURE GUARD] UNDEPLOYED DEPENDENCY`. PR #877 hit the same trap with `--marker`. That was
fixed in merge `3f31757f`; `--state` has the same problem but nothing has triggered it yet.

- Reproduced on origin/main `fbf0c5223`: exit 1 with the file present, exit 0 without it.
- No test on main triggers it today. Three test helpers are one edit away from doing so, and
  the entry names them. The knowledge-routing step in three workflows and the
  `knowledge-harvester` agent run without `--state` from the repository root.
- Fix direction: resolve the default against the deployed output root, and have tests always
  pass a temporary `--state`.

No code changes.
