---
title: "KI-CG-20261009-required-ci-ruff-has-no-local-pre-commit-counterpart — the required Lint (ruff) CI check has never had a matching pre-commit hook, so a lint violation passes every local commit-time gate and fails only in CI"
description: "high — .github/workflows/ci.yml runs `ruff check scripts tests unit_tests kernel` as the required Lint (ruff) job. The generated pre-commit config and its source, the hooks_manifest in templates/scripts/commit_guardian/commit_guardian.json, contain no ruff hook, and git history shows none ever existed. The only local ruff is a Claude Code PostToolUse hook limited to E722/BLE001/TRY. PR #1058 pushed two E741 violations that every local gate passed and CI rejected. Three in-repo texts (a hook's own message, a manifest comment, and a commit message) assert a pre-commit ruff hook that does not exist."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/build-orchestration/BO-500-computed-quality-gates/BO-570.yaml
  - docs/acceptance-criteria/build-orchestration/BO-500-computed-quality-gates/BO-570-4.yaml
---

# KI-CG-20261009-required-ci-ruff-has-no-local-pre-commit-counterpart — the required `Lint (ruff)` CI check has never had a matching pre-commit hook, so a lint violation passes every local commit-time gate and fails only in CI

- **Severity:** high. `Lint (ruff)` is one of `main`'s required checks. A violation it catches
  can always be committed and pushed locally, and nothing local says so. Each instance costs a
  red PR and a fix-up commit, and a reader of the local hook output has every reason to believe
  ruff already ran (see "Texts that claim a hook exists").
