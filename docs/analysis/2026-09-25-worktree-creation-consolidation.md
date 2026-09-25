---
title: "Worktrees are made by seven different recipes, and the one that failed today treats \"no worktree\" as a normal outcome"
description: "Inventory of every place the leafcutter-ai package creates, reuses, locates, bootstraps or removes a git worktree; a trace of the 2026-09-25 /plan-feature run that wrote ACs onto main; the ways the paths diverge and fail; and a proposed single standalone worktree component with a CLI/JSON contract, a migration order and a behavioural test matrix."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - worktree_manager
  - build_orchestration
  - ac_driven_dev
  - build_pipeline
  - commit_guardian
---

# Worktrees are made by seven different recipes, and the one that failed today treats "no worktree" as a normal outcome

The goal, in the user's words: *"I only want to have ONE script that creates worktrees and
works 100% of times — no matter in which workflow or skill we use it. It should really be a
standalone component we can use."*

This page covers what exists today, why today's `/plan-feature` run ended up writing
acceptance criteria straight onto `main`, and what a single component would have to own for
that goal to hold.

**Verdict.** There is no single worktree component today. There are seven recipes spread
over two Python scripts, four sandboxed workflows, four agent or skill prompts and one how-to:

1. `setup_ticket_worktree.py`, with four subcommands that disagree with each other.
2. `worktree_repo_facts.py` plus an LLM that runs `git worktree add` itself.
3. The `feature` skill's hand-written epic recipe.
4. `finalize-feature`'s temporary baseline worktrees.
5. `EnterWorktree` in the manual-drive how-to.
6. The CLAUDE.md manual bootstrap recipe.
7. `git_recovery.py`'s poisoned-worktree fallback.

They disagree on how to find the repository, which base to branch from, what to name the
branch, where the worktree goes, how to bootstrap it, and what counts as failure.

Today's incident was not a git problem. The `setup_ticket_worktree.py create-ac-worktree`
command was never run. An agent refused a shell step outside its charter. The workflow then
sent the *path-resolution* command in place of the *create* command. That returned exit 0.
The workflow reads "exit 0 with unparseable output" as "no worktree, use the current
checkout", so it carried on.

The fix is not another guard in `plan-feature.js`. It is one deterministic script:

- It emits exactly one JSON object with an explicit status.
- It verifies its own result.
- It works from any directory.
- Callers are forbidden to continue on anything but `status: "ok"`.

**Decided 2026-09-25 (see section 8):** the script creates per-feature **clones**, not
worktrees. Every clone gets real install files and no symlink, and branches from `origin/main`.
Agents run the script from a skill. The measured reasoning is in
[the decision memo](2026-09-25-worktree-isolation-decision-memo.md).

## 1. Case study — the 2026-09-25 `/plan-feature` run

**Source:** the workflow journal
`~/.claude/projects/c--Users-Hendrik-Code-leafcutter/95e90780-…/subagents/workflows/wf_f3f4d0e4-86f/journal.jsonl`,
its per-agent transcripts and `*.meta.json` agent types, and
`templates/workflows-js/plan-feature.js`. The deployed `.claude/workflows/plan-feature.js`
differs only in five comment lines where `{{config.output_root}}` is rendered.

**Setup:** the session's working directory was the workspace parent
`C:\Users\Hendrik\Code\leafcutter`. That folder is not a git repository: its `.git` holds
only an empty `hooks/` directory. Every agent the workflow dispatched inherited that
directory.

