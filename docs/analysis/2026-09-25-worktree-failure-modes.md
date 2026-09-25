---
title: "Worktree failure modes F1–F14, each tied to evidence"
description: "The fourteen ways worktree creation, reuse, bootstrap and removal fail today in the leafcutter-ai package, each tied to the incident trace, a known issue or a sandbox run. Part of the worktree-consolidation analysis."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - worktree_manager
  - build_orchestration
---

# Worktree failure modes F1–F14, each tied to evidence

Part of [the worktree-consolidation analysis](2026-09-25-worktree-creation-consolidation.md). The decisions taken on 2026-09-25
(per-feature clones, real install files, `origin/main` everywhere, one script run from a skill)
are in section 8 of that page and in [the decision memo](2026-09-25-worktree-isolation-decision-memo.md);
where they change what is written here, they win.

## 4. Failure modes, with evidence

**F1 — Shell steps are sent to an agent that refuses them.**

- plan-feature sends its resolver, branch check, orphan scan, committed-stage scan and
  pause-store steps to status-checker (`plan-feature.js:2291`, `:2448`, `:613`, `:835`,
  `:1858`, `:1879`).
- build-feature sends `worktree_repo_facts` there too (`build-feature.js:1410`).
- finalize sends `git worktree add/remove --force` and `rm -rf` there (`finalize-feature.js:634-660`, `:1299-1340`).
- status-checker's registry entry is `permits_shell: false` (`config/agent_registry.json:1300`),
  and its charter limits it to ticket-state questions (`templates/agents/status-checker.md:1-16`, `:204-206`).
- Evidence: today's journal lines 5, 19 and 21; KI-BO-020.

**F2 — "Not a worktree" is a valid state rather than an error.**

- plan-feature: a null `authoringWorktreePath` runs everything bare (section 1, step 5).
  KI-ACD-007 shows the product-truth phase writing into the main checkout even when a
  worktree *was* created (`docs/known-issues/ac-driven-dev/open-high-ki-acd-007.md:29-45`).
- build-epic falls back to the epic folder (`build-epic.js:345-347`).
- finalize falls back to `"unknown"` (`finalize-feature.js:541-548`).
- fast-lane-ship falls back to the path the model claimed (`fast-lane-ship.js:841`).
- Evidence: today's run; KI-BO-027 (the epic folder returned as the worktree path);
  KI-BO-20260921 "abandons the epic worktree branch", where phase agents wrote into the main
  checkout
  (`docs/known-issues/build-orchestration/open-blocker-ki-bo-20260921-build-feature-abandons-the-epic-worktree-branch.md:45-75`).

**F3 — Results depend on the working directory.**

- Bare `git` in plan-feature from the workspace parent gives exit 128 (today, journal lines 3, 9, 11).
- `worktree_repo_facts.py base` with no argument returns
  `{"main_checkout": null, "worktree_base": null, "layout": null}` from the workspace parent,
  but the right answer from inside `leafcutter-ai` or from inside a worktree. Reproduced
  today from all three directories; this is KI-BO-20260921-worktree-base-resolver-defaults-to-cwd.
- `SCRIPT._worktree_exists` and `_create_worktree` run git without `-C` and depend on an
  earlier `os.chdir` (`SCRIPT:383-388`, `:479-492`).
- Related guard false results: KI-CG-20260901, and `CLAUDE.md:756-765`.

**F4 — Stdout is not a clean JSON channel.**

- A sandbox run of the current template (`create-ac-worktree probe1`, see Method) printed on stdout:
  ```
  branch 'ac-authoring/probe1' set up to track 'origin/main'.
  HEAD is now at bc5d638 init
  ```
  before any JSON.
- `_create_ac_worktree` and `_create_fastlane_worktree` do not capture git's output
  (`SCRIPT:582-620`, `:1238-1279`), unlike `_create_worktree`, whose comment documents exactly
  this hazard (`SCRIPT:474-478`).