- **Status:** open, no AC of its own. The nearest ACs are `BO-570` ("Render and lint defects are
  caught locally at sign-off, before the PR or CI") and its children `BO-570-3`, `BO-570-4`,
  `BO-570-4-i` and `BO-570-4-ii` (a repo-ruff runner and a python sign-off gate). All are
  `readiness: approved` and `work_status: todo`. Those specify a **sign-off** gate in the build
  pipeline, not a pre-commit hook, so even built they would not cover a hand commit.
- **Occurrences:** 1 recorded here (PR #1058, 2026-10-08). The 2026-07-06
  EPIC-WorktreeQualityGateGuard retrospective, quoted in the root CLAUDE.md Pre-Drive Checklist,
  describes the same escape for `F401`/`F841`.
- **First seen:** 2026-07-06 (retrospective) · **Last seen:** 2026-10-08
- **Where:** CI side, `.github/workflows/ci.yml:168-183` (job `lint`, name `Lint (ruff)`, step
  `ruff check scripts tests unit_tests kernel`), configured by `ruff.toml`
  (`select = ["E", "F", "E722"]`). Local side: the generated `.leafcutter/pre-commit-config.yaml`,
  produced by `scripts/build_precommit.py:298-357` from
  `templates/scripts/commit_guardian/commit_guardian.json` → `hooks_manifest.hooks`.

## Re-verification (2026-10-09, worktree at origin/main `5caa16ca`)

- `grep -ci ruff .leafcutter/pre-commit-config.yaml` returned **0**. The deployed config (the
  worktree's `.pre-commit-config.yaml` is a symlink to it) has no ruff hook.
- `git grep -n -i ruff` over `templates/scripts/commit_guardian/` and `.pre-commit-config.yaml`:
  in `commit_guardian.json` the only hits are `.ruff_cache` in an exclusion list (`:176`) and the
  `exception_handling` section (`:1477-1482`). That section's `_comment` reads "Ruff rules E722,
  BLE001, and TRY are also enforced via pyproject.toml [tool.ruff.lint] select", and it carries a
  `ruff_rules` list. The other hits are comments in hook scripts. No hook entry invokes ruff.
- `git ls-files "*pre-commit-config*"` returns no config file. The pre-commit config is
  generated, so the "template" whose history matters is the `hooks_manifest` in
  `commit_guardian.json`.

## Did a local ruff hook ever exist? No. It never existed.

- `git log --all -S "ruff check"` restricted to `*commit_guardian.json`, `*pre-commit-config*`,
  `*.pre-commit-hooks.yaml`, `*.yaml` and `*.yml` returns three commits: `ece619a09` (2026-06-17,
  "ci: add ruff lint gate", which touched `ci.yml`, `ruff.toml` and lint fixes, no hook file),
  `928691b98` (2026-06-24, the BO-570 AC and ticket YAML), and `b9e490682` (adds `kernel` to the
  CI lint). None adds a pre-commit hook.
- `git log --all -G "id: ruff|ruff-pre-commit|astral-sh/ruff|\"id\": \"ruff"` returns **nothing**.
  No hook entry for ruff, local or from the upstream `ruff-pre-commit` repo, has ever been added
  to any tracked file.
- `git log -S ruff` on the two manifest paths (`templates/scripts/commit_guardian/commit_guardian.json`
  and the retired `templates/commit-guardian/commit_guardian.json`) returns five commits. The
  initial commit `11dbd26b7` contains only `.ruff_cache`. `bab5de389` added the
  `exception_handling` section. `275a4828c`, `2c2aa2283` and `21d341e38` are a whole-file
  deletion, its restore, and the retirement of the duplicate tree.

So CLAUDE.md's phrase "the (unestablished) worktree ruff hook" describes an expectation, not a
removed hook. There has never been one to establish.

## The PR #1058 instance

`unit_tests/commit_guardian/test_ge_118e.py` reached the PR with `E741 ambiguous variable name
\`l\`` at two sites. In the parent of `4b9894b40`, the comprehensions use `l` in
`any(l.startswith("Unsupported entry") ...)` and `[l for l in ... .splitlines() ...]`. The fix
commit `4b9894b40` ("make the GE-118e tests pass CI's ruff and mypy") says CI failed the required
`Lint (ruff)` check on exactly these two sites and renamed them to `line`. E741 falls within
`ruff.toml`'s `select = ["E", ...]`.

## Texts that claim a hook exists

Three texts in the repository assert a local ruff gate that does not exist. Each makes the gap
harder to see:

1. `templates/hooks/check_exception_handling_hook.py:263-265`. Its ruff-not-found message says
   violations "will still be caught at commit time by the pre-commit ruff hook."
2. `templates/scripts/commit_guardian/commit_guardian.json:1477`. The comment says the rules are
   "enforced via pyproject.toml". This repository has no `pyproject.toml` (`git ls-files` finds
   only `ruff.toml`). The sibling `ruff_rules` key is read by nothing: `git grep -l ruff_rules`
   over `scripts templates unit_tests tests` returns only this file.
3. The fix commit `4b9894b40` itself: "the commit that introduced E741 passed the local
   pre-commit ruff hook. Local and CI ruff disagree on these test files." **Inferred:** the ruff
   that ran locally was the Claude Code **PostToolUse** hook `check_exception_handling_hook.py`
   (registered in `templates/settings.json` under `PostToolUse`, matcher `Edit|Write`). It runs
   `ruff check --select E722,BLE001,TRY` on each edited file (`RUFF_SELECT`, `:49`), and that
   rule set cannot report E741. It is an edit-time hook for agent sessions, not a pre-commit
   hook. It does not run on a human's commit, and it does not use `ruff.toml`'s rule set.

`scripts/run_ci_local.py:64` runs `ruff check scripts tests unit_tests` (without `kernel`) as a
manual, optional mirror of CI. It is not a hook, and its tree list has drifted from CI's.

## Detection

```bash
ruff check scripts tests unit_tests kernel
```

Run it from the repository root before pushing. A non-empty result that the commit did not
report is this gap.

## Workaround

Run the command above before every push, as the root CLAUDE.md "Full test suite + ruff at
epic-finalize" checklist item already instructs (with the older three-tree list).

## Fix direction

Add a ruff entry to `hooks_manifest.hooks` in `templates/scripts/commit_guardian/commit_guardian.json`
that runs `ruff check` over the **same four trees** (`scripts tests unit_tests kernel`) with the
**same configuration** (`ruff.toml`, no `--select` override), so local and CI ruff cannot
disagree. A shared definition is better than two hand-kept copies: either CI invokes the same
hook (`pre-commit run ruff --all-files`) or both read the tree list from one place. Consider
the kernel's extra `--select E722,BLE001,TRY` step (`ci.yml:185-188`) at the same time. Then
correct the three texts above: the hook message, the manifest comment and its unread
`ruff_rules` key, and `run_ci_local.py`'s tree list.

**Pattern:** a required remote gate with no local counterpart, plus local text saying the
counterpart exists. The only place the gate runs is after the push.