| # | Journal line | Step (label → agent type) | What happened | Code that let it through |
|---|---|---|---|---|
| 1 | 2-3 | `detect-current-branch` → status-checker | Bare `git branch --show-current` from the workspace parent: exit 128, "not a git repository". | Swallowed as best-effort (`plan-feature.js:2311-2313`). The variable it sets, `userIsOnMain`, is never read anywhere (`:2285`, `:2302`). |
| 2 | — | Workspace-setup permission pre-flight | Passed: `worktree-agent` has `permits_shell: true` (`config/agent_registry.json:1368`). | The pre-flight checks only the *setup* agent (`:2342-2432`), not the agent that step 3 uses. |
| 3 | 4-5 | `resolve-worktree-setup-script-path` → **status-checker** | Refused: *"out of scope for status-checker … not resolving or executing arbitrary repo-tooling scripts"*. | Hard-coded to status-checker (`:2447-2449`), which the registry marks `permits_shell: false` (`config/agent_registry.json:1300`). The refusal has no `output` field, so it becomes `ok:false` (`:2239-2253`). |
| 4 | 6-7 | `worktree-setup` → worktree-agent | On `ok:false` the workflow sends the **resolution command again** in place of `create-ac-worktree` (`:2458-2461`). worktree-agent ran it; the child-directory probe (`:2066-2071`) found `leafcutter-ai`; it returned exit 0 with the **script's path** as output. | The code comment (`:2451-2457`) assumes the re-issued resolution "fails again for real and deterministically". It only would if the first failure had been a resolution failure. It was a refusal. |
| 5 | — | Result handling | `exit_code` was 0, so no halt (`:2488-2499`). `JSON.parse("/c/…/setup_ticket_worktree.py")` threw and was caught, leaving `wtPayload = null` (`:2501-2509`). `authoringWorktreePath` stayed `null` and `acStoreDir` stayed the relative `"docs/acceptance-criteria"` (`:2434-2435`). | Nothing after this point asserts that a worktree exists. A null path is a supported "current checkout" mode throughout the file, e.g. `:290`, `:602-604`, `:753`. |
| 6 | 8-11 | `scan-orphans-git-status`, `scan-committed-stages` → status-checker | Bare git from the workspace parent: exit 128 both times. | Both read "git failed" as "nothing found" (`:620-623`, `:840-843`). |
| 7 | 12-17 | triage, pt-classify, **stage-po-author** → product-owner | The PO was told *"Write AC YAML files ONLY to docs/acceptance-criteria … Do NOT write AC files to docs/acceptance-criteria/ relative to the current checkout — use the absolute path docs/acceptance-criteria instead"* (`:3096-3098`), which contradicts itself once the path is relative. It wrote `INF-1400*` untracked into `leafcutter-ai/docs/acceptance-criteria/` on `main` (journal line 17, its own `anomalies`). | The only remaining guard is the branch check at commit time (`:296-369`). It would refuse the commit, but only after the files were already in the main checkout. |
| 8 | 18-21 | `pause-persist`, `pause-persist-verify` → status-checker | Refused again, for the same charter reason. | The same agent-selection error, in a second place (`:1858`, `:1879`). |

**Why it failed:** a shell step was sent to an agent whose charter and registry entry say it
does not run shell commands. This has happened before: KI-BO-020 records status-checker
refusing the fast lane's release step, and the lane discarding the refusal
(`docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-020.md:39-55`).

**Why it did not halt:** the create step's only failure signal is a non-zero exit code.
Three other outcomes pass silently:

- exit 0 with non-JSON output;
- a missing `worktree_path`;
- an output that is a file path.

After that, the workflow has a first-class mode that runs without a worktree.

**Even the success path was fragile.** Had resolution worked, it would have run
`leafcutter-ai/.leafcutter/scripts/setup_ticket_worktree.py`. That is a **stale**,
gitignored copy: 2,150 lines, dated 2026-09-09, versus the 2,338-line deployment in
`<workspace>/.leafcutter/scripts/` dated 2026-09-24. The resolver always appends
`$REPO_ROOT/.leafcutter/…` (`:2131`), and in the dev layout the repository root is
`leafcutter-ai`, not the workspace.

Its output would also not have parsed reliably, because `create-ac-worktree` writes git's own
messages to stdout (see F4 in section 4).

## 2. Inventory

**Legend**