- `_bootstrap` lets `git submodule`, pip/poetry and `build.py` write to stdout (`SCRIPT:1497-1553`).
- KI-ACD-004 recorded this pollution and fixed it for `create-only` only
  (`resolved-blocker-ki-acd-004.md:147-155`).
- Whether a caller parses the result then depends on whether an LLM picks the right line.
  plan-feature parses the whole trimmed output (`plan-feature.js:2504`). The fast lane has twice
  seen worktree-agent echo a made-up path (`fast-lane-ship.js:767-777`).

**F5 — A half-made worktree is later reported as healthy.**

- On Windows without Developer Mode, the sandbox run created the worktree and branch, then
  failed bootstrap with `BOOTSTRAP ERROR: AC-5 …` and exit 1. The cause was WinError 1314 on
  both symlinks, with no root `.pre-commit-config.yaml` to copy.
- **Re-running the same command returned exit 0 with `"created": false`**, on a worktree
  containing only `.git`, `.gitignore` and `a.txt`. The reuse path skips bootstrap entirely
  (`SCRIPT:1941-1951`, `:1785-1792`, `:2034-2036`).
- Related: KI-BO-20260831-1331, a half-created fast-lane worktree with 3,695 empty YAML files
  that git does not list (`…/open-high-ki-bo-20260831-1331.md:30-50`).

**F6 — Bootstrap failure is swallowed.**

- `build.py` failing inside `_bootstrap` only warns (`SCRIPT:1554-1560`).
- KI-BP-20260907-bootstrap-swallows-build-failure: a fast-lane worktree was missing
  `build_orchestration/`, and the run died four steps later
  (`…/open-high-ki-bp-20260907-bootstrap-swallows-build-failure.md:41-62`).

**F7 — The "hooks are active" check passes when they are not.**

- The AC-5 probe accepts a `.leafcutter` symlink alone (`SCRIPT:1579`). `pre-commit` only
  reads `.pre-commit-config.yaml` at the worktree root.
- KI-BP-20260826-worktree-hooks-only-on-one-path observed hooks disabled with the symlink
  present, and 51 AC records nearly committed unchecked
  (`…/open-high-ki-bp-20260826-worktree-hooks-only-on-one-path.md:55-100`).
- `CLAUDE.md:556` has the same OR, and so does the probe tool: `verify_precommit_active.py`'s
  `check_b_config` accepts `.leafcutter/pre-commit-config.yaml` in place of the root file
  (`templates/scripts/commit_guardian/verify_precommit_active.py:77-134`).
- `install_pre_commit_shims.find_hooks_dir` reads `<root>/.git/config` as a file. In a worktree
  `.git` is a file, so it falls back to `<worktree>/.git/hooks`, a path that cannot exist
  (`templates/scripts/commit_guardian/install_pre_commit_shims.py:73-83`).
