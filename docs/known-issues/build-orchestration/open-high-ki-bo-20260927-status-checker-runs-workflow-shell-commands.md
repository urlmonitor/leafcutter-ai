---
title: "KI-BO-20260927-status-checker-runs-workflow-shell-commands — six workflows still send shell, git and script commands to status-checker, the agent registered as not permitted to run them, so any of those steps fails whenever it declines"
description: "high — PR #896 moved plan-feature's pause-store calls off status-checker after it refused one. About 40 other shell dispatches across plan-feature, build-feature, build-ticket, build-epic, fast-lane-ship and finalize-feature still go to it, including git reset --hard, git restore and rm. Enumerated on main at 93bd801c. Refusals are by judgement, so they are intermittent."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-28'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
  - docs/known-issues/build-orchestration/open-blocker-ki-bo-20260925-finalize-gate-accepts-agent-answers.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-020.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-008.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260928-pause-verify-rejects-an-enveloped-read-back.md
---

# KI-BO-20260927-status-checker-runs-workflow-shell-commands — six workflows still send shell, git and script commands to status-checker, the agent registered as not permitted to run them, so any of those steps fails whenever it declines

- **Severity:** high. The failure is silent and intermittent. `status-checker` complies most of the time. When it declines, the caller gets a failed or unparseable reply, and most sites treat that as a real answer: "no orphans", "branch unknown", "store absent".
- **Status:** open. No AC. Widens `KI-BO-20260901-1620`, which covers only fast-lane-ship.js.
- **Occurrences:** 2. Occurrence 1: `/plan-feature` run `wf_734389cf-248`, 2026-09-25, `pause_store.py write` → `pause_persist_failed` (session observation, not re-verified). Occurrence 2: three refusals in `plan-feature` and `finalize-feature` builds on 2026-09-25, moved here from `KI-BO-20260901-1620` on 2026-09-28 (see [Occurrences](#occurrences)). Its `pause-persist` refusal is probably the same event as Occurrence 1. Earlier refusals: `KI-BO-020` (fast-lane release, twice).
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** the `agentType: "status-checker"` sites below, `templates/workflows-js/*.js` on main at `93bd801c`.

## The charter mismatch

`config/agent_registry.json:1296-1300` gives `status-checker` `permits_shell: false`. It is the only agent that says `false` explicitly. Its template limits it to ticket investigation: *"Edits restricted to `tickets/**/*.md` and your own response. Never edit code."* (`templates/agents/status-checker.md:221`). It holds `Bash` for read-only diagnostics, which the schema allows (see `KI-BO-20260901-1620`'s correction). It does not hold it to mutate a repository. It declines by reading its charter, so whether a given prompt is refused depends on wording and model.

PR #896 (`06bfbddf`, BO-2300a-1-ii, merged 2026-09-25) moved plan-feature's pause-store calls to `worktree-agent` after exactly such a refusal. The same pattern survives everywhere else.

## Sites (line = the `agentType` line)

**Mutating** (these change the repository, the store or the logs):

| file:line | label | command |
|---|---|---|
| plan-feature.js:974 | `discard-orphan-delete` | `rm -f <file>` |
| plan-feature.js:988 | `discard-orphan-unstage` | `git restore --staged` |
| plan-feature.js:1000 | `discard-orphan-restore` | `git restore` |
| plan-feature.js:1184 | `pt-telemetry` | `mkdir -p` + `printf >>` log append |
| plan-feature.js:1462 | `pt-reconcile-run` | `python apply_flow_backlinks.py` (writes flow files) |
| plan-feature.js:3495 | `apply-approval` | Edit of AC YAML (`readiness`, `priority`), outside `tickets/**` (not shell, but outside the charter) |
| finalize-feature.js:374, :446 | `read-pause-record`, `pause-persist` | `pause_store.py read/write` (see `KI-BO-20260925-finalize-gate-accepts-agent-answers`) |
| finalize-feature.js:655 | `cleanup-baseline-worktree` | `rm -rf` |
| finalize-feature.js:725 | `gh-auth-switch` | `gh auth switch` |
| finalize-feature.js:1340 | `step-3-targeted-rerun` | `git worktree add`, `build.py`, `python3 -m pytest`, `rm -rf`. FIN-100h's own comment at `:829-832` says `status-checker` refuses this kind of step |
| finalize-feature.js:1562 | `step-3.5-reset-merge` | `git merge --abort` / **`git reset --hard HEAD`** |
| finalize-feature.js:1661 | `step-3.5-closure` | edits + `git commit` |
| finalize-feature.js:2127 | `step-5-sync-main` | `git checkout main && git pull` |

**Read-only shell** (these return data the workflow branches on):

| file | lines (label) |
|---|---|
| plan-feature.js | 315, 1237 (`branch-check`); 613 (`scan-orphans-git-status`); 835 (`scan-committed-stages`, refused live on 2026-09-25); 952 (`discard-orphan-status`); 1141 (`pt-store-check`); 1377 (`resume-flow-ref`); 2320 (`detect-current-branch`); 3028 (`resume-log`) |
| build-feature.js | 1359 (`resolve-target`, `test -f .git`); 1410 (`repoFactsCall`: `worktree_repo_facts.py`, called at 1419/1423/1428/1434); 1657 (`ticket-planner`, told to verify test files "with the shell") |
| build-ticket.js | 1223 (`worktree-check`: `test -f`, `git branch`, `git rev-parse`); 1284 (`ticket-planner`, same shell check) |
| build-epic.js | 318 (`worktree-check`: `test -f`, `git branch`) |
| fast-lane-ship.js | 886 (`resolve-connected`, `select-connected`); 973 (producibility guard) |
| finalize-feature.js | 537 (`pre-flight`); 679, 703 (`gh-config`, `gh-auth-status`); 918 (`step-1-pr-probe`); 1263 (`step-3-changed-files`); 1495, 1522 (3.5 probes); 1768 (`pre-step-4-sync-check`); 2006 (`step-4-pr-state`); 2210 (`step-6-scope-detect`); 2250 (`step-7-worktree-probe`) |

**In charter, not counted:** plan-feature.js:671 (`scan-orphans-read-file`, a file read). build-feature.js:1091/1122/2291/2728 and the build-ticket/build-epic readback, completion and planner reads of ticket files. The ask-the-user gates (plan-feature.js:2605, 2694, 2864, 3227, 3367; finalize-feature.js:2041) are a provenance problem, covered by `KI-BO-20260925-finalize-gate-accepts-agent-answers`.

**Already moved off `status-checker`, not counted:** plan-feature.js:1865, :1886 (`pause-persist`, `pause-persist-verify`) and :2479 (`resolve-worktree-setup-script-path`), all by PR #896. finalize-feature.js:829 (`step-0-baseline`) and :1017 (`step-2-merge-main`), by AC FIN-100h. plan-feature.js has 21 `status-checker` dispatches in total. The ones not listed above are in charter.

**fast-lane-ship.js vs `KI-BO-20260901-1620`:** 1620's claim site has since moved to `CLAIM_EXECUTOR_AGENT_TYPE = "worktree-agent"` (`:1050`, `:1058`), and release uses `python-coder` (`:515`). Its other two sites remain on `status-checker` at `:886` and `:973` (1620 cites them as 666/750).

## Occurrences

**Occurrence 1 — 2026-09-25, `wf_734389cf-248`.** See the Occurrences line above.

**Occurrence 2 — 2026-09-25, `plan-feature.js` and `finalize-feature.js` builds; one refusal ended a
run that could not be resumed.** Moved here from `KI-BO-20260901-1620` on 2026-09-28. Windows 11,
workspace-parent layout. Three `status-checker` dispatches that run shell commands were refused as
out of scope:

| run build | step | effect |
|---|---|---|
| deployed `plan-feature.js` built before PR #896 | `pause-persist` (a `pause_store.py` write for `gate-po`) | `pause-persist-verify` found no record, and the run ended `pause_persist_failed` ("this run CANNOT be resumed") at the first human gate |
| same | `scan-committed-stages` (`git log origin/main..HEAD`) | declined |
| an older deployed build | `resolve-workspace-setup-permission` (`cat agent_registry.json`) | refused. That dispatch was later removed by ACD-2100b-5 |

PR #896 (`06bfbddf`, merged 2026-09-25 17:11 UTC, BO-2300a-1-ii) has since moved the pause-store
round trip and `resolve-worktree-setup-script-path` to `worktree-agent`. The DECISION HISTORY at
`plan-feature.js:3580-3603` cites `KI-BO-20260901-1620`. The deployed copies that refused did not
have that fix. `KI-BP-008` Occurrence 3 explains why stale copies ran. `finalize-feature.js` kept
its own copy of the pause helpers, which #896 left as "a known residual" (`:374`, `:446` in the
Mutating table). The remaining sites from this occurrence are already in the tables above.

A `pause_persist_failed` from a build that has #896 has a different cause: `worktree-agent` wraps
the read-back in an envelope of its own and the verify rejects it. That is
`KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back`, not this entry.

## Detection

`grep -n 'agentType: *"status-checker"' templates/workflows-js/*.js`, then read each prompt for `Run`, `git `, `python`, `rm`, `gh `. At runtime, a refusal shows up as a step whose reply is prose instead of the requested JSON. Most sites parse that as a failure and fail closed or treat it as empty. The run's own result rarely names the refusal.

## Workaround

None in the product. Re-run the workflow. Refusals are not deterministic.

## Suggested fix

1. Move the mutating sites first, finalize's `git reset --hard` and `git commit` and plan-feature's `discard-orphan-*` before the rest, to an agent whose charter covers them.
2. **Residual: `worktree-agent` is a stopgap, not the answer.** It is the only `permits_shell: true` agent (`config/agent_registry.json:1368`), which is why #896 and the fast-lane claim fix chose it. But its template says *"You are the worktree lifecycle agent. You have exactly two actions: **create** and **remove**."* (`templates/agents/worktree-agent.md:85`). Running `pause_store.py`, `git log` or `rm` is outside that charter too. It has not refused yet, for the same reason `status-checker` usually does not. The durable fix is `KI-BO-20260901-1620` item 4: a dedicated shell-executor agent chartered to run one given command and return its stdout/exit code, plus 1620 item 2's mechanical check that every shell-bearing `agentType` dispatch names a `permits_shell: true` agent.
3. The E2 engine gives workflow bodies no subprocess access (1620 item 3), so "call the CLI directly" is not available.

**Pattern:** a fix applied at the site that failed, while the same dispatch shape stays live at about 40 other sites that simply have not failed yet.