- Op: C create · R reuse · L locate · B bootstrap · X remove · V verify.
- Runtime:
  - *WF*: a sandboxed workflow body with no filesystem access, so every shell step is an `agent()` dispatch (ADR-030; `unit_tests/_workflow_engine_harness.py:83-95`).
  - *main*: the main agent loop, running a skill.
  - *sub*: a sub-agent.
- `SCRIPT` = `templates/scripts/setup_ticket_worktree.py`. It is deployed by
  `build_template_standalone_scripts()` (`scripts/build_phases_script_deploy.py:416-488`,
  registered at `scripts/build.py:1522`), a shallow glob of `templates/scripts/*.py`.
  - It lands under the output root, i.e. `<target>/.leafcutter/scripts/` (`scripts/build.py:1548-1550`, `:1931-1932`).
  - The manifest entry is also a glob (`scripts/build_deploy_manifest_helpers.py:241-259`), not a named entry.
  - `leafcutter-ai/.leafcutter/` exists because running `build.py` inside `leafcutter-ai` without `--target-dir` targets the current directory (`scripts/build.py:1878`).

### 2.1 The scripts

| Site | Op | Repo-root resolution | Base / fetch | Branch | Lands at | Bootstrap | Failure signal |
|---|---|---|---|---|---|---|---|
| `SCRIPT setup-ticket` `:1752-1807` | C R B | `_git_toplevel(ticket dir)` (`:1773`), then `_resolve_installed_layout` (`:285-364`), then `os.chdir` | **local `main`**, no fetch (`_create_worktree` `:451-497`) | `feature/<slug>` | `<base>/worktrees/<slug>` | `_bootstrap` on fresh creation only | Exit 1 plus a stderr line (`:2161-2178`) |
| `SCRIPT create-only` `:1810-1861` | C R B | `--repo-root`, else script-location anchor, else search of cwd's children (`:229-282`) | **local `main`**, no fetch | `feature/<slug>` | same | same | same |
| `SCRIPT create-ac-worktree` `:1864-1970` | C R B | **script-location anchor only** (`:1907`); no fallback, no `--repo-root` | `origin/main` after a best-effort fetch (`:500-524`). An existing branch is reused **as-is** (`:578-603`). | `ac-authoring/<session>` or `ac-YYYYMMDD` | same | same | same, but git's stdout leaks (F4) |
| `SCRIPT create-fastlane-worktree` `:1973-2061` | C R B V | **script-location anchor only** (`:2007`) | `origin/main` after a best-effort fetch. An existing branch is force-reset with `-B` (`:1238-1262`). | `fast-lane/<slug>` | same | same | Refusal JSON with exit 0 when occupied (`:2020-2023`); exit 1 otherwise; reports `base_commit` (`:1157-1196`) |
| `SCRIPT _bootstrap` `:1393-1580` | B | — | — | — | — | Steps: `.env` symlink or copy; `.mcp.json` copy; `git submodule update`; poetry or pip; `build.py --target-dir <wt>`; `.leafcutter` symlink, else a copy of `.pre-commit-config.yaml` (`:1289-1390`); drift hook; shims (`:1648-1744`) | `build.py` failure only warns (`:1554-1560`); the AC-5 probe accepts `.leafcutter` alone (`:1577-1580`) |
| `scripts/setup_ticket_worktree.py` (tracked, 2,266 lines) | C R B | as above, but **without** the search fallback or `--repo-root` | as above | as above | as above | Adds a create-time `verify_precommit_active.py` gate that the template **must not** have (`unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py:90-100`) | — |
| `templates/scripts/worktree_repo_facts.py` | L V | `--git-common-dir` from the `start` argument, which **defaults to `.`** (`:139-181`, `:235-236`) | `branch-standing` runs `git fetch origin main` (`:184-222`) | — | `<base>/worktrees` | — | Always exits 0; nulls when not in a repository |
| `templates/scripts/git_recovery.py:54-79` | C | — | an existing branch | reuses the branch | new path | none | Recovery-only |

### 2.2 Workflows (runtime WF; every step is an agent dispatch)