- Every worktree not created through the script (feature epic, `EnterWorktree`,
  build-feature's LLM-made worktree) has no guaranteed hooks at all.

**F8 — The symlink approach makes guards resolve the wrong root.**

- KI-CG-009: `Path(__file__).resolve()` follows `.leafcutter` into the main checkout
  (`…/open-high-ki-cg-009.md:37-60`).
- The allowlist dual-update rule (`CLAUDE.md:575-583`).
- KI-BP-017 / KI-FC-001: feedback lands in the install tree.
- KI-BP-20260826-1331: the shared `.leafcutter/` is a collage of whatever each worktree last wrote.

**F9 — Stale bases.**

- `setup-ticket` and `create-only` branch from local `main`, which is why quick-fix needs its
  own staleness gate (`quick-fix.js:290-300`).
- ac-authoring reuses an existing branch at its old tip (`SCRIPT:578-603`).
- The fast lane had the same bug until it switched to `-B` (KI-BO-017,
  `…/open-high-ki-bo-017.md:30-45`). The code is fixed (`SCRIPT:1238-1262`), but the KI is
  still filed as open.
- finalize adds baseline worktrees from `origin/main` without fetching first (`finalize-feature.js:795`).
- A branch cut minutes ago goes stale before it is pushed (KI-BO-20260909-worktrees-go-stale-within-minutes).
- The scaffold must be on `origin/main` first (`CLAUDE.md:599-633`).

**F10 — Different naming rules make one drive corrupt another.**

- build-feature expects `epic/<kebab>` (`build-feature.js:1427`), the feature skill creates
  `EPIC-<Name>` (`feature/SKILL.md:76`), and `_worktree_exists` recognises neither.
- In KI-BO-20260921-build-feature-abandons-the-epic-worktree-branch, a re-run moved the
  worktree from `EPIC-FilesStayWorkable` to a fresh `epic/files-stay-workable` cut from
  `origin/main`, and drove the epic from the main checkout (`…:24-45`).

**F11 — The deployed copy cannot find the repository.**

- The workspace-level deployment (`<workspace>/.leafcutter/scripts/`) is outside every repository.
- In the sandbox it failed `create-ac-worktree` with
  `Failed to resolve git toplevel from …\.leafcutter\scripts`.
- `create-only` succeeded, via the search fallback.
- KI-ACD-004 is the same failure, first time round
  (`docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-004.md:33-60`). It
  deliberately left the anchor-only lookup in `create-ac-worktree` and
  `create-fastlane-worktree` (`:147-155`). Its fix moved plan-feature to the stale in-repo
  copy rather than making the script resolve correctly.
- The resolvers also disagree on ambiguity: `check_workspace_setup_permission.py` takes the
  **first** child repository it finds (`scripts/worktree/check_workspace_setup_permission.py:148-188`),
  while `SCRIPT` refuses anything other than exactly one (`SCRIPT:267-282`).

**F12 — A worktree-creating agent acts on the wrong instructions.**

- KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation: the fast lane's
  worktree-agent read the user's earlier chat and deleted a remote branch instead of creating
  a worktree (`…:22-50`).
- An LLM in the create path is itself a failure mode.

**F13 — Tests cannot see F1, F4 or F5.**

- `test_acd_2100a_1.py`'s harness executes every dispatched command, so an agent refusing
  its task is never modelled.
- `test_fastlane_template_deploy_parity.py:90-100` *enforces* drift between the two script
  copies.
- The behavioural script tests (`test_acd_2100a_2.py`, `test_bo2400f_3_reconnect_stale_main_behavioral.py`,
  `test_bo2400f_13_occupied_workspace_refusal.py`, `test_ge_120e_1.py`) run real git in
  temporary repositories. But none of them runs from a workspace parent or from inside another
  worktree, none simulates a symlink being denied, and none asserts that stdout is exactly one
  JSON object.
- `tests/test_setup_ticket_worktree.py` has 41 mock sites.
- Most behavioural fast-lane tests exercise the **tracked `scripts/` copy**, not the template
  that is actually deployed (`unit_tests/build_orchestration/_bo2400f13_fixtures.py:54`, which
  labels it `DEPLOYED_SCRIPT`; `test_bo2400f_3_reconnect_stale_main_behavioral.py:67-80`).
- No test runs the template's `create-ac-worktree` or `create-fastlane-worktree` against a
  real repository.
- Windows symlink denial is covered only by a mocked `OSError(1314)`
  (`tests/test_setup_ticket_worktree.py:188-198`).

**F14 — Tests leak worktrees into the real repository.**

- `git worktree list` in `leafcutter-ai` includes
  a worktree under the user's pytest temp directory
  (`%TEMP%/pytest-of-<user>/pytest-<n>/layouts0/worktree-<id>/leafcutter-ai`).
- KI-TQ-012 is the sibling defect: fixture identity was written into the real repository's config.
