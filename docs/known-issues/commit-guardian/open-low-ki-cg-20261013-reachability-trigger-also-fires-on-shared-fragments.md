---
title: "KI-CG-20261013-reachability-trigger-also-fires-on-shared-fragments — check-reachability's registered files pattern `templates/workflows-js/.*\\.js` matches build-inlined `_shared/` fragments at any depth, so once the automation-script set is derived from that scope a fragment will be read as a standalone automation script"
description: "low — latent. On main no file sits below templates/workflows-js/, and in precommit mode the hook checks nothing until BO-2900c-4 derives the automation set. The BO-4300 epic adds templates/workflows-js/_shared/workspace-answer.js, a fragment the build copies between empty marker pairs in each workflow. The epic narrowed check-workflow-meta to direct children (its ticket 16) and left check-reachability's pattern alone. In source, the commands live only in the fragment, so a derivation must handle fragments explicitly either way."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-13'
components:
  - commit_guardian
  - build_orchestration
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900c-4.yaml
---

# KI-CG-20261013-reachability-trigger-also-fires-on-shared-fragments — one hook was narrowed for `_shared/`, the other was not

> Filed 2026-10-13 from the BO-4300 drive. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`).

- **Severity:** low. Latent: nothing misbehaves today. It becomes a wrong verdict only when BO-2900c-4
  lands and the branch with `_shared/` fragments is on main.
- **Status:** open, no AC. Pattern verified on `origin/main` `964f23a60`. Fragment and narrowing are
  **latent on main; live when the branch lands** (`epic/every-piece-of-separate-work-gets-its-workspace`, tip `cc3c85edc`).
- **Occurrences:** 0 observed failures. Found while narrowing `check-workflow-meta` on the epic.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:**
  - `templates/scripts/commit_guardian/commit_guardian.json:1246` (main): `check-reachability`
    `"files": "^(scripts/build_orchestration/.*\\.py|templates/workflows-js/.*\\.js)$"`, with
    `pass_filenames: false`. On the epic branch the same entry is at `:1273`, unchanged.
  - `templates/scripts/commit_guardian/check_reachability.py:362-370`: with no `--automation`
    supplied, it prints "nothing to check this run" and exits 0. The registered entry supplies none.
  - Epic branch: `templates/workflows-js/_shared/workspace-answer.js` and `_shared/README.md` (the
    fragment, copied by `scripts/build_phases_workflows.py` between `// WORKSPACE-ANSWER-START` /
    `-END` markers, e.g. `build-feature.js:1556-1557`). `check-workflow-meta` narrowed to
    `^templates/workflows-js/[^/]+\\.js$` (`commit_guardian.json:1085`, commit `4af1bd65d`, ticket 16).

## What is true today

- The pattern only decides when the hook fires. The hook reads no file list. So on the epic, a commit
  that touches only `_shared/workspace-answer.js` fires `check-reachability`, which prints its
  BO-2900c-4 "nothing to check" note and passes.
- `check-workflow-meta` had the same `.*\.js` scope. It refused ticket 10's commit on the fragment ("no
  `export const meta` block found"), which is why ticket 16 narrowed it. `check-reachability` passed the
  same commit only because it checks nothing yet.

## Why it will matter (inferred)

BO-2900c-4 asks that "the set of scripts checked is the set of automation scripts that exist at the time
of the check". The hook's exemption ground (`commit_guardian.json:1986-1987`,
`hook_trigger_reachability_exemption_registry`) describes the automation side as
`templates/workflows-js/*.js`. If the derivation
reuses the `files` scope, a `_shared/` fragment becomes an "automation script". If it uses the shallow
workflow glob, it misses commands that, in source, exist only in the fragment: the workflow templates
hold empty marker pairs and get the fragment's text only at build time. Neither reading is right
without an explicit rule for fragments.

## Detection

`git ls-files 'templates/workflows-js/*/**'` returns anything, and `check-reachability`'s `files` pattern
still ends in `.*\.js`. After BO-2900c-4, also look for a reachability finding that names a
`_shared/` file, or a capability reported uncalled while its only caller is a fragment.

## Fix direction

- Narrow the trigger to direct children, as ticket 16 did for `check-workflow-meta`, or name `_shared/`
  explicitly if fragment edits should re-run the check.
- Give BO-2900c-4 an explicit fragment rule. Scan the built, inlined workflow bodies, or attribute a
  fragment's invocations to every workflow that includes its marker pair. Add a case to its fixtures: an
  invocation that exists only in a fragment.
- Better: derive both hooks' scope from one declaration of "what is a workflow script", so the two cannot
  drift apart again.

**Pattern:** two hooks registered on the same tree with copy-pasted scope, and a fix applied to one.