| Site | Op | Script or command, and the agent it goes to | Base / branch / location | Failure → halt? |
|---|---|---|---|---|
| `plan-feature.js:2262-2514` | L C R | Resolver sent to **status-checker** (`:2447`), then `create-ac-worktree` sent to worktree-agent (`:2465-2470`) | `origin/main`, `ac-authoring/<component>` | **No.** Only an explicit non-zero exit halts. Anything else continues without a worktree (section 1). |
| `build-feature.js:1404-1452` | L R C V | `worktree_repo_facts.py facts/base/branch-standing` sent to status-checker (`:1409-1440`). Then a **free-text** prompt to worktree-agent: "Open a NEW git worktree at the EXACT location … Bootstrap it (copy/symlink .leafcutter …)" (`:1442`). No script is named. | `origin/main`, or the existing branch; `epic/<kebab>` or `ticket/<kebab>`; `<base>/<identity>` | Yes, every null halts (`undetermined()` `:1415`). But `base` without a start path returns nulls from the workspace parent, so every dev-layout run halts (KI-BO-20260921-worktree-base-resolver; reproduced in section 4). Branch and base are never checked after creation, only the location. |
| `build-ticket.js:1184-1274` | L V | Trusts `args.worktree_path` unchecked (`:1184`, `:1206`), else status-checker runs `test -f .git`, `branch --show-current`, `--show-toplevel` (`:1215-1224`) | — | Yes (`:1228-1274`) |
| `build-epic.js:305-347` (not called from anywhere) | L V | status-checker probe (`:312-319`) | — | **No.** It falls back to `callerWorktreePath \|\| probe \|\| epicPath` (`:345-347`), and a null probe skips the not-on-main guard. |
| `quick-fix.js:230-353` | L C V | General-purpose agent. It looks for the script only at `<cwd>/scripts/` and `<cwd>/leafcutter-ai/scripts/` (`:283-284`), never `.leafcutter/scripts`. In this workspace that picks the **tracked, drifted** `leafcutter-ai/scripts/` copy, which lacks the search fallback and `--repo-root`; in an adopter it finds nothing and blocks. Staleness gate (`:290-300`), then `create-only` (`:307`), then a branch check (`:333-353`). | **local `main`**, after refusing if local main is behind; `feature/<slug>` | Yes, a blocked or null reply halts (`:152-157`). The reported `worktree_root` is trusted without a git cross-check (`:322-323`). |
| `fast-lane-ship.js:668-851` | C R V | `python3 .leafcutter/scripts/setup_ticket_worktree.py create-fastlane-worktree` sent to worktree-agent "from the repository root" (`:678`); git verification (`:781-841`) | `origin/main`, `fast-lane/<slug>` | Yes (`:714-753`), except `:841`: an empty verify reply falls back to the path the model claimed |
| `finalize-feature.js:488-577` | L V | status-checker runs `git worktree list` and matches by substring (`:488-538`) | — | **No.** A malformed reply becomes `worktree_root: "unknown"`, which passes the main-branch check (`:541-548`, `:565-577`). |
| `finalize-feature.js:780-834`, `:1299-1340` | C B X | `git -C <root> worktree add --detach /tmp/leafcutter-main-baseline-* origin/main`, then `build.py`, then pytest, then `worktree remove --force` (general-purpose agent / status-checker) | `origin/main` **without a fetch** | Degrades and continues (`:836-895`) |
| `finalize-feature.js:2246-2316` | X | worktree-agent "Remove the worktree at …", with no schema | — | An unparseable probe is read as `{exists:true}`; the step is marked complete even when `removed:false` |

### 2.3 Agents, skills, commands and docs

| Site | Op | Recipe | Notes |
|---|---|---|---|
| `templates/agents/worktree-agent.md:96-118` | C R | `python scripts/setup_ticket_worktree.py create-only` or `setup-ticket`. The path is relative, so it only works with cwd = repo root. Epic paths go to the `feature` skill (`:114`). | Tells the agent to parse `ticket_path_new` (`:112`), but the script emits `ticket_path_final`. Has no recipe for the location, branch and start ref that build-feature asks for. |
| `templates/agents/worktree-agent.md:120-150` | V | Probe: `.pre-commit-config.yaml` exists | — |
| `templates/skills/feature/SKILL.md:70-142` (Epic Workflow) | C B V | `MAIN_REPO=$(pwd)`, `git fetch origin`, `git worktree add -b "$EPIC_NAME" "$REPO_PARENT/$EPIC_NAME" origin/main`. Bootstrap by hand; `import settings` check (a project-specific leftover); `build.py`; `ln -s` or `cp` fallback. | A **sibling** of the repository, and a branch **with no prefix**. The adopter repo `bybit-trader` has 107 worktrees placed this way, versus 21 under `worktrees/` (measured with `git worktree list`). |
| `templates/skills/feature/SKILL.md:210-216` (Feature Workflow) | C | `python scripts/setup_ticket_worktree.py create-only` | `:230` says "always base on origin/main", which is false for `create-only` |
| `templates/skills/build-single-ticket/SKILL.md:62-111` | C R B | `python scripts/setup_ticket_worktree.py setup-ticket "$TICKET_PATH"` | Halts on non-zero (`:81-83`) |
| `templates/skills/quick-fix/SKILL.md:202-284` | L C | Same two-location lookup and `create-only` as quick-fix.js | Has no rule for a non-JSON reply |
| `templates/skills/plan-feature/SKILL.md:125-205` | V | Pre-flight `check_workspace_setup_permission.py`; result passed as `args` | `templates/commands/plan-feature.md:19` calls `Workflow("plan-feature", …)` **without** running the pre-flight, so that entry point always stops with "MISSING pre-flight" (`plan-feature.js:2354-2365`) |
| `templates/workflows/close-worktree.md:83-164` | X | Sweep with `python leafcutter/scripts/worktree/sweep_processes.py` (`:85`, a prefix that matches neither layout), then `worktree remove`, `--force`, the `\\?\` MAX_PATH escape, `prune`, `branch -d`, delete the remote branch | Confirmation-gated |
| `templates/skills/building-epics/SKILL.md:86-119`, `:761-783` | V X | Pre-drive `verify_precommit_active.py`, which does not hard-halt; a fallback that runs `git worktree remove` directly | — |
| `templates/skills/build-feature-ops-notes/SKILL.md:277-283` | C | `git worktree add --detach /tmp/base origin/main` | No removal step |
| `templates/skills/ship/SKILL.md:50-53` | X | `git worktree remove`; `git branch -d feature/<name>` | — |
| `templates/workflows/build-backlog.md:127-142` | C | `Agent(worktree-agent, create)` | — |
| `docs/how-to/drive-epic-manually.md:87-93` | C | `EnterWorktree` tool, "do not use any shell script" | **No bootstrap at all**. The harness puts these under `.claude/worktrees/agent-*`; 9 of them exist in `bybit-trader`. |
| `CLAUDE.md:546-573` | B V | Manual `ln -s <main>/.leafcutter` or `cp .pre-commit-config.yaml`; check `ls … .pre-commit-config.yaml \|\| ls … .leafcutter` | The check has the same fail-open OR as the script (F7) |
| `CLAUDE.md:575-595` | B | The allowlist must be edited in both the worktree root and the workspace root, because the hook resolves through the symlink | Exists only because of the symlink approach |
| `CLAUDE.md:599-633` | C | Land the scaffold on `origin/main` before creating the epic worktree | Needed because the base is `origin/main`, not local `main` |

## 3. Divergences

| Dimension | Variants in use | Evidence |
|---|---|---|
| **Repository-root resolution** | (a) the script's own location, `git -C <script dir> rev-parse --show-toplevel`; (b) (a) plus a search of cwd's children, `create-only` only; (c) the parent of `--git-common-dir` from cwd, then child and sibling probes (plan-feature's shell snippet); (d) `--git-common-dir` from a `start` argument that defaults to cwd (`worktree_repo_facts`); (e) `MAIN_REPO=$(pwd)` (feature skill); (f) `ls <cwd>/scripts/…` or `<cwd>/leafcutter-ai/scripts/…` (quick-fix); (g) `--show-toplevel` from cwd (build-ticket, finalize) | `SCRIPT:137-168`, `:229-282`; `plan-feature.js:2062-2096`; `worktree_repo_facts.py:139-181`; `feature/SKILL.md:70-72`; `quick-fix.js:283-284`; `build-ticket.js:1219` |
| **Which copy of the script runs** | `<workspace>/.leafcutter/scripts/` (current); `leafcutter-ai/.leafcutter/scripts/` (stale, gitignored, 2026-09-09); `leafcutter-ai/scripts/` (tracked, divergent source); an adopter's deployed copy | File sizes, dates and diffs in section 1; `SCRIPT` decision-history note on deliberate drift (template, near `:2226-2232`) |
| **cwd assumption** | "run from the repository root" (fast-lane, worktree-agent, feature); any cwd (plan-feature snippet); cwd = worktree root (commit and building-epics probes) | `fast-lane-ship.js:677`; `worktree-agent.md:101`; `CLAUDE.md:756-765` |
| **Base ref** | local `main` (`setup-ticket`, `create-only`); `origin/main` (ac, fast-lane, build-feature, feature epic); an existing branch tip (ac reuse, build-feature reuse); `origin/main` without a fetch (finalize) | `SCRIPT:487`, `:617`, `:1249`; `build-feature.js:1435-1440`; `finalize-feature.js:795` |
| **Fetch** | none; best-effort that warns; mandatory that halts (`branch-standing`) | `SCRIPT:500-524`; `worktree_repo_facts.py:201`; `build-feature.js:1437` |
| **Branch naming** | `feature/`, `ac-authoring/`, `fast-lane/`, `epic/`, `ticket/`, bare `EPIC-<Name>`, harness `worktree-agent-<id>`; in live use also `fix/`, `acs/`, `codex/` | `SCRIPT:1803`, `:1929`, `:643`; `build-feature.js:1427`; `feature/SKILL.md:76`; `git worktree list` in both repos |
| **Reuse matching** | `_worktree_exists` knows `feature/ ticket/ ac-authoring/ fast-lane/` but not `epic/` or bare `EPIC-*`; build-feature matches on exact location plus branch; finalize matches on a branch substring | `SCRIPT:403-410`; `build-feature.js:1431`; `finalize-feature.js:488-538` |
| **Landing directory** | `<workspace>/worktrees/<slug>` (dev layout); `<consumer>.parent/worktrees/<slug>` for a deployed copy in an adopter (inferred from `SCRIPT:342-364`: the deployed copy's anchor is the consumer root, whose parent is not a repository, so "dev layout" is chosen); a sibling of the main checkout (feature epic); `.claude/worktrees/` (harness); `/tmp/leafcutter-main-baseline-*` (finalize) | `SCRIPT:285-364`; `feature/SKILL.md:72-74`; `finalize-feature.js:795` |
| **Bootstrap** | full `_bootstrap`; a hand-written subset (feature epic); "copy/symlink .leafcutter", left to an LLM (build-feature); `build.py` only (finalize temp worktrees); none (`EnterWorktree`); none on reuse (every `SCRIPT` subcommand) | `SCRIPT:1941-1951`; `build-feature.js:1442`; `drive-epic-manually.md:87-93` |
| **Symlink vs copy** | Symlink `.leafcutter` first, else copy `.pre-commit-config.yaml` (script); `ln -s`, else `cp` (feature, CLAUDE.md); `build.py` output as real files (what the current `worktrees/*` actually contain). The symlink is what causes KI-CG-009, the allowlist dual-update rule and KI-BP-017 / KI-FC-001. | `SCRIPT:1343-1382`; `CLAUDE.md:531-541`, `:575-583`; KI-CG-009 `:37-60` |
| **Windows** | Without Developer Mode, `os.symlink` raises WinError 1314, so the `.env` and `.leafcutter` symlinks both fall back or fail; PowerShell `\\?\` escape for MAX_PATH on remove | Sandbox run (F5); `close-worktree.md:118-143` |
| **Output contract** | one JSON line (intended); JSON line mixed with git's stdout (ac, fast-lane in practice); discriminated `outcome` (fast-lane only); nothing at all (feature skill, `EnterWorktree`) | F4 |
| **Failure semantics** | exit 1 plus stderr; exit 0 plus refusal JSON; exit 0 plus nulls (`worktree_repo_facts`); warn and continue (`build.py`, fetch, shims) | `SCRIPT:2161-2178`, `:2020-2023`; `worktree_repo_facts.py:245-262`; `SCRIPT:1554-1560` |
| **Who runs it** | status-checker (`permits_shell: false`), worktree-agent (`permits_shell: true`, Haiku in the template, Sonnet in the registry), general-purpose, the main loop | `config/agent_registry.json:1300`, `:1368`; `worktree-agent.md` frontmatter |

## 4. Failure modes, with evidence

Moved to [2026-09-25-worktree-failure-modes.md](2026-09-25-worktree-failure-modes.md): failure modes F1–F14, with evidence.

## 5. Proposal: one standalone worktree component

Moved to [2026-09-25-worktree-component-proposal.md](2026-09-25-worktree-component-proposal.md): the proposed standalone component: shape, CLI, result contract, ownership and caller rules.

## 6. Migration plan

Moved to [2026-09-25-worktree-migration-plan.md](2026-09-25-worktree-migration-plan.md): the migration order and the behavioural test matrix.

## 7. Open questions for the user

1. **Clones or worktrees?** ADR-018 (status *Proposed*) wants to retire shared-`.git`
   worktrees for autonomous drives in favour of per-feature clones
   (`docs/architecture/adrs/ADR-018-agent-isolation-topology.md:1-50`). Should the component's
   contract be written as "isolated working copy" with worktree as today's implementation, so
   a clone backend can drop in later?
2. **Symlink or real files for `.leafcutter`?** Symlinks caused F8 and fail on Windows without
   Developer Mode. Running `build.py --target-dir <worktree>`, which the live `worktrees/*`
   already carry as real files, avoids both, at the cost of the build's run time and
   KI-BP-004's frozen-hooks staleness. Proposed default: real files, plus a re-bootstrap on
   every `ensure`.
3. **One base for every kind?** Today ticket and feature worktrees branch from local `main` so
   an unpushed ticket-creation commit is included, and everything else branches from
   `origin/main`. Should `origin/main` after a fetch be universal, with "local main is ahead"
   reported as a refusal that tells you to push first?
4. **One naming scheme?** Proposed: `<kind>/<slug>` for every kind, including `epic/`. Existing
   `EPIC-<Name>` sibling worktrees in adopters would then need either a one-time migration or a
   `locate` alias.
5. **Where should adopter worktrees live?** `<consumer>/worktrees/` (inside the project,
   gitignored), or `<consumer>.parent/worktrees/`, where the deployed copy currently puts them
   and where every project in `~/Code` would share one directory?
6. **Should `leafcutter-ai/.leafcutter/` exist at all?** It is a stale, gitignored build
   output inside the package repository, produced by running `build.py` there without
   `--target-dir` (`scripts/build.py:1878`). Today's resolver prefers it over the current
   deployment. Options: refuse that invocation, or turn the directory into a pointer to the
   workspace deployment.
7. **Which agent runs shell steps for workflows?** Options:
   - broaden worktree-agent's charter to "run this exact command";
   - add a narrow `shell-runner` agent with `permits_shell: true`;
   - have the skill layer (main loop) create the worktree before invoking the workflow and pass
     it in via `args`. This is the pattern the plan-feature pre-flight already uses, and it
     removes the LLM from the create path entirely.
8. **When may removal happen?** Should `remove` always require a caller-supplied confirmation
   token, so that sandboxed callers like finalize Step 7 stop deadlocking on worktree-agent's
   interactive "yes"?

## 8. Decisions (2026-09-25)

The user decided questions 1, 2, 3 and 7 on 2026-09-25. For questions 1 and 2 the user asked
an expert review agent to decide. Its measured reasoning is kept in
[the decision memo](2026-09-25-worktree-isolation-decision-memo.md), and the user accepted it
as sound.

| # | Question | Decision | Decided by |
|---|---|---|---|
| 1 | Clones or worktrees? | **Per-feature clones.** Each is a hardlinked local-path clone of the main checkout, with `origin` re-pointed at the hub. There is no `git worktree`, and no `--shared` or `--reference` by default. The landing directory stays `<base>/worktrees/<slug>`, and the JSON keeps `worktree_path` as an alias. This accepts the direction of ADR-018 §1. | Expert memo, accepted by the user |
| 2 | Symlink or real files for `.leafcutter`? | **Real files, never a symlink.** `build.py --target-dir <workspace> --config-path <explicit>` runs on every `ensure`, followed by a clean-tree check and a canary commit that proves the hooks are active. | Expert memo, accepted by the user |
| 3 | One base for every kind? | **Yes: `origin/main` after a fetch, for every kind.** | User |
| 7 | Who runs the create step? | **One standalone script that always creates the workspace the same way.** Agents run it from a skill, and workflows get the result passed in. No workflow step sends worktree creation to an agent as free-form shell work. | User |

These questions are still open and go to the component's AC authoring: 4 (one naming
scheme), 5 (where adopter workspaces live), 6 (whether `leafcutter-ai/.leafcutter/` should
exist) and 8 (a confirmation token for `remove`).

What these decisions mean for sections 5 and 6: section 5's contract still holds, with the
additions listed under "Consequences for the standalone script's contract" in the decision
memo. The script clones rather than adding worktrees. It finds workspaces through a marker
file, not `git worktree list`. There is no symlink step. And its JSON gains `mechanism`, `hub`,
`workspace_path`, `bootstrap.restored_tracked` and `checks.hooks_canary_rejected`.
Section 6's migration order is unchanged. It gains a cut-over chore: prune and retire the 19
registered worktrees, and set `gc.auto=0` on the main checkout in the meantime.

## Method

- **Incident:** read the full workflow journal and each agent's transcript (prompt, tool calls,
  tool results) plus `*.meta.json` for agent types. Cross-referenced with
  `templates/workflows-js/plan-feature.js`. The deployed copy was diffed after normalising CR
  and the output-root placeholder.
- **Sandbox:** a scratch repository with a bare `origin`, a `.leafcutter/` holding
  `pre-commit-config.yaml` only, and the current `templates/scripts/setup_ticket_worktree.py`
  copied into place. Runs:
  - `create-ac-worktree` from the workspace parent (stdout pollution, symlink failure,
    bootstrap error after creation);
  - the same command again (silent reuse with exit 0);
  - a new slug from inside the first worktree;
  - the script copied to a workspace-level `.leafcutter/scripts` running `create-ac-worktree`
    (repository not found) and `create-only` (found via search).
  - Also ran the deployed `worktree_repo_facts.py base` from the workspace parent,
    `leafcutter-ai`, and a real worktree.
- **Inventory:** grep over `templates/`, `scripts/`, `docs/`, `unit_tests/`, `tests/` and both
  CLAUDE.md files for `worktree add|remove|prune`, `setup_ticket_worktree`, the subcommand
  names, `EnterWorktree`, `git-common-dir`, `show-toplevel`, `.leafcutter` and
  `.pre-commit-config.yaml` bootstrap. Every hit was read in context. Placement counts come
  from `git worktree list --porcelain` in `leafcutter-ai` and `bybit-trader`.
- **Not verified by running:**
  - the consumer-layout landing directory in section 3 (inferred from `SCRIPT:342-364`);
  - behaviour under WSL2 and macOS.
